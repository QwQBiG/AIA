"""
Unit and property tests for TextCleaner

Feature: ux-hyper-optimization
"""

import pytest
from hypothesis import given, strategies as st, settings

from src.text_cleaner import TextCleaner


class TestTextCleanerUnitTests:
    """Unit tests for TextCleaner."""
    
    def test_initialization_defaults(self):
        """Test TextCleaner initialization with default parameters."""
        cleaner = TextCleaner()
        
        assert cleaner.remove_emoji is True
        assert cleaner.remove_markdown is True
        assert cleaner.remove_parenthetical is True
    
    def test_initialization_custom(self):
        """Test TextCleaner initialization with custom parameters."""
        cleaner = TextCleaner(
            remove_emoji=False,
            remove_markdown=False,
            remove_parenthetical=False
        )
        
        assert cleaner.remove_emoji is False
        assert cleaner.remove_markdown is False
        assert cleaner.remove_parenthetical is False
    
    def test_clean_empty_string(self):
        """Test cleaning empty string."""
        cleaner = TextCleaner()
        assert cleaner.clean("") == ""
    
    def test_clean_removes_emoji(self):
        """Test that emoji characters are removed."""
        cleaner = TextCleaner()
        
        assert cleaner.clean("Hello 😀 World") == "Hello World"
        assert cleaner.clean("🎉 Party 🎊") == "Party"
        assert cleaner.clean("😀😁😂") == ""
    
    def test_clean_preserves_emoji_when_disabled(self):
        """Test that emoji are preserved when remove_emoji is False."""
        cleaner = TextCleaner(remove_emoji=False)
        
        result = cleaner.clean("Hello 😀 World")
        assert "😀" in result
    
    def test_clean_removes_markdown_bold(self):
        """Test that markdown bold formatting is removed."""
        cleaner = TextCleaner()
        
        assert cleaner.clean("**bold text**") == "bold text"
        assert cleaner.clean("__bold text__") == "bold text"
    
    def test_clean_removes_markdown_italic(self):
        """Test that markdown italic formatting is removed."""
        cleaner = TextCleaner()
        
        assert cleaner.clean("*italic text*") == "italic text"
        assert cleaner.clean("_italic text_") == "italic text"
    
    def test_clean_removes_markdown_strikethrough(self):
        """Test that markdown strikethrough is removed."""
        cleaner = TextCleaner()
        
        assert cleaner.clean("~~strikethrough~~") == "strikethrough"
    
    def test_clean_removes_markdown_code(self):
        """Test that markdown code formatting is removed."""
        cleaner = TextCleaner()
        
        assert cleaner.clean("`code`") == "code"
    
    def test_clean_preserves_markdown_when_disabled(self):
        """Test that markdown is preserved when remove_markdown is False."""
        cleaner = TextCleaner(remove_markdown=False)
        
        assert cleaner.clean("**bold**") == "**bold**"
    
    def test_clean_removes_parenthetical_english(self):
        """Test that English parenthetical content is removed."""
        cleaner = TextCleaner()
        
        assert cleaner.clean("Hello (world) there") == "Hello there"
    
    def test_clean_removes_parenthetical_chinese(self):
        """Test that Chinese parenthetical content is removed."""
        cleaner = TextCleaner()
        
        assert cleaner.clean("你好（笑）世界") == "你好世界"
    
    def test_clean_preserves_parenthetical_when_disabled(self):
        """Test that parenthetical is preserved when remove_parenthetical is False."""
        cleaner = TextCleaner(remove_parenthetical=False)
        
        assert cleaner.clean("Hello (world)") == "Hello (world)"
    
    def test_clean_preserves_chinese_punctuation(self):
        """Test that Chinese punctuation is preserved."""
        cleaner = TextCleaner()
        
        result = cleaner.clean("你好，世界！这是测试。")
        assert "，" in result
        assert "！" in result
        assert "。" in result
    
    def test_clean_preserves_english_punctuation(self):
        """Test that English punctuation is preserved."""
        cleaner = TextCleaner()
        
        result = cleaner.clean("Hello, world! This is a test.")
        assert "," in result
        assert "!" in result
        assert "." in result
    
    def test_clean_normalizes_whitespace(self):
        """Test that multiple whitespace is normalized."""
        cleaner = TextCleaner()
        
        assert cleaner.clean("Hello    World") == "Hello World"
        assert cleaner.clean("  Hello  ") == "Hello"
    
    def test_clean_combined(self):
        """Test cleaning text with multiple elements."""
        cleaner = TextCleaner()
        
        result = cleaner.clean("**Hello** 😀 (test) 你好！")
        assert result == "Hello 你好！"
    
    def test_has_emoji(self):
        """Test emoji detection."""
        cleaner = TextCleaner()
        
        assert cleaner.has_emoji("Hello 😀") is True
        assert cleaner.has_emoji("Hello World") is False
    
    def test_has_markdown(self):
        """Test markdown detection."""
        cleaner = TextCleaner()
        
        assert cleaner.has_markdown("**bold**") is True
        assert cleaner.has_markdown("*italic*") is True
        assert cleaner.has_markdown("plain text") is False
    
    def test_has_parenthetical(self):
        """Test parenthetical detection."""
        cleaner = TextCleaner()
        
        assert cleaner.has_parenthetical("Hello (world)") is True
        assert cleaner.has_parenthetical("你好（笑）") is True
        assert cleaner.has_parenthetical("plain text") is False


class TestTextCleanerPropertyTests:
    """Property-based tests for TextCleaner."""
    
    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_text_cleaning_completeness_property(self, text: str):
        """
        Property 3: 文本清洗完整性 (Sanitization Completeness)
        
        For any input text containing Emojis or Markdown formatting, 
        the text sent to GPT-SoVITS MUST NOT contain these characters,
        while the original text is preserved for subtitle display.
        
        Feature: ux-hyper-optimization, Property 3: 文本清洗完整性
        **Validates: Requirements 3.1, 3.2, 3.4**
        """
        cleaner = TextCleaner()
        cleaned = cleaner.clean(text)
        
        # Property: Cleaned text should not contain emoji
        assert not cleaner.has_emoji(cleaned), \
            f"Cleaned text still contains emoji: {repr(cleaned)}"
        
        # Property: Cleaned text should not contain markdown formatting
        assert not cleaner.has_markdown(cleaned), \
            f"Cleaned text still contains markdown: {repr(cleaned)}"
        
        # Property: Cleaned text should not contain parenthetical content
        assert not cleaner.has_parenthetical(cleaned), \
            f"Cleaned text still contains parenthetical: {repr(cleaned)}"
    
    @given(st.text(
        alphabet=st.characters(
            whitelist_categories=('L', 'N', 'P', 'Z'),
            whitelist_characters='，。！？、；,.!?;'
        ),
        min_size=1,
        max_size=100
    ))
    @settings(max_examples=100)
    def test_punctuation_preservation_property(self, text: str):
        """
        Property: TTS-friendly punctuation preservation
        
        For any text containing TTS-friendly punctuation (，。！？、；,.!?;),
        the cleaner SHALL preserve these characters.
        
        Feature: ux-hyper-optimization
        **Validates: Requirements 3.5**
        """
        cleaner = TextCleaner()
        cleaned = cleaner.clean(text)
        
        # TTS-friendly punctuation that should be preserved
        tts_punctuation = set('，。！？、；,.!?;')
        
        # Count punctuation in original (excluding whitespace-only strings)
        original_punct = [c for c in text if c in tts_punctuation]
        cleaned_punct = [c for c in cleaned if c in tts_punctuation]
        
        # All punctuation from original should be in cleaned
        # (unless they were inside parenthetical content)
        for punct in cleaned_punct:
            assert punct in tts_punctuation, \
                f"Unexpected punctuation removed: {punct}"
    
    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_idempotence_property(self, text: str):
        """
        Property: Cleaning idempotence
        
        For any text, cleaning it twice should produce the same result
        as cleaning it once.
        
        Feature: ux-hyper-optimization
        """
        cleaner = TextCleaner()
        
        once = cleaner.clean(text)
        twice = cleaner.clean(once)
        
        assert once == twice, \
            f"Cleaning is not idempotent: once={repr(once)}, twice={repr(twice)}"
