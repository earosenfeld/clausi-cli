"""AI provider abstraction for local, BYOK compliance scanning.

Calls Anthropic/OpenAI directly with the user's own API key - no Clausi
backend involved. Prompt/response contract matches the original hosted
service so cached results and report generation stay compatible.
"""

import json
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


PROMPT_TEMPLATE = """You are a compliance auditor analyzing code for {regulation} compliance.

Your task is to identify potential compliance violations in the provided code.

Focus on these specific clauses:
{clause_list}

File: {file_path}

Code to analyze:
```
{code}
```

Respond with a JSON object in this exact format:
{{
  "findings": [
    {{
      "clause_id": "EUAIA-3.1",
      "clause_text": "Brief clause description",
      "violation": "Description of the violation",
      "severity": "critical|high|medium|low",
      "confidence": 0.95,
      "finding_certainty": "High|Medium|Low",
      "remediation_complexity": "High|Medium|Low",
      "responsible_party": "Engineering|Security|Data|Legal|Product",
      "why_this_matters": "Brief business context for this requirement",
      "business_impact": "Consequence of non-compliance",
      "line_start": 10,
      "line_end": 15,
      "code_snippet": "relevant code excerpt",
      "recommendation": "How to fix this",
      "auto_fixable": true,
      "evidence": "Why this is a violation"
    }}
  ]
}}

Rules:
- Only include actual violations, not potential issues
- Confidence score: 0.0 (uncertain) to 1.0 (certain)
- finding_certainty: High (>=0.8), Medium (0.5-0.8), Low (<0.5)
- Severity: critical (blocking issue), high (legal risk), medium (best practice), low (minor)
- remediation_complexity: High (architecture change), Medium (moderate refactor), Low (simple code change)
- responsible_party: Most appropriate team to fix (Engineering, Security, Data, Legal, Product)
- auto_fixable: true only if fix is simple and safe
- Provide line numbers if identifiable
- Be specific and actionable in recommendations

IMPORTANT: Return ONLY the JSON object, with no explanatory text before or after it."""


def clause_display_text(clause: Dict[str, Any]) -> str:
    """Build a human-readable text blob for a clause from its YAML fields."""
    title = clause.get("title", "")
    description = clause.get("description", "")
    requirements = clause.get("requirements") or []
    parts = [p for p in (title, description) if p]
    text = ": ".join(parts) if parts else clause.get("id", "")
    if requirements:
        text += "\n  Requirements: " + "; ".join(requirements)
    return text


def build_prompt(regulation: str, clauses: List[Dict[str, Any]], file_path: str, code: str) -> str:
    """Build the compliance-analysis prompt for a single file."""
    clause_lines = []
    for clause in clauses:
        clause_id = clause.get("id", "")
        clause_lines.append(f"- {clause_id}: {clause_display_text(clause)}")
    return PROMPT_TEMPLATE.format(
        regulation=regulation,
        clause_list="\n".join(clause_lines),
        file_path=file_path,
        code=code,
    )


def extract_json_object(text: str) -> Dict[str, Any]:
    """Parse a JSON object out of a model response.

    OpenAI is called with response_format=json_object, so its output is always
    bare JSON. Claude has no equivalent guarantee: despite the prompt asking for
    JSON only, it commonly wraps the object in ```json fences or prefixes a
    sentence like "Here is the analysis:". Parsing the raw text directly made
    every such response an analysis failure.
    """
    if text is None:
        raise ValueError("empty response")

    candidate = text.strip()

    # Strip a fenced block, with or without a language tag.
    fence = re.match(r"^```[a-zA-Z]*\s*\n(.*?)\n?```$", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Last resort: the outermost {...} span, for prose wrapped around the object.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end > start:
        return json.loads(candidate[start:end + 1])

    raise json.JSONDecodeError("no JSON object found in response", candidate, 0)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) - no tokenizer dependency needed for BYOK."""
    return max(1, len(text) // 4)


class AIProviderError(Exception):
    """Raised when an AI provider call fails."""


class AIProvider(ABC):
    """Base class for a BYOK AI provider used to scan a single file."""

    name = "base"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def analyze_code(self, regulation: str, clauses: List[Dict[str, Any]],
                      file_path: str, code: str) -> Dict[str, Any]:
        """Analyze a single file and return {"findings": [...], "prompt_tokens": int,
        "completion_tokens": int}."""

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate USD cost for the given token counts."""

    @abstractmethod
    def generate_text(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Freeform (non-JSON) generation, e.g. for documentation.

        Returns {"text": str, "prompt_tokens": int, "completion_tokens": int}.
        """


class ClaudeProvider(AIProvider):
    """Anthropic Claude provider."""

    name = "claude"
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    # USD per 1M tokens (input, output)
    PRICING = {
        "claude-3-5-sonnet-20241022": (3.0, 15.0),
        "claude-3-opus-20240229": (15.0, 75.0),
        "claude-3-sonnet-20240229": (3.0, 15.0),
    }

    def __init__(self, api_key: str, model: Optional[str] = None):
        super().__init__(api_key, model or self.DEFAULT_MODEL)
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)

    def analyze_code(self, regulation, clauses, file_path, code):
        prompt = build_prompt(regulation, clauses, file_path, code)
        try:
            # No temperature: the Anthropic SDK removed sampling parameters from
            # messages.create() in 1.0, and current models reject them with a 400.
            response = self._client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            raise AIProviderError(f"Claude API error: {e}") from e

        text = response.content[0].text
        try:
            parsed = extract_json_object(text)
        except (json.JSONDecodeError, IndexError, ValueError) as e:
            raise AIProviderError(f"Could not parse Claude response as JSON: {e}") from e

        usage = getattr(response, "usage", None)
        return {
            "findings": parsed.get("findings", []),
            "prompt_tokens": getattr(usage, "input_tokens", estimate_tokens(prompt)),
            "completion_tokens": getattr(usage, "output_tokens", estimate_tokens(text)),
        }

    def estimate_cost(self, input_tokens, output_tokens):
        in_rate, out_rate = self.PRICING.get(self.model, self.PRICING[self.DEFAULT_MODEL])
        return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate

    def generate_text(self, system_prompt, user_prompt):
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as e:
            raise AIProviderError(f"Claude API error: {e}") from e

        text = response.content[0].text
        usage = getattr(response, "usage", None)
        return {
            "text": text,
            "prompt_tokens": getattr(usage, "input_tokens", estimate_tokens(system_prompt + user_prompt)),
            "completion_tokens": getattr(usage, "output_tokens", estimate_tokens(text)),
        }


class OpenAIProvider(AIProvider):
    """OpenAI provider."""

    name = "openai"
    DEFAULT_MODEL = "gpt-4o"
    PRICING = {
        "gpt-4": (30.0, 60.0),
        "gpt-4-turbo": (10.0, 30.0),
        "gpt-4o": (5.0, 15.0),
    }

    def __init__(self, api_key: str, model: Optional[str] = None):
        super().__init__(api_key, model or self.DEFAULT_MODEL)
        import openai
        self._client = openai.OpenAI(api_key=api_key)

    def analyze_code(self, regulation, clauses, file_path, code):
        prompt = build_prompt(regulation, clauses, file_path, code)
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": "You are a compliance auditor. Respond only with JSON."},
                    {"role": "user", "content": prompt},
                ],
            )
        except Exception as e:
            raise AIProviderError(f"OpenAI API error: {e}") from e

        text = response.choices[0].message.content
        try:
            parsed = extract_json_object(text)
        except (json.JSONDecodeError, ValueError) as e:
            raise AIProviderError(f"Could not parse OpenAI response as JSON: {e}") from e

        usage = getattr(response, "usage", None)
        return {
            "findings": parsed.get("findings", []),
            "prompt_tokens": getattr(usage, "prompt_tokens", estimate_tokens(prompt)),
            "completion_tokens": getattr(usage, "completion_tokens", estimate_tokens(text)),
        }

    def estimate_cost(self, input_tokens, output_tokens):
        in_rate, out_rate = self.PRICING.get(self.model, self.PRICING[self.DEFAULT_MODEL])
        return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate

    def generate_text(self, system_prompt, user_prompt):
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                temperature=0.2,
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as e:
            raise AIProviderError(f"OpenAI API error: {e}") from e

        text = response.choices[0].message.content
        usage = getattr(response, "usage", None)
        return {
            "text": text,
            "prompt_tokens": getattr(usage, "prompt_tokens", estimate_tokens(system_prompt + user_prompt)),
            "completion_tokens": getattr(usage, "completion_tokens", estimate_tokens(text)),
        }


class LocalAgentProvider(AIProvider):
    """Runs analysis through an agent CLI already installed and signed in.

    No API key: the CLI uses whatever credentials the user has already set up
    (a Claude Pro/Max subscription, a ChatGPT plan, or its own configured key),
    so scanning works with nothing to obtain or paste. Cost is reported as zero
    because Clausi cannot see the user's plan or per-call billing.
    """

    binary = ""
    friendly_name = ""
    install_hint = ""
    timeout_seconds = 300

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        # api_key is accepted for factory symmetry and deliberately unused.
        super().__init__(api_key or "", model or "")

    @classmethod
    def resolve_binary(cls) -> Optional[str]:
        """Absolute path to the CLI, or None.

        The full path matters on Windows, where these CLIs install as .CMD
        shims that cannot be executed from a bare name.
        """
        return shutil.which(cls.binary)

    @classmethod
    def is_available(cls) -> bool:
        return cls.resolve_binary() is not None

    def _command(self, executable: str) -> List[str]:
        raise NotImplementedError

    def _run(self, prompt: str) -> str:
        executable = self.resolve_binary()
        if not executable:
            raise AIProviderError(
                f"{self.friendly_name} was not found on your PATH. {self.install_hint}"
            )
        try:
            completed = subprocess.run(
                self._command(executable),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                # The prompt goes on stdin, never argv: it embeds whole source
                # files, and Windows caps a command line near 32KB. Keeping it
                # off argv also means no shell ever parses user code.
                input=prompt,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired as e:
            raise AIProviderError(
                f"{self.friendly_name} timed out after {self.timeout_seconds}s"
            ) from e
        except OSError as e:
            raise AIProviderError(f"Could not run {self.friendly_name}: {e}") from e

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[:400]
            raise AIProviderError(
                f"{self.friendly_name} exited {completed.returncode}: {detail}"
            )

        output = (completed.stdout or "").strip()
        if not output:
            raise AIProviderError(f"{self.friendly_name} returned no output")
        return output

    def analyze_code(self, regulation, clauses, file_path, code):
        prompt = build_prompt(regulation, clauses, file_path, code)
        text = self._run(prompt)
        try:
            parsed = extract_json_object(text)
        except (json.JSONDecodeError, ValueError) as e:
            raise AIProviderError(
                f"Could not parse {self.friendly_name} response as JSON: {e}"
            ) from e
        return {
            "findings": parsed.get("findings", []),
            "prompt_tokens": estimate_tokens(prompt),
            "completion_tokens": estimate_tokens(text),
        }

    def estimate_cost(self, input_tokens, output_tokens):
        # Billed by the user's existing plan, not per-token by us.
        return 0.0

    def generate_text(self, system_prompt, user_prompt):
        combined = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
        text = self._run(combined)
        return {
            "text": text,
            "prompt_tokens": estimate_tokens(combined),
            "completion_tokens": estimate_tokens(text),
        }


class ClaudeCodeProvider(LocalAgentProvider):
    """Uses a locally installed, signed-in Claude Code CLI."""

    name = "claude-code"
    binary = "claude"
    friendly_name = "Claude Code"
    install_hint = "Install it from https://claude.com/claude-code and run `claude` once to sign in."

    def _command(self, executable: str) -> List[str]:
        cmd = [executable, "-p"]
        if self.model:
            cmd += ["--model", self.model]
        return cmd


class CodexProvider(LocalAgentProvider):
    """Uses a locally installed, signed-in Codex CLI."""

    name = "codex"
    binary = "codex"
    friendly_name = "Codex"
    install_hint = "Install it from https://developers.openai.com/codex and sign in."

    def _command(self, executable: str) -> List[str]:
        # `codex exec` with no prompt argument reads instructions from stdin.
        cmd = [executable, "exec"]
        if self.model:
            cmd += ["-m", self.model]
        return cmd


LOCAL_AGENT_PROVIDERS = {
    ClaudeCodeProvider.name: ClaudeCodeProvider,
    CodexProvider.name: CodexProvider,
}


def get_ai_provider(provider_name: str, api_key: str, model: Optional[str] = None) -> AIProvider:
    """Instantiate a provider: an API-key one, or a local agent CLI."""
    if provider_name == "claude":
        return ClaudeProvider(api_key, model)
    if provider_name == "openai":
        return OpenAIProvider(api_key, model)
    local = LOCAL_AGENT_PROVIDERS.get(provider_name)
    if local:
        return local(api_key, model)
    raise ValueError(f"Unsupported AI provider: {provider_name}")
