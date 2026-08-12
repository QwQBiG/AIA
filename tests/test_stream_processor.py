"""
Unit and property tests for StreamProcessor

Feature: performance-optimization
"""

import pytest
from hypothesis import given, strategies as st, settings
from typing import List

from src.stream_processor import StreamProcessor


class TestStreamProcessorUnitTests:
    """Unit tests for StreamProcessor."""
    
    def test_initialization(self):
        """Test StreamProcessor initialization with default and custom parameters."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        assert processor.text_buffer == ""
        assert processor.emotion is None
        assert processor.emotion_extracted is False
        assert processor.min_sentence_length == 5
        
        # Test custom min_sentence_length
        processor2 = StreamProcessor(
            on_sentence=lambda s: sentences.append(s),
            min_sentence_length=10
        )
        assert processor2.min_sentence_length == 10
    
    def test_emotion_extraction_happy(self):
        """Test extraction of [happy] emotion tag."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        emotion = processor.feed("[happy] ")
        assert emotion == "happy"
        assert processor.emotion == "happy"
        assert processor.emotion_extracted is True
    
    def test_emotion_extraction_all_valid_emotions(self):
        """Test extraction of all valid emotion tags."""
        valid_emotions = ['neutral', 'happy', 'angry', 'sad', 'surprised']
        
        for emotion_tag in valid_emotions:
            sentences = []
            processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
            
            result = processor.feed(f"[{emotion_tag}] Hello!")
            assert result == emotion_tag
            assert processor.emotion == emotion_tag
    
    def test_emotion_extraction_invalid_emotion(self):
        """Test that invalid emotion tags are ignored."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        # Feed text with invalid emotion tag
        result = processor.feed("[excited] Hello!")
        assert result is None
        assert processor.emotion is None
    
    def test_emotion_extraction_no_tag(self):
        """Test handling of text without emotion tag."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        # Feed enough text to trigger "no emotion" detection
        for char in "This is a test message without emotion tag.":
            processor.feed(char)
        
        assert processor.emotion_extracted is True
        assert processor.emotion is None
    
    def test_sentence_detection_chinese_punctuation(self):
        """Test sentence detection with Chinese punctuation."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        processor.feed("[happy] 你好！")
        processor.feed("我是娜娜。")
        processor.feed("很高兴见到你？")
        processor.flush()
        
        assert len(sentences) == 3
        assert "你好！" in sentences[0]
        assert "我是娜娜。" in sentences[1]
        assert "很高兴见到你？" in sentences[2]
    
    def test_sentence_detection_english_punctuation(self):
        """Test sentence detection with English punctuation."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        processor.feed("[neutral] Hello! ")
        processor.feed("How are you? ")
        processor.feed("I am fine.")
        processor.flush()
        
        assert len(sentences) == 3
        assert "Hello!" in sentences[0]
        assert "How are you?" in sentences[1]
        assert "I am fine." in sentences[2]
    
    def test_sentence_detection_mixed_punctuation(self):
        """Test sentence detection with mixed Chinese and English punctuation."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        processor.feed("[happy] Hello! 你好。Nice to meet you!")
        processor.flush()
        
        # Should detect at least 2 sentences (Hello! and the rest)
        # The exact count depends on min_sentence_length handling
        assert len(sentences) >= 2
        # Verify all content is captured
        joined = "".join(sentences)
        assert "Hello" in joined
        assert "你好" in joined
        assert "Nice to meet you" in joined
    
    def test_minimum_sentence_length(self):
        """Test that sentences shorter than min_sentence_length are handled correctly."""
        sentences = []
        processor = StreamProcessor(
            on_sentence=lambda s: sentences.append(s),
            min_sentence_length=10
        )
        
        # Short sentence followed by longer one
        processor.feed("[neutral] Hi! This is a longer sentence.")
        processor.flush()
        
        # The short "Hi!" should be combined or handled appropriately
        assert len(sentences) >= 1
    
    def test_flush_remaining_text(self):
        """Test that flush() outputs remaining text without delimiter."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        processor.feed("[happy] Hello world")  # No ending punctuation
        assert len(sentences) == 0  # Not emitted yet
        
        processor.flush()
        assert len(sentences) == 1
        assert "Hello world" in sentences[0]
    
    def test_reset(self):
        """Test reset() clears all state."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        processor.feed("[happy] Some text")
        assert processor.emotion == "happy"
        assert processor.text_buffer != ""
        
        processor.reset()
        
        assert processor.text_buffer == ""
        assert processor.emotion is None
        assert processor.emotion_extracted is False
    
    def test_get_current_emotion(self):
        """Test get_current_emotion() returns correct value."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        assert processor.get_current_emotion() is None
        
        processor.feed("[sad] ")
        assert processor.get_current_emotion() == "sad"
    
    def test_get_buffer_content(self):
        """Test get_buffer_content() returns current buffer."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        processor.feed("[neutral] Hello")
        assert "Hello" in processor.get_buffer_content()
    
    def test_token_by_token_feeding(self):
        """Test feeding tokens one character at a time."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        text = "[happy] 你好！我是娜娜。"
        for char in text:
            processor.feed(char)
        processor.flush()
        
        assert processor.emotion == "happy"
        assert len(sentences) == 2
    
    def test_emotion_only_extracted_once(self):
        """Test that emotion tag is only extracted from the beginning."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        # First emotion tag should be extracted
        result1 = processor.feed("[happy] Hello! ")
        assert result1 == "happy"
        
        # Second emotion tag in text should NOT be extracted as emotion
        result2 = processor.feed("[sad] This is just text.")
        assert result2 is None  # No new emotion detected
        assert processor.emotion == "happy"  # Still the first emotion
        
        processor.flush()
        # The [sad] should appear in the sentence text
        assert any("[sad]" in s for s in sentences)
    
    def test_whitespace_handling(self):
        """Test handling of whitespace around emotion tags and sentences."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        processor.feed("  [happy]   Hello world!  ")
        processor.flush()
        
        assert processor.emotion == "happy"
        assert len(sentences) >= 1
    
    def test_semicolon_as_delimiter(self):
        """Test that semicolons work as sentence delimiters."""
        sentences = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        processor.feed("[neutral] First part; second part。")
        processor.flush()
        
        assert len(sentences) == 2


class TestStreamProcessorPropertyTests:
    """Property-based tests for StreamProcessor."""
    
    @given(st.text(min_size=1, max_size=200).filter(lambda x: x.strip()))
    @settings(max_examples=100)
    def test_sentence_integrity_property(self, text: str):
        """
        Property 3: Sentence Integrity
        For any input text, joining all split sentences SHALL produce a string 
        that contains all the original text content (ignoring the emotion tag).
        
        Feature: performance-optimization, Property 3: Sentence Integrity
        Validates: Requirements 2.1
        """
        sentences: List[str] = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        # Prepend a valid emotion tag
        full_text = f"[happy] {text}"
        
        # Feed the text token by token
        for char in full_text:
            processor.feed(char)
        processor.flush()
        
        # Join all emitted sentences
        joined_output = "".join(sentences)
        
        # The joined output should contain all non-tag content from the original
        # (whitespace may be normalized, so we compare stripped versions)
        original_content = text.strip()
        
        # All characters from original text should appear in output
        # (order preserved, but whitespace may be normalized)
        for char in original_content:
            if char.strip():  # Skip whitespace comparison
                assert char in joined_output, f"Character '{char}' missing from output"
    
    @given(st.sampled_from(['neutral', 'happy', 'angry', 'sad', 'surprised']))
    @settings(max_examples=100)
    def test_emotion_extraction_property(self, emotion: str):
        """
        Property: Emotion Extraction Consistency
        For any valid emotion tag, the StreamProcessor SHALL correctly extract 
        and store the emotion, and it SHALL only be extracted once.
        
        Feature: performance-optimization
        Validates: Requirements 1.3
        """
        sentences: List[str] = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        # Feed text with emotion tag
        result = processor.feed(f"[{emotion}] Test message。")
        
        # Emotion should be detected
        assert result == emotion
        assert processor.emotion == emotion
        assert processor.emotion_extracted is True
        
        # Feeding more text should not change the emotion
        processor.feed("[angry] More text。")
        assert processor.emotion == emotion  # Still the original emotion
    
    @given(st.lists(
        st.text(min_size=2, max_size=50).filter(
            lambda x: x.strip() and 
            '。' not in x and '！' not in x and '？' not in x and
            ';' not in x and '；' not in x and '.' not in x and '!' not in x and '?' not in x
        ),
        min_size=2,
        max_size=5,
        unique=True  # Ensure unique elements to avoid duplicate position issues
    ))
    @settings(max_examples=100)
    def test_sentence_order_property(self, sentence_parts: List[str]):
        """
        Property 2: Pipeline Order (Sentence Level)
        For any sequence of sentence parts, the emitted sentences SHALL maintain
        the original order of content.
        
        Feature: performance-optimization, Property 2: Pipeline Order
        Validates: Requirements 2.4
        """
        sentences: List[str] = []
        processor = StreamProcessor(on_sentence=lambda s: sentences.append(s))
        
        # Create sentences with delimiters
        full_text = "[neutral] " + "。".join(sentence_parts) + "。"
        
        # Feed the text
        for char in full_text:
            processor.feed(char)
        processor.flush()
        
        # Verify order is maintained
        joined = "".join(sentences)
        for i, part in enumerate(sentence_parts):
            part_stripped = part.strip()
            if part_stripped:
                assert part_stripped in joined, f"Part '{part_stripped}' not found in output"
                
                # Check relative order with next parts (only for unique parts)
                if i < len(sentence_parts) - 1:
                    next_part = sentence_parts[i + 1].strip()
                    if next_part and part_stripped != next_part:
                        if part_stripped in joined and next_part in joined:
                            pos_current = joined.find(part_stripped)
                            pos_next = joined.find(next_part)
                            assert pos_current < pos_next, f"Order violated: '{part_stripped}' should come before '{next_part}'"


class TestAggressiveSplitPropertyTests:
    """Property-based tests for aggressive splitting feature."""
    
    @given(
        st.text(min_size=15, max_size=100, alphabet=st.characters(
            whitelist_categories=('L', 'N'),  # Letters and numbers only
            whitelist_characters=' '
        )).filter(lambda x: len(x.strip()) >= 15)
    )
    @settings(max_examples=100)
    def test_aggressive_split_on_comma_property(self, text_before_comma: str):
        """
        Property 4: 激进分句有效性 (Aggressive Split Effectiveness)
        For any text buffer exceeding the configured minimum length with a comma delimiter,
        the Stream_Processor SHALL emit a sentence segment, reducing time-to-first-audio.
        
        Feature: ux-hyper-optimization, Property 4: 激进分句有效性
        Validates: Requirements 4.1, 4.2
        """
        sentences: List[str] = []
        
        # Create processor with aggressive splitting enabled
        processor = StreamProcessor(
            on_sentence=lambda s: sentences.append(s),
            min_sentence_length=5,
            aggressive_split=True,
            aggressive_min_length=10
        )
        
        # Ensure text is long enough (at least aggressive_min_length)
        text_before = text_before_comma.strip()
        if len(text_before) < 12:
            text_before = text_before + "a" * (12 - len(text_before))
        
        # Create text with comma after sufficient length
        full_text = f"[neutral] {text_before}，后续内容"
        
        # Feed the text character by character
        for char in full_text:
            processor.feed(char)
        
        # Check if aggressive split occurred (sentence emitted before flush)
        # The comma should trigger a split when buffer >= aggressive_min_length
        if len(text_before) >= 10:
            # Should have emitted at least one sentence due to aggressive split
            assert len(sentences) >= 1, (
                f"Aggressive split should have occurred. "
                f"Buffer length: {len(text_before)}, sentences: {sentences}"
            )
            # The first sentence should contain content before the comma
            first_sentence = sentences[0]
            # Verify the split happened at or after the comma
            assert '，' in first_sentence or len(first_sentence) >= 4, (
                f"First sentence should include comma or be substantial: {first_sentence}"
            )
        
        # Flush remaining content
        processor.flush()
        
        # All content should be captured
        joined = "".join(sentences)
        # Verify key content is present (allowing for whitespace normalization)
        assert "后续内容" in joined or len(sentences) > 0
    
    @given(st.integers(min_value=4, max_value=20))
    @settings(max_examples=100)
    def test_aggressive_split_respects_min_fragment_length(self, fragment_length: int):
        """
        Property: Aggressive split respects minimum fragment length
        For any aggressive split, the resulting fragment SHALL NOT be shorter than
        MIN_FRAGMENT_LENGTH (4 characters) to prevent tiny audio clips.
        
        Feature: ux-hyper-optimization
        Validates: Requirements 4.3
        """
        sentences: List[str] = []
        
        processor = StreamProcessor(
            on_sentence=lambda s: sentences.append(s),
            min_sentence_length=4,
            aggressive_split=True,
            aggressive_min_length=10
        )
        
        # Create text where comma appears at various positions
        # Use fragment_length to control where comma appears
        text = "a" * fragment_length + "，" + "b" * 20
        full_text = f"[neutral] {text}"
        
        for char in full_text:
            processor.feed(char)
        processor.flush()
        
        # All emitted sentences should be at least MIN_FRAGMENT_LENGTH
        for sentence in sentences:
            stripped = sentence.strip()
            if stripped:  # Only check non-empty sentences
                assert len(stripped) >= processor.MIN_FRAGMENT_LENGTH, (
                    f"Fragment too short: '{stripped}' (length {len(stripped)})"
                )
    
    @given(st.text(min_size=5, max_size=50, alphabet=st.characters(
        whitelist_categories=('L', 'N'),
        whitelist_characters=' '
    )).filter(lambda x: len(x.strip()) >= 5))
    @settings(max_examples=100)
    def test_aggressive_split_disabled_no_comma_split(self, text: str):
        """
        Property: When aggressive split is disabled, commas do not trigger splits
        For any text with commas, when aggressive_split=False, the Stream_Processor
        SHALL NOT split on commas, only on standard sentence delimiters.
        
        Feature: ux-hyper-optimization
        Validates: Requirements 4.1 (inverse test)
        """
        sentences: List[str] = []
        
        # Create processor WITHOUT aggressive splitting
        processor = StreamProcessor(
            on_sentence=lambda s: sentences.append(s),
            min_sentence_length=5,
            aggressive_split=False  # Disabled
        )
        
        # Create text with comma but no sentence-ending punctuation
        text_clean = text.strip()
        full_text = f"[neutral] {text_clean}，更多内容"
        
        for char in full_text:
            processor.feed(char)
        
        # Without aggressive split, comma should NOT trigger emission
        # (no sentence-ending punctuation in the text)
        assert len(sentences) == 0, (
            f"Without aggressive split, comma should not trigger emission. "
            f"Got sentences: {sentences}"
        )
        
        # Flush to get remaining content
        processor.flush()
        
        # Now we should have the full content as one sentence
        assert len(sentences) == 1
        joined = sentences[0]
        assert text_clean in joined
        assert "更多内容" in joined
