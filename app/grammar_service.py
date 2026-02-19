"""Grammar checking service with chunking and engine orchestration."""

import asyncio
import logging
import os
import re

from app.llm_client import LLMClient
from app.schemas import GrammarIssue

logger = logging.getLogger(__name__)

try:
    import language_tool_python
    _LANGUAGE_TOOL_AVAILABLE = True
except ImportError:
    language_tool_python = None  # type: ignore[assignment]
    _LANGUAGE_TOOL_AVAILABLE = False


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
        
        # Initialize LanguageTool
        self._language_tool = None
        self._language_tool_enabled = os.getenv("LANGUAGETOOL_ENABLED", "true").lower() == "true"
        if self._language_tool_enabled and _LANGUAGE_TOOL_AVAILABLE:
            try:
                languagetool_url = os.getenv("LANGUAGETOOL_URL")
                if languagetool_url:
                    self._language_tool = language_tool_python.LanguageTool('en-US', remote_server=languagetool_url)
                else:
                    self._language_tool = language_tool_python.LanguageTool('en-US')
                logger.info("LanguageTool initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize LanguageTool: {e}")
        elif self._language_tool_enabled and not _LANGUAGE_TOOL_AVAILABLE:
            logger.info("language-tool-python not installed; LanguageTool checking disabled")

    async def check_text(
        self,
        text: str,
        mode: str = "best_quality",
        max_suggestions: int = 5,
        use_ai: bool = True,
    ) -> tuple[list[GrammarIssue], str]:
        """Check text for grammar issues.

        Args:
            text: Plain text to check
            mode: Checking mode (best_quality, hybrid, fast)
            max_suggestions: Maximum suggestions per issue
            use_ai: Whether to use AI (LLM) for checking

        Returns:
            Tuple of (issues list, engine used)
        """
        if not text or not text.strip():
            if mode == "fast" or not use_ai:
                return [], "languagetool"
            if mode == "hybrid":
                return [], "hybrid"
            return [], "llm"

        # Enforce max length
        if len(text) > self.max_input_length:
            text = text[: self.max_input_length]
            logger.warning(f"Text truncated to {self.max_input_length} characters")

        # If useAI is False, force fast mode (LanguageTool only)
        if not use_ai:
            mode = "fast"

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
        any_success = False
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
                any_success = True

            except Exception as e:
                logger.error(f"Failed to check chunk at offset {offset}: {e}")
                last_error = e

            offset += len(chunk)

        if not any_success:
            raise RuntimeError("All LLM chunk checks failed") from last_error

        return all_issues

    async def _check_with_languagetool(self, text: str) -> list[GrammarIssue]:
        """Check text using LanguageTool.

        Args:
            text: Text to check

        Returns:
            List of grammar issues
        """
        if not self._language_tool:
            logger.warning("LanguageTool not available, returning empty list")
            return []
        
        try:
            # LanguageTool is synchronous; run in a thread to avoid blocking the event loop
            matches = await asyncio.to_thread(self._language_tool.check, text)
            
            issues = []
            for match in matches:
                # Map LanguageTool match to GrammarIssue
                issue_type = self._map_languagetool_type(match)
                severity = self._map_languagetool_severity(match)
                
                # Get context around the error
                context_start = max(0, match.offset - 10)
                context_end = min(len(text), match.offset + match.errorLength + 10)
                context = text[context_start:context_end]
                
                issue = GrammarIssue(
                    type=issue_type,
                    severity=severity,
                    message=match.message,
                    shortMessage=match.ruleId or "Grammar Issue",
                    plainRange={
                        "start": match.offset,
                        "end": match.offset + match.errorLength
                    },
                    context=context,
                    suggestions=[repl for repl in match.replacements[:5]],
                    replacement=match.replacements[0] if match.replacements else None,
                    confidence=0.7  # LanguageTool doesn't provide confidence scores
                )
                issues.append(issue)
            
            return issues
            
        except Exception as e:
            logger.error(f"LanguageTool check failed: {e}")
            return []
    
    def _map_languagetool_type(self, match) -> str:
        """Map LanguageTool issue type to our type.
        
        Args:
            match: LanguageTool match object
            
        Returns:
            Issue type: "grammar", "spelling", or "style"
        """
        try:
            category = match.category.lower() if match.category else ""
            rule_id = (match.ruleId or "").lower()
            
            if "spell" in category or "spell" in rule_id or "typo" in category:
                return "spelling"
            elif "style" in category or "style" in rule_id:
                return "style"
            else:
                return "grammar"
        except AttributeError:
            return "grammar"
    
    def _map_languagetool_severity(self, match) -> str:
        """Map LanguageTool issue type to severity.
        
        Args:
            match: LanguageTool match object
            
        Returns:
            Severity: "error", "warning", or "info"
        """
        try:
            issue_type = match.issueType.lower() if match.issueType else ""
            
            if "misspelling" in issue_type or "confusion" in issue_type:
                return "error"
            elif "style" in issue_type or "hint" in issue_type:
                return "info"
            else:
                return "warning"
        except AttributeError:
            return "warning"

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
