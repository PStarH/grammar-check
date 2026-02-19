from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser

BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "div",
    "dl",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "section",
    "table",
    "tr",
    "ul",
}


@dataclass
class HtmlExtractionResult:
    plain_text: str


class VisibleTextHTMLParser(HTMLParser):
    def __init__(self, skip_tags: set[str], br_as_newline: bool = True) -> None:
        super().__init__(convert_charrefs=False)
        self.skip_tags = {tag.lower() for tag in skip_tags}
        self.br_as_newline = br_as_newline
        self._parts: list[str] = []
        self._tag_stack: list[str] = []
        self._skip_depth = 0

    def _append_text(self, text: str) -> None:
        if not text:
            return
        text = unescape(text).replace("\xa0", " ")
        self._parts.append(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        low = tag.lower()
        self._tag_stack.append(low)
        if low in self.skip_tags:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if low == "br":
            self._parts.append("\n" if self.br_as_newline else " ")
        elif low in BLOCK_TAGS and self._parts and not self._parts[-1].endswith("\n"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        low = tag.lower()
        if self._tag_stack:
            self._tag_stack.pop()
        if low in self.skip_tags and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if low in BLOCK_TAGS and self._parts and not self._parts[-1].endswith("\n"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._append_text(data)


def _normalize_whitespace(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    compact = "\n".join(line for line in lines)
    # collapse excessive newlines
    while "\n\n\n" in compact:
        compact = compact.replace("\n\n\n", "\n\n")
    return compact.strip()


def extract_visible_text(
    html: str,
    skip_tags: list[str] | None = None,
    br_as_newline: bool = True,
) -> HtmlExtractionResult:
    parser = VisibleTextHTMLParser(
        skip_tags=set(skip_tags or ["script", "style", "code", "pre"]), br_as_newline=br_as_newline
    )
    parser.feed(html)
    parser.close()
    return HtmlExtractionResult(plain_text=_normalize_whitespace("".join(parser._parts)))
