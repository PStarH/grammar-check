"""HTML text extraction module."""
import re
from typing import List, Set
from bs4 import BeautifulSoup, NavigableString


class HTMLExtractor:
    """Extracts plain text from HTML while preserving context."""
    
    def __init__(self, skip_tags: List[str] = None):
        """Initialize the extractor.
        
        Args:
            skip_tags: List of tag names to skip during extraction
        """
        self.skip_tags: Set[str] = set(skip_tags or ["script", "style", "code", "pre"])
    
    def extract_text(self, html: str) -> str:
        """Extract visible text from HTML.
        
        Args:
            html: HTML string to parse
            
        Returns:
            Plain text extracted from HTML
        """
        if not html or not html.strip():
            return ""
        
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            # Fallback to html.parser if lxml fails
            soup = BeautifulSoup(html, "html.parser")
        
        # Remove skip tags
        for tag_name in self.skip_tags:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        
        # Extract text with normalization
        text = self._extract_text_recursive(soup)
        
        # Normalize whitespace
        text = self._normalize_whitespace(text)
        
        return text.strip()
    
    def _extract_text_recursive(self, element) -> str:
        """Recursively extract text from element.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            Extracted text
        """
        if isinstance(element, NavigableString):
            text = str(element)
            # Convert HTML entities
            text = text.replace('\xa0', ' ')  # &nbsp;
            text = text.replace('\u200b', '')  # zero-width space
            return text
        
        if element.name in self.skip_tags:
            return ""
        
        texts = []
        for child in element.children:
            child_text = self._extract_text_recursive(child)
            if child_text:
                texts.append(child_text)
        
        result = "".join(texts)
        
        # Add spacing for block elements
        if element.name in ["p", "div", "br", "hr", "li", "tr"]:
            result += " "
        elif element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            result += " "
        
        return result
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text.
        
        Args:
            text: Input text
            
        Returns:
            Text with normalized whitespace
        """
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        # Replace multiple newlines with single space
        text = re.sub(r'\n+', ' ', text)
        # Replace tabs with space
        text = re.sub(r'\t+', ' ', text)
        return text


def extract_plain_text(html: str, skip_tags: List[str] = None) -> str:
    """Convenience function to extract plain text from HTML.
    
    Args:
        html: HTML string to parse
        skip_tags: List of tag names to skip
        
    Returns:
        Plain text extracted from HTML
    """
    extractor = HTMLExtractor(skip_tags=skip_tags)
    return extractor.extract_text(html)
