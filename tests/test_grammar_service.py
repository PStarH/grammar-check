"""Tests for grammar service."""

import pytest

from app.grammar_service import GrammarService


def test_split_into_sentences():
    """Test sentence splitting."""
    service = GrammarService()

    text = "First sentence. Second sentence! Third sentence? Fourth."
    sentences = service._split_into_sentences(text)

    assert len(sentences) == 4
    assert "First sentence." in sentences[0]
    assert "Second sentence!" in sentences[1]
    assert "Third sentence?" in sentences[2]
    assert "Fourth." in sentences[3]


def test_split_into_chunks_short_text():
    """Test chunking of short text."""
    service = GrammarService()

    text = "This is a short text."
    chunks = service._split_into_chunks(text)

    assert len(chunks) == 1
    assert chunks[0] == text


def test_split_into_chunks_long_text():
    """Test chunking of long text."""
    service = GrammarService()
    service.max_chunk_size = 50  # Set small for testing

    # Create text with multiple sentences
    text = "First sentence here. " * 10  # 210 characters
    chunks = service._split_into_chunks(text)

    # Should be split into multiple chunks
    assert len(chunks) > 1

    # Each chunk should be <= max_chunk_size
    for chunk in chunks:
        assert (
            len(chunk) <= service.max_chunk_size + 30
        )  # Allow some overflow for sentence boundaries


def test_split_into_chunks_very_long_sentence():
    """Test chunking when single sentence exceeds max size."""
    service = GrammarService()
    service.max_chunk_size = 50

    # Create a very long sentence without proper punctuation
    text = "word " * 100  # 500 characters, no sentence breaks
    chunks = service._split_into_chunks(text)

    # Should be split even without sentence boundaries
    assert len(chunks) > 1


@pytest.mark.asyncio
async def test_check_text_empty():
    """Test checking empty text."""
    service = GrammarService()

    issues, engine = await service.check_text("")

    assert issues == []
    assert engine == "llm"


@pytest.mark.asyncio
async def test_check_text_empty_hybrid_engine():
    """Empty hybrid checks should return schema-supported engine value."""
    service = GrammarService()
    issues, engine = await service.check_text("", mode="hybrid")
    assert issues == []
    assert engine == "hybrid"


class _AlwaysFailLLMClient:
    async def check_grammar(self, text: str, max_suggestions: int = 5):
        _ = (text, max_suggestions)
        raise TimeoutError("LLM timeout")


@pytest.mark.asyncio
async def test_check_with_llm_raises_when_all_chunks_fail():
    """When all chunks fail, _check_with_llm should raise to enable fallback."""
    service = GrammarService(llm_client=_AlwaysFailLLMClient())
    service.max_chunk_size = 5

    with pytest.raises(RuntimeError, match="All LLM chunk checks failed"):
        await service._check_with_llm("This input forces chunking and failures.")


@pytest.mark.asyncio
async def test_hybrid_mode_falls_back_when_all_chunks_fail():
    """Hybrid mode should report fallback when LLM fails on all chunks."""
    service = GrammarService(llm_client=_AlwaysFailLLMClient())
    service.max_chunk_size = 5

    issues, engine = await service.check_text("This input forces fallback.", mode="hybrid")

    assert issues == []
    assert engine == "fallback"


@pytest.mark.asyncio
async def test_check_text_no_llm_client():
    """Test checking text without LLM client."""
    service = GrammarService(llm_client=None)

    with pytest.raises(ValueError):
        await service._check_with_llm("Some text")


def test_sentence_splitting_edge_cases():
    """Test edge cases in sentence splitting."""
    service = GrammarService()

    # Single sentence without ending punctuation
    text = "Just one sentence"
    sentences = service._split_into_sentences(text)
    assert len(sentences) == 1

    # Multiple punctuation marks
    text = "What?! Really... Yes."
    sentences = service._split_into_sentences(text)
    assert len(sentences) >= 2

    # No punctuation
    text = "No punctuation here"
    sentences = service._split_into_sentences(text)
    assert len(sentences) == 1


@pytest.mark.asyncio
async def test_check_text_with_languagetool():
    """Test checking text with LanguageTool."""
    service = GrammarService(llm_client=None)
    
    # Only test if LanguageTool is available
    if service._language_tool:
        text = "I has a mistake here."
        issues, engine = await service.check_text(text, mode="fast", use_ai=False)
        
        # LanguageTool should be used and might find issues
        assert engine == "languagetool"
        # We can't guarantee issues found as it depends on LanguageTool availability
        assert isinstance(issues, list)


@pytest.mark.asyncio
async def test_check_text_with_use_ai_false():
    """Test that useAI=False forces LanguageTool only."""
    service = GrammarService(llm_client=None)
    
    text = "This is a test."
    issues, engine = await service.check_text(text, mode="best_quality", use_ai=False)
    
    # Should use LanguageTool even with best_quality mode when useAI=False
    assert engine == "languagetool"
    assert isinstance(issues, list)


@pytest.mark.asyncio
async def test_languagetool_mapping_functions():
    """Test LanguageTool type and severity mapping."""
    service = GrammarService()
    
    # Create a mock match object with all required attributes
    class MockMatch:
        def __init__(self):
            self.category = "GRAMMAR"
            self.ruleId = "GRAMMAR_ERROR"
            self.issueType = "misspelling"
            self.offset = 0
            self.errorLength = 5
            self.message = "Test error message"
            self.replacements = ["correction1", "correction2"]
    
    match = MockMatch()
    
    # Test type mapping
    issue_type = service._map_languagetool_type(match)
    assert issue_type in ["grammar", "spelling", "style"]
    
    # Test severity mapping
    severity = service._map_languagetool_severity(match)
    assert severity in ["error", "warning", "info"]
    
    # Test with missing attributes
    class IncompleteMatch:
        pass
    
    incomplete_match = IncompleteMatch()
    issue_type = service._map_languagetool_type(incomplete_match)
    assert issue_type == "grammar"  # Should default to grammar
    
    severity = service._map_languagetool_severity(incomplete_match)
    assert severity == "warning"  # Should default to warning
