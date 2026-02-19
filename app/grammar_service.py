"""Grammar checking service with chunking and engine orchestration."""

import logging
import re

from app.llm_client import LLMClient
from app.schemas import GrammarIssue

logger = logging.getLogger(__name__)


class GrammarService:
    """Service for orchestrating grammar checking."""

    def __init__(self, llm_client: LLMClient | None = None):
        """Initialize the service.

        Args:
            llm_client: LLM client instance
        """
        self.llm_client = llm_client
        self.max_chunk_size = 2000  # characters per chunk
        self.max_input_length = 50000  # maximum input length

    async def check_text(
        self,
        text: str,
        mode: str = "best_quality",
        max_suggestions: int = 5,
    ) -> tuple[list[GrammarIssue], str]:
        """Check text for grammar issues.

        Args:
            text: Plain text to check
            mode: Checking mode (best_quality, hybrid, fast)
            max_suggestions: Maximum suggestions per issue

        Returns:
            Tuple of (issues list, engine used)
        """
        if not text or not text.strip():
            if mode == "fast":
                return [], "languagetool"
            if mode == "hybrid":
                return [], "hybrid"
            return [], "llm"

        # Enforce max length
        if len(text) > self.max_input_length:
            text = text[: self.max_input_length]
            logger.warning(f"Text truncated to {self.max_input_length} characters")

        engine = "llm"

        try:
            if mode == "best_quality":
                issues = await self._check_with_llm(text, max_suggestions)
            elif mode == "hybrid":
                # Try LLM first, fallback to LanguageTool if needed
                try:
                    issues = await self._check_with_llm(text, max_suggestions)
                    engine = "hybrid"
                except Exception as e:
                    logger.warning(f"LLM check failed, falling back to LanguageTool: {e}")
                    issues = await self._check_with_languagetool(text)
                    engine = "fallback"
            elif mode == "fast":
                issues = await self._check_with_languagetool(text)
                engine = "languagetool"
            else:
                issues = await self._check_with_llm(text, max_suggestions)

            return issues, engine

        except Exception as e:
            logger.error(f"Grammar check failed: {e}")
            # Return empty list on error
            return [], "fallback"

    async def _check_with_llm(
        self,
        text: str,
        max_suggestions: int = 5,
    ) -> list[GrammarIssue]:
        """Check text using LLM with chunking.

        Args:
            text: Text to check
            max_suggestions: Maximum suggestions per issue

        Returns:
            List of grammar issues
        """
        if not self.llm_client:
            raise ValueError("LLM client not configured")

        # Split into chunks if needed
        chunks = self._split_into_chunks(text)

        all_issues = []
        offset = 0
        failures = 0
        last_error = None

        for chunk in chunks:
            try:
                chunk_issues = await self.llm_client.check_grammar(
                    chunk,
                    max_suggestions=max_suggestions,
                )

                # Adjust offsets for this chunk
                for issue in chunk_issues:
                    issue.plainRange.start += offset
                    issue.plainRange.end += offset

                all_issues.extend(chunk_issues)

            except Exception as e:
                logger.error(f"Failed to check chunk at offset {offset}: {e}")
                failures += 1
                last_error = e

            offset += len(chunk)

        if failures == len(chunks):
            raise RuntimeError("All LLM chunk checks failed") from last_error

        return all_issues

    async def _check_with_languagetool(self, text: str) -> list[GrammarIssue]:
        """Check text using LanguageTool.

        Args:
            text: Text to check

        Returns:
            List of grammar issues
        """
        # This is a placeholder for LanguageTool integration
        # In a full implementation, this would use language-tool-python
        logger.info("LanguageTool check not implemented, returning empty list")
        return []

    def _split_into_chunks(self, text: str) -> list[str]:
        """Split text into chunks for processing.

        Args:
            text: Text to split

        Returns:
            List of text chunks
        """
        if len(text) <= self.max_chunk_size:
            return [text]

        chunks = []
        sentences = self._split_into_sentences(text)

        current_chunk = ""
        for sentence in sentences:
            # If single sentence is too long, split it
            if len(sentence) > self.max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                # Split long sentence by chunks
                for i in range(0, len(sentence), self.max_chunk_size):
                    chunks.append(sentence[i : i + self.max_chunk_size])
            elif len(current_chunk) + len(sentence) <= self.max_chunk_size:
                current_chunk += sentence
            else:
                chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        # Simple sentence splitting (can be improved with better NLP)
        # Split on period, question mark, exclamation mark followed by space or end
        pattern = r"([.!?]+[\s]+|[.!?]+$)"
        parts = re.split(pattern, text)

        sentences = []
        current = ""
        for part in parts:
            current += part
            if re.match(pattern, part):
                sentences.append(current)
                current = ""

        if current:
            sentences.append(current)

        return sentences
