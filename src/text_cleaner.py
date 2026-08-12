"""
Text cleaner module for AI VTuber System.

This module provides text cleaning functionality to prepare text for TTS,
removing Emoji characters, Markdown formatting, and parenthetical content
while preserving TTS-friendly punctuation.

Feature: ux-hyper-optimization
Requirements: 3.1, 3.2, 3.3, 3.5
"""

import re
from typing import Optional


class TextCleaner:
    """
    文本清洗器 - 移除 Emoji、Markdown 和括号内容
    
    Cleans text for TTS processing by removing:
    - Emoji characters
    - Markdown formatting (preserving content)
    - Parenthetical content (optional)
    
    Preserves TTS-friendly punctuation: ，。！？、；
    """
    
    # Emoji 正则模式 - comprehensive Unicode emoji ranges
    # Carefully selected to avoid CJK character ranges
    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # geometric shapes extended
        "\U0001F800-\U0001F8FF"  # supplemental arrows-c
        "\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs
        "\U0001FA00-\U0001FA6F"  # chess symbols
        "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-a
        "\U00002702-\U000027B0"  # dingbats
        "\U00002600-\U000026FF"  # misc symbols (sun, cloud, etc.)
        "\U0000FE00-\U0000FE0F"  # variation selectors
        "\U0001F000-\U0001F02F"  # mahjong tiles
        "\U0001F0A0-\U0001F0FF"  # playing cards
        "\U0001F200-\U0001F251"  # enclosed ideographic supplement (safe range)
        "]+",
        flags=re.UNICODE
    )
    
    # Markdown 格式标记 - bold, italic, strikethrough
    # Matches **text**, *text*, __text__, _text_, ~~text~~
    MARKDOWN_BOLD_PATTERN = re.compile(r'\*\*([^*]+)\*\*')
    MARKDOWN_ITALIC_PATTERN = re.compile(r'\*([^*]+)\*')
    MARKDOWN_UNDERSCORE_BOLD_PATTERN = re.compile(r'__([^_]+)__')
    MARKDOWN_UNDERSCORE_ITALIC_PATTERN = re.compile(r'_([^_]+)_')
    MARKDOWN_STRIKETHROUGH_PATTERN = re.compile(r'~~([^~]+)~~')
    MARKDOWN_CODE_PATTERN = re.compile(r'`([^`]+)`')
    
    # 括号内容（可选移除）- Chinese and English parentheses
    PARENTHETICAL_PATTERN = re.compile(r'[（(][^）)]*[）)]')
    
    def __init__(
        self,
        remove_emoji: bool = True,
        remove_markdown: bool = True,
        remove_parenthetical: bool = True
    ):
        """
        Initialize TextCleaner with configuration options.
        
        Args:
            remove_emoji: Whether to remove emoji characters
            remove_markdown: Whether to remove markdown formatting
            remove_parenthetical: Whether to remove parenthetical content
        """
        self.remove_emoji = remove_emoji
        self.remove_markdown = remove_markdown
        self.remove_parenthetical = remove_parenthetical
    
    def clean(self, text: str) -> str:
        """
        清洗文本，移除不适合 TTS 的内容
        
        Cleans text by removing emoji, markdown formatting, and parenthetical
        content based on configuration. Preserves TTS-friendly punctuation.
        
        Args:
            text: 原始文本 (original text)
            
        Returns:
            清洗后的文本 (cleaned text)
            
        Requirements: 3.1, 3.2, 3.3, 3.5
        """
        if not text:
            return ""
        
        result = text
        
        # Remove Emojis (Requirement 3.1)
        if self.remove_emoji:
            result = self.EMOJI_PATTERN.sub('', result)
        
        # Remove Markdown formatting - keep content (Requirement 3.2)
        if self.remove_markdown:
            result = self._remove_markdown(result)
        
        # Remove parenthetical content if configured (Requirement 3.3)
        if self.remove_parenthetical:
            result = self.PARENTHETICAL_PATTERN.sub('', result)
        
        # Clean up extra whitespace while preserving single spaces
        result = self._normalize_whitespace(result)
        
        return result.strip()
    
    def _remove_markdown(self, text: str) -> str:
        """
        Remove markdown formatting while preserving content.
        
        Handles: **bold**, *italic*, __bold__, _italic_, ~~strikethrough~~, `code`
        
        Args:
            text: Text with potential markdown formatting
            
        Returns:
            Text with markdown markers removed, content preserved
        """
        result = text
        
        # Order matters: process double markers before single markers
        # Bold: **text** -> text
        result = self.MARKDOWN_BOLD_PATTERN.sub(r'\1', result)
        
        # Underscore bold: __text__ -> text
        result = self.MARKDOWN_UNDERSCORE_BOLD_PATTERN.sub(r'\1', result)
        
        # Strikethrough: ~~text~~ -> text
        result = self.MARKDOWN_STRIKETHROUGH_PATTERN.sub(r'\1', result)
        
        # Code: `text` -> text
        result = self.MARKDOWN_CODE_PATTERN.sub(r'\1', result)
        
        # Italic: *text* -> text (after bold to avoid conflicts)
        result = self.MARKDOWN_ITALIC_PATTERN.sub(r'\1', result)
        
        # Underscore italic: _text_ -> text (after bold to avoid conflicts)
        result = self.MARKDOWN_UNDERSCORE_ITALIC_PATTERN.sub(r'\1', result)
        
        return result
    
    def _normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace: collapse multiple spaces to single space.
        
        Preserves TTS-friendly punctuation: ，。！？、；,.!?;
        
        Args:
            text: Text with potential extra whitespace
            
        Returns:
            Text with normalized whitespace
        """
        # Replace multiple whitespace with single space
        return ' '.join(text.split())
    
    def has_emoji(self, text: str) -> bool:
        """
        Check if text contains emoji characters.
        
        Args:
            text: Text to check
            
        Returns:
            True if text contains emoji, False otherwise
        """
        return bool(self.EMOJI_PATTERN.search(text))
    
    def has_markdown(self, text: str) -> bool:
        """
        Check if text contains markdown formatting.
        
        Args:
            text: Text to check
            
        Returns:
            True if text contains markdown, False otherwise
        """
        patterns = [
            self.MARKDOWN_BOLD_PATTERN,
            self.MARKDOWN_ITALIC_PATTERN,
            self.MARKDOWN_UNDERSCORE_BOLD_PATTERN,
            self.MARKDOWN_UNDERSCORE_ITALIC_PATTERN,
            self.MARKDOWN_STRIKETHROUGH_PATTERN,
            self.MARKDOWN_CODE_PATTERN,
        ]
        return any(p.search(text) for p in patterns)
    
    def has_parenthetical(self, text: str) -> bool:
        """
        Check if text contains parenthetical content.
        
        Args:
            text: Text to check
            
        Returns:
            True if text contains parenthetical content, False otherwise
        """
        return bool(self.PARENTHETICAL_PATTERN.search(text))
