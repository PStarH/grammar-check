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
        self.max_input_length = int(os.getenv("MAX_INPUT_LENGTH", "120000"))
        self._basic_rule_checker_enabled = (
            os.getenv("BASIC_RULES_ENABLED", "true").lower() == "true"
        )

        self._basic_rules = [
            {
                "pattern": re.compile(r"\b[Ii]\s+has\b"),
                "type": "grammar",
                "severity": "error",
                "message": "Subject-verb agreement: use 'I have'.",
                "short": "Subject-verb agreement",
                "suggestions": ["I have"],
                "confidence": 0.82,
            },
            {
                "pattern": re.compile(r"\b[Tt]heir\s+going\b"),
                "type": "grammar",
                "severity": "error",
                "message": "Possessive pronoun used as contraction: use 'They're going'.",
                "short": "Wrong word form",
                "suggestions": ["They're going"],
                "confidence": 0.78,
            },
            {
                "pattern": re.compile(r"\b([Hh]e|[Ss]he|[Ii]t)\s+go\b"),
                "type": "grammar",
                "severity": "warning",
                "message": "Possible tense/agreement issue. Consider 'goes' or past tense form.",
                "short": "Possible agreement issue",
                "suggestions": ["goes", "went"],
                "confidence": 0.72,
            },
            {
                "pattern": re.compile(r"\b[Tt]hey\s+was\b"),
                "type": "grammar",
                "severity": "error",
                "message": "Plural subject should use 'were'.",
                "short": "Subject-verb agreement",
                "suggestions": ["they were"],
                "confidence": 0.8,
            },
            {
                "pattern": re.compile(r"\b([Aa])\s+([aeiouAEIOU]\w*)"),
                "type": "grammar",
                "severity": "warning",
                "message": "Use 'an' before words starting with vowel sounds.",
                "short": "Article usage",
                "suggestions": ["an"],
                "confidence": 0.65,
            },
            {
                "pattern": re.compile(r"\b([Aa]n)\s+([^aeiouAEIOU\W]\w*)"),
                "type": "grammar",
                "severity": "warning",
                "message": "Use 'a' before words starting with consonant sounds.",
                "short": "Article usage",
                "suggestions": ["a"],
                "confidence": 0.62,
            },
            {
                "pattern": re.compile(r"\bcould of\b"),
                "type": "grammar",
                "severity": "error",
                "message": "Use 'could have' instead of 'could of'.",
                "short": "Wrong phrase",
                "suggestions": ["could have"],
                "confidence": 0.86,
            },
            {
                "pattern": re.compile(r"\bshould of\b"),
                "type": "grammar",
                "severity": "error",
                "message": "Use 'should have' instead of 'should of'.",
                "short": "Wrong phrase",
                "suggestions": ["should have"],
                "confidence": 0.86,
            },
            {
                "pattern": re.compile(r"\bwould of\b"),
                "type": "grammar",
                "severity": "error",
                "message": "Use 'would have' instead of 'would of'.",
                "short": "Wrong phrase",
                "suggestions": ["would have"],
                "confidence": 0.86,
            },
        ]

        # Initialize LanguageTool
        self._language_tool = None
        self._language_tool_enabled = os.getenv("LANGUAGETOOL_ENABLED", "true").lower() == "true"
        if self._language_tool_enabled and _LANGUAGE_TOOL_AVAILABLE:
            try:
                languagetool_url = os.getenv("LANGUAGETOOL_URL")
                if languagetool_url:
                    self._language_tool = language_tool_python.LanguageTool(
                        'en-US', remote_server=languagetool_url
                    )
                else:
                    self._language_tool = language_tool_python.LanguageTool('en-US')
                logger.info("LanguageTool initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize LanguageTool: {e}")
        elif self._language_tool_enabled and not _LANGUAGE_TOOL_AVAILABLE:
            logger.info("language-tool-python not installed; LanguageTool checking disabled")


    def has_non_ai_engine(self) -> bool:
        """Return whether any non-AI engine is available."""
        return self._language_tool is not None or self._basic_rule_checker_enabled

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
                return [], self._get_non_ai_engine_name()
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
                    issues = await self._check_with_languagetool(text, max_suggestions)
                    engine = "fallback"
            elif mode == "fast":
                issues = await self._check_with_languagetool(text, max_suggestions)
                engine = self._get_non_ai_engine_name()
            else:
                issues = await self._check_with_llm(text, max_suggestions)

            return issues, engine

        except Exception as e:
            logger.error(f"Grammar check failed: {e}")
            # Return empty list on error
            return [], "fallback"

    def _get_non_ai_engine_name(self) -> str:
        """Return which non-AI engine would be used."""
        if self._language_tool is not None:
            return "languagetool"
        if self._basic_rule_checker_enabled:
            return "basic_rules"
        return "fallback"

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

    async def _check_with_languagetool(
        self, text: str, max_suggestions: int = 5
    ) -> list[GrammarIssue]:
        """Check text using LanguageTool.

        Args:
            text: Text to check
            max_suggestions: Maximum suggestions per issue

        Returns:
            List of grammar issues
        """
        if not self._language_tool:
            if not self._basic_rule_checker_enabled:
                logger.warning("LanguageTool and basic rules are disabled, returning empty list")
                return []
            logger.warning("LanguageTool not available, using built-in basic rules")
            return self._check_with_basic_rules(text, max_suggestions)
        
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
                    suggestions=[repl for repl in match.replacements[:max_suggestions]],
                    replacement=match.replacements[0] if match.replacements else None,
                    confidence=0.7  # LanguageTool doesn't provide confidence scores
                )
                issues.append(issue)
            
            return issues
            
        except Exception as e:
            logger.error(f"LanguageTool check failed: {e}")
            return []

    def _check_with_basic_rules(self, text: str, max_suggestions: int = 5) -> list[GrammarIssue]:
        """Check text using a small built-in rule set.

        This is a minimal fallback to keep the API usable when neither
        LanguageTool nor LLM is available.
        """
        safe_max_suggestions = max(1, min(max_suggestions, 100))

        issues: list[GrammarIssue] = []
        for rule in self._basic_rules:
            pattern = rule["pattern"]
            suggestions = rule["suggestions"]
            replacement = suggestions[0] if suggestions else None
            for match in pattern.finditer(text):
                context_start = max(0, match.start() - 20)
                context_end = min(len(text), match.end() + 20)
                issues.append(
                    GrammarIssue(
                        type=rule["type"],
                        severity=rule["severity"],
                        message=rule["message"],
                        shortMessage=rule["short"],
                        plainRange={"start": match.start(), "end": match.end()},
                        context=text[context_start:context_end],
                        suggestions=suggestions[:safe_max_suggestions],
                        replacement=replacement,
                        confidence=rule["confidence"],
                    )
                )

        issues.sort(key=lambda i: (i.plainRange.start, i.plainRange.end))
        return issues

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
