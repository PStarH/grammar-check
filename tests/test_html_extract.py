from app.html_extract import extract_visible_text


def test_extract_visible_text_skips_tags_and_entities() -> None:
    html = "<p>Tom&nbsp;is here</p><code>ignore me</code><p>Line<br>two</p>"
    result = extract_visible_text(html, ["code", "script", "style", "pre"])
    assert result.plain_text == "Tom is here\nLine\ntwo"


def test_extract_offset_deterministic() -> None:
    html = "<div><p>Hello <strong>wrld</strong>.</p></div>"
    result = extract_visible_text(html)
    idx = result.plain_text.index("wrld")
    assert result.plain_text[idx : idx + 4] == "wrld"
