"""AI provider abstraction for local, BYOK compliance scanning.

Calls Anthropic/OpenAI directly with the user's own API key - no Clausi
backend involved. Prompt/response contract matches the original hosted
service so cached results and report generation stay compatible.
"""

import hashlib
import json
import random
import re
import shutil
import subprocess
import time
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
      "impact_score": 4,
      "likelihood_score": 3,
      "risk_rationale": "Why the impact and likelihood scores are appropriate",
      "line_start": 10,
      "line_end": 15,
      "code_snippet": "relevant code excerpt",
      "recommendation": "How to fix this",
      "verification_criteria": "Specific evidence or test that proves the finding is closed",
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
- impact_score: 1 (negligible) to 5 (severe), based on the consequence in this scan scope
- likelihood_score: 1 (rare) to 5 (almost certain), based only on evidence in the supplied code; omit or null when evidence is insufficient
- risk_rationale: Explain the evidence behind impact and likelihood without overstating certainty
- verification_criteria: Define observable, testable closure evidence
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


def analysis_fingerprint(clauses: List[Dict[str, Any]]) -> str:
    """Hash everything that shapes an analysis besides the file content itself.

    The cache is keyed on file content, regulation name, provider, and model.
    None of those change when we edit PROMPT_TEMPLATE or when a regulation pack
    revises a clause's wording - so without this component, an existing user
    would keep being served findings produced by the previous prompt against
    the previous clause text, silently, until the entry expired. Since the
    whole point of maintained regulation packs is that the legal content
    changes, that staleness is a correctness bug, not a performance detail.

    Changing this value invalidates cached entries by design.
    """
    payload = {
        "prompt": PROMPT_TEMPLATE,
        "clauses": sorted(
            f"{c.get('id', '')}|{clause_display_text(c)}" for c in (clauses or [])
        ),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


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


# Every file's request carries the whole prompt scaffold - the instructions plus
# the full text of every clause in scope - so the per-file input is dominated by
# the regulation, not by the file, on anything but the largest sources. Measured
# 2026-08-31: EU-AIA 1,977 tokens (8 clauses), GDPR 2,038 (9), SOC2 2,885 (20).
# Estimating from file content alone understates a real scan by more than 2x.
def prompt_overhead_tokens(regulation: str, clauses: List[Dict[str, Any]]) -> int:
    """Input tokens each file's request costs before any of its code is added."""
    return estimate_tokens(build_prompt(regulation, clauses, "src/placeholder.py", ""))


# Output is a findings array, not a function of input size: a large file does not
# produce a proportionally larger response, and MAX_ANALYSIS_TOKENS caps it
# regardless. Measured 2026-08-31 over a real scan: ~1,018 completion tokens per
# call. Rounded up, since under-quoting is the failure that costs the user money.
EST_OUTPUT_TOKENS_PER_CALL = 1100


class AIProviderError(Exception):
    """Raised when an AI provider call fails."""


# Transient-failure handling. A scan runs MAX_WORKERS files concurrently against
# one account, so rate limits are the expected case on any real repository, not
# an edge case. Without retries each 429 permanently loses a file: the user pays
# for the rest of the scan and gets a report with a hole in it.
# Findings for one file, as JSON. A response cut off at the limit is invalid
# JSON, so an under-sized budget shows up as a parse failure rather than as the
# budget problem it actually is - hence the explicit stop_reason check below.
MAX_ANALYSIS_TOKENS = 8192

MAX_ATTEMPTS = 4
BASE_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 30.0
RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
RETRYABLE_NAME_HINTS = (
    "ratelimit", "apiconnection", "apitimeout", "internalserver",
    "overloaded", "serviceunavailable",
)


def _retry_after_seconds(exc: Exception) -> Optional[float]:
    """Honour a server-supplied Retry-After header when there is one."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    try:
        value = headers.get("retry-after")
    except AttributeError:
        return None
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def is_retryable(exc: Exception) -> bool:
    """Whether a provider exception is worth trying again.

    Matched structurally (status code, then class name) rather than by
    importing each SDK's exception types, so this stays correct across SDK
    versions and works for providers whose exceptions we never import.
    """
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if isinstance(status, int) and status in RETRYABLE_STATUS:
        return True
    name = type(exc).__name__.lower()
    return any(hint in name for hint in RETRYABLE_NAME_HINTS)


def call_with_retries(operation, description: str, sleep=time.sleep):
    """Run a provider call, retrying transient failures with backoff + jitter.

    Jitter matters here specifically: the whole thread pool tends to get rate
    limited at the same instant, and un-jittered backoff would march every
    worker into the next retry simultaneously.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return operation()
        except Exception as e:  # noqa: BLE001 - re-raised below when terminal
            last_exc = e
            if attempt == MAX_ATTEMPTS or not is_retryable(e):
                break
            delay = _retry_after_seconds(e)
            if delay is None:
                delay = min(BASE_RETRY_DELAY * (2 ** (attempt - 1)), MAX_RETRY_DELAY)
                delay += random.uniform(0, delay / 2)
            sleep(delay)
    raise AIProviderError(
        f"{description} failed after {MAX_ATTEMPTS} attempt(s): {last_exc}"
    ) from last_exc


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
    DEFAULT_MODEL = "claude-opus-5"
    # USD per 1M tokens (input, output). Verified against Anthropic's published
    # rates 2026-08-24. These drive the pre-scan estimate and the --max-cost
    # guardrail, so a stale entry silently under-quotes the user; re-check when
    # bumping the default model. Unknown models fall back to DEFAULT_MODEL's
    # rate (see estimate_cost), which is why the default must stay listed here.
    PRICING = {
        "claude-opus-5": (5.0, 25.0),
        "claude-sonnet-5": (3.0, 15.0),
        "claude-haiku-4-5": (1.0, 5.0),
        "claude-opus-4-8": (5.0, 25.0),
        "claude-sonnet-4-6": (3.0, 15.0),
        # Retired models kept so existing configs still price correctly.
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
        # No temperature: the Anthropic SDK removed sampling parameters from
        # messages.create() in 1.0, and current models reject them with a 400.
        response = call_with_retries(
            lambda: self._client.messages.create(
                model=self.model,
                max_tokens=MAX_ANALYSIS_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            ),
            f"Claude analysis of {file_path}",
        )

        text = self._response_text(response, file_path)
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

    @staticmethod
    def _response_text(response, description: str) -> str:
        """Pull the text out of a Messages response, diagnosing truncation.

        Reported separately from a parse error because the fixes differ: a
        truncated response means the token budget was too small, not that the
        model ignored the JSON instruction.
        """
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise AIProviderError(
                f"Claude response for {description} hit the {MAX_ANALYSIS_TOKENS}-token "
                "output limit and was cut off mid-JSON. The file likely produced more "
                "findings than fit in one response."
            )
        blocks = getattr(response, "content", None) or []
        for block in blocks:
            text = getattr(block, "text", None)
            if text:
                return text
        raise AIProviderError(f"Claude returned no text content for {description}")

    def estimate_cost(self, input_tokens, output_tokens):
        in_rate, out_rate = self.PRICING.get(self.model, self.PRICING[self.DEFAULT_MODEL])
        return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate

    def generate_text(self, system_prompt, user_prompt):
        response = call_with_retries(
            lambda: self._client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ),
            "Claude text generation",
        )

        text = self._response_text(response, "generated document")
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
        response = call_with_retries(
            lambda: self._client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                max_completion_tokens=MAX_ANALYSIS_TOKENS,
                messages=[
                    {"role": "system", "content": "You are a compliance auditor. Respond only with JSON."},
                    {"role": "user", "content": prompt},
                ],
            ),
            f"OpenAI analysis of {file_path}",
        )

        choice = response.choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            raise AIProviderError(
                f"OpenAI response for {file_path} hit the {MAX_ANALYSIS_TOKENS}-token "
                "output limit and was cut off mid-JSON."
            )
        text = choice.message.content
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
        response = call_with_retries(
            lambda: self._client.chat.completions.create(
                model=self.model,
                max_completion_tokens=MAX_ANALYSIS_TOKENS,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            ),
            "OpenAI text generation",
        )

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

    # An agent CLI occasionally answers with prose or an empty turn instead of
    # the requested JSON - observed against both files of a two-file scan that
    # then succeeded unchanged on a re-run. One retry costs nothing here (the
    # user's plan already covers these calls) and turns a lost file into a
    # completed one.
    PARSE_ATTEMPTS = 2

    def analyze_code(self, regulation, clauses, file_path, code):
        prompt = build_prompt(regulation, clauses, file_path, code)
        last_error = None
        for attempt in range(self.PARSE_ATTEMPTS):
            text = self._run(prompt)
            try:
                parsed = extract_json_object(text)
                break
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
        else:
            raise AIProviderError(
                f"Could not parse {self.friendly_name} response as JSON after "
                f"{self.PARSE_ATTEMPTS} attempt(s): {last_error}"
            ) from last_error
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
