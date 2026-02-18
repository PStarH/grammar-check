"""Tests for HTML text extraction."""

from app.html_extract import HTMLExtractor, extract_plain_text


def test_extract_simple_text():
    """Test extraction of simple text."""
    html = "<p>Hello world</p>"
    result = extract_plain_text(html)
    assert result == "Hello world"


def test_extract_nested_tags():
    """Test extraction from nested tags."""
    html = "<div><p>Hello <strong>world</strong></p></div>"
    result = extract_plain_text(html)
    assert "Hello" in result
    assert "world" in result


def test_skip_script_tags():
    """Test that script tags are skipped."""
    html = "<p>Hello</p><script>alert('test')</script><p>world</p>"
    result = extract_plain_text(html)
    assert "Hello" in result
    assert "world" in result
    assert "alert" not in result
    assert "test" not in result


def test_skip_style_tags():
    """Test that style tags are skipped."""
    html = "<p>Hello</p><style>.test { color: red; }</style><p>world</p>"
    result = extract_plain_text(html)
    assert "Hello" in result
    assert "world" in result
    assert "color" not in result


def test_skip_custom_tags():
    """Test skipping custom tags."""
    html = "<p>Show this</p><custom>Hide this</custom><p>Show that</p>"
    extractor = HTMLExtractor(skip_tags=["custom"])
    result = extractor.extract_text(html)
    assert "Show this" in result
    assert "Show that" in result
    assert "Hide this" not in result


def test_normalize_nbsp():
    """Test that &nbsp; is converted to space."""
    html = "<p>Hello&nbsp;world</p>"
    result = extract_plain_text(html)
    assert "Hello world" in result


def test_multiple_spaces():
    """Test that multiple spaces are normalized."""
    html = "<p>Hello    world</p>"
    result = extract_plain_text(html)
    assert "Hello world" in result


def test_empty_html():
    """Test extraction from empty HTML."""
    result = extract_plain_text("")
    assert result == ""


def test_whitespace_only():
    """Test extraction from whitespace-only HTML."""
    result = extract_plain_text("   \n  \t  ")
    assert result == ""


def test_block_elements_spacing():
    """Test that block elements add spacing."""
    html = "<p>First paragraph</p><p>Second paragraph</p>"
    result = extract_plain_text(html)
    assert "First paragraph" in result
    assert "Second paragraph" in result
    # Should have space between them
    assert result.count("paragraph") == 2


def test_complex_html():
    """Test extraction from complex HTML."""
    html = """
    <html>
        <head>
            <title>Test Page</title>
            <style>.test { color: red; }</style>
        </head>
        <body>
            <h1>Main Title</h1>
            <p>This is a <strong>test</strong> paragraph with <em>emphasis</em>.</p>
            <script>console.log('test');</script>
            <div>
                <ul>
                    <li>Item 1</li>
                    <li>Item 2</li>
                </ul>
            </div>
        </body>
    </html>
    """
    result = extract_plain_text(html)
    assert "Test Page" in result
    assert "Main Title" in result
    assert "test" in result
    assert "paragraph" in result
    assert "emphasis" in result
    assert "Item 1" in result
    assert "Item 2" in result
    assert "console.log" not in result
    assert "color: red" not in result


def test_malformed_html():
    """Test handling of malformed HTML."""
    html = "<p>Unclosed paragraph<div>Mixed nesting</p></div>"
    result = extract_plain_text(html)
    assert "Unclosed paragraph" in result
    assert "Mixed nesting" in result
