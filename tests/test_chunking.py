from app.chunking import chunk_plain_text


def test_chunk_boundaries_preserve_offsets() -> None:
    text = "A short sentence. " * 100
    chunks = chunk_plain_text(text, max_chunk_chars=120)
    rebuilt = "".join(c.text for c in chunks)
    assert rebuilt.replace("\n\n", "") in text
    assert chunks[0].start == 0
    assert chunks[-1].end <= len(text)
