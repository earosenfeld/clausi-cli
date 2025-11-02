"""
Claude Code CLI Provider - Local execution of claude commands

This module provides direct integration with Claude Code CLI,
executing claude commands locally in the authenticated terminal
instead of via backend subprocess (which fails authentication).
"""

import subprocess
import json
import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ClaudeCodeProvider:
    """Provider for executing code analysis using local Claude Code CLI."""

    def __init__(self):
        """Initialize Claude Code provider."""
        self.model = "claude-sonnet-4-5-20250929"
        logger.info("Initialized ClaudeCodeProvider (local claude CLI)")

    def analyze_code(
        self,
        code: str,
        regulation: str,
        file_path: str,
        clauses: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Analyze code using local claude CLI.

        Args:
            code: Source code to analyze
            regulation: Regulation name (e.g., "EU AI Act")
            file_path: Path to the file being analyzed
            clauses: Optional list of specific clauses to check

        Returns:
            Dict containing findings and metadata
        """
        # Build the analysis prompt
        prompt = self._build_prompt(code, regulation, file_path, clauses)

        try:
            # Call claude CLI locally (we're in authenticated session)
            logger.info(f"Calling local claude CLI for {file_path}...")

            # Escape prompt for shell
            escaped_prompt = prompt.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')

            # Run claude command
            result = subprocess.run(
                f'claude --print --dangerously-skip-permissions "{escaped_prompt}"',
                capture_output=True,
                text=True,
                timeout=120,
                shell=True
            )

            if result.returncode != 0:
                logger.error(f"Claude CLI failed: {result.stderr or result.stdout}")
                raise RuntimeError(f"Claude CLI failed: {result.stderr or result.stdout[:200]}")

            response_text = result.stdout.strip()

            # Extract JSON from response (claude might wrap it in markdown)
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
            elif not response_text.startswith('{'):
                # Try to find JSON block anywhere in response
                json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)

            # Parse the response
            findings_data = json.loads(response_text)

            logger.info(f"Claude CLI analysis complete for {file_path}: {len(findings_data.get('findings', []))} findings")

            return {
                "findings": findings_data.get("findings", []),
                "metadata": {
                    "model": self.model,
                    "provider": "claude-cli-local",
                    "file_path": file_path
                }
            }

        except subprocess.TimeoutExpired:
            logger.error(f"Claude CLI timeout for {file_path}")
            raise RuntimeError("Claude Code CLI timed out")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude CLI response: {e}")
            logger.error(f"Response: {response_text[:500]}")
            raise RuntimeError("Claude CLI returned invalid JSON")
        except Exception as e:
            logger.error(f"Claude CLI error: {str(e)}")
            raise

    def _build_prompt(
        self,
        code: str,
        regulation: str,
        file_path: str,
        clauses: Optional[List[Dict]] = None
    ) -> str:
        """Build the analysis prompt for Claude."""

        prompt_parts = [
            f"You are a compliance auditor analyzing code for {regulation} compliance.",
            "",
            "Your task is to identify potential compliance violations in the provided code.",
            ""
        ]

        # Add clause-specific instructions if provided
        if clauses:
            prompt_parts.append("Focus on these specific clauses:")
            for clause in clauses:
                clause_id = clause.get("id", "")
                clause_text = clause.get("text", "")
                prompt_parts.append(f"- {clause_id}: {clause_text}")
            prompt_parts.append("")

        # Add file context
        prompt_parts.append(f"File: {file_path}")
        prompt_parts.append("")

        # Add the code
        prompt_parts.extend([
            "Code to analyze:",
            "```",
            code,
            "```",
            "",
            "Respond with a JSON object in this exact format:",
            "{",
            '  "findings": [',
            '    {',
            '      "clause_id": "EUAIA-3.1",',
            '      "clause_text": "Brief clause description",',
            '      "violation": "Description of the violation",',
            '      "severity": "high|medium|low",',
            '      "confidence": 0.95,',
            '      "line_start": 10,',
            '      "line_end": 15,',
            '      "code_snippet": "relevant code excerpt",',
            '      "recommendation": "How to fix this",',
            '      "auto_fixable": true,',
            '      "evidence": "Why this is a violation"',
            '    }',
            '  ]',
            '}',
            "",
            "Rules:",
            "- Only include actual violations, not potential issues",
            "- Confidence score: 0.0 (uncertain) to 1.0 (certain)",
            "- Severity: high (legal risk), medium (best practice), low (minor)",
            "- auto_fixable: true only if fix is simple and safe",
            "- Provide line numbers if identifiable",
            "- Be specific and actionable in recommendations"
        ])

        return "\n".join(prompt_parts)
