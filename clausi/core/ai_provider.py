"""AI provider abstraction for local, BYOK compliance scanning.

Calls Anthropic/OpenAI directly with the user's own API key - no Clausi
backend involved. Prompt/response contract matches the original hosted
service so cached results and report generation stay compatible.
"""

import json
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
            response = self._client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            raise AIProviderError(f"Claude API error: {e}") from e

        text = response.content[0].text
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, IndexError) as e:
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
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
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


def get_ai_provider(provider_name: str, api_key: str, model: Optional[str] = None) -> AIProvider:
    """Instantiate a BYOK provider. provider_name is 'claude' or 'openai'."""
    if provider_name == "claude":
        return ClaudeProvider(api_key, model)
    if provider_name == "openai":
        return OpenAIProvider(api_key, model)
    raise ValueError(f"Unsupported AI provider: {provider_name}")
