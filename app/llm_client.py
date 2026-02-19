"""LLM client for grammar checking."""

import json
import logging
import os

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.schemas import GrammarIssue

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for LLM-based grammar checking."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        """Initialize the LLM client.

        Args:
            api_key: API key for LLM service
            base_url: Base URL for LLM service
            model: Model name to use
        """
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")

        if not self.api_key:
            raise ValueError("LLM_API_KEY must be set")

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def check_grammar(
        self,
        text: str,
        max_suggestions: int = 5,
        timeout: int = 30,
    ) -> list[GrammarIssue]:
        """Check grammar using LLM.

        Args:
            text: Text to check
            max_suggestions: Maximum suggestions per issue
            timeout: Request timeout in seconds

        Returns:
            List of grammar issues
        """
        if not text or not text.strip():
            return []

        prompt = self._build_prompt(text, max_suggestions)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert English grammar checker. "
                            "Return only valid JSON matching the schema provided."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=4000,
                timeout=timeout,
            )

            content = response.choices[0].message.content.strip()

            # Parse JSON response
            issues_data = self._parse_json_response(content)

            # Convert to Pydantic models
            issues = []
            for issue_data in issues_data:
                try:
                    issue = GrammarIssue(**issue_data)
                    issues.append(issue)
                except Exception as e:
                    logger.warning(f"Failed to parse issue: {e}, data: {issue_data}")
                    continue

            return issues

        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            raise

    def _build_prompt(self, text: str, max_suggestions: int) -> str:
        """Build prompt for LLM.

        Args:
            text: Text to check
            max_suggestions: Maximum suggestions per issue

        Returns:
            Prompt string
        """
        schema_example = {
            "type": "grammar|spelling|style",
            "severity": "error|warning|info",
            "message": "detailed explanation",
            "shortMessage": "brief label",
            "plainRange": {"start": 0, "end": 5},
            "context": "text snippet around error",
            "suggestions": ["suggestion1", "suggestion2"],
            "replacement": "best suggestion",
            "confidence": 0.9,
        }

        prompt = f"""Analyze the following English text for grammar, spelling, and style issues.

Text to analyze:
{text}

Return ONLY a JSON array of issues. Each issue must match this schema:
{json.dumps(schema_example, indent=2)}

Rules:
1. Return ONLY the JSON array, no other text or markdown
2. plainRange.start and plainRange.end are character offsets in the input text (0-indexed)
3. Provide up to {max_suggestions} suggestions per issue
4. Set replacement to the single best suggestion
5. Set confidence between 0.0 and 1.0
6. context should be ~20 characters around the error
7. If no issues found, return an empty array: []

JSON array of issues:"""

        return prompt

    def _parse_json_response(self, content: str) -> list[dict]:
        """Parse JSON response from LLM.

        Args:
            content: Response content

        Returns:
            List of issue dictionaries
        """
        # Try to extract JSON from markdown code blocks if present
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()

        # Remove any leading/trailing whitespace
        content = content.strip()

        # Try to parse JSON
        try:
            issues = json.loads(content)
            if not isinstance(issues, list):
                logger.warning(f"Expected list, got {type(issues)}")
                return []
            return issues
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}, content: {content[:200]}")
            # Try to find JSON array in the content
            try:
                # Look for [ ... ] pattern
                start = content.find("[")
                end = content.rfind("]")
                if start >= 0 and end > start:
                    json_str = content[start : end + 1]
                    issues = json.loads(json_str)
                    if isinstance(issues, list):
                        return issues
            except Exception:
                pass
            return []
