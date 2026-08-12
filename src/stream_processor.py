"""
Stream Processor for AI VTuber System

This module provides the StreamProcessor class that sits between the LLM and TTS components,
responsible for:
1. Extracting emotion tags from the beginning of streamed responses
2. Buffering incoming tokens and detecting sentence boundaries
3. Triggering callbacks when complete sentences are detected

The StreamProcessor enables real-time sentence-by-sentence TTS processing,
reducing perceived latency by allowing audio generation to start before
the full response is received.
"""

import re
import logging
from typing import Callable, Optional, Set


class StreamProcessor:
    """
    Stream text processor for sentence chunking and emotion extraction.
    
    This class acts as middleware between the LLM streaming output and the TTS pipeline.
    It buffers incoming tokens, detects sentence boundaries based on punctuation,
    and extracts emotion tags from the beginning of the response.
    
    Attributes:
        SENTENCE_DELIMITERS: Set of punctuation characters that mark sentence boundaries
        AGGRESSIVE_DELIMITERS: Set of punctuation characters for aggressive splitting (commas, etc.)
        EMOTION_PATTERN: Regex pattern for extracting [emotion] tags
        MIN_SENTENCE_LENGTH: Minimum character count before a sentence can be emitted
    """
    
    # Chinese and English sentence-ending punctuation
    SENTENCE_DELIMITERS: Set[str] = {'。', '！', '？', '；', '.', '!', '?', ';'}
    
    # Aggressive splitting delimiters (commas, pause markers)
    AGGRESSIVE_DELIMITERS: Set[str] = {'，', '、', ','}
    
    # Pattern to match emotion tags at the start of text: [emotion]
    EMOTION_PATTERN = re.compile(r'^\s*\[(\w+)\]\s*')
    
    # Valid emotion tags - expanded to include common expressions
    VALID_EMOTIONS: Set[str] = {
        'neutral', 'happy', 'angry', 'sad', 'surprised',
        'giggles', 'laughing', 'smiling', 'excited', 'cheerful',
        'worried', 'confused', 'thinking', 'shy', 'embarrassed'
    }
    
    # Minimum fragment length to prevent tiny audio clips
    MIN_FRAGMENT_LENGTH: int = 4
    
    def __init__(
        self, 
        on_sentence: Callable[[str], None],
        min_sentence_length: int = 5,
        aggressive_split: bool = False,
        aggressive_min_length: int = 10
    ):
        """
        Initialize the StreamProcessor.
        
        Args:
            on_sentence: Callback function invoked when a complete sentence is detected.
                        The callback receives the sentence text as its argument.
            min_sentence_length: Minimum number of characters required before a sentence
                               can be emitted. This prevents very short fragments from
                               being sent to TTS. Default is 5.
            aggressive_split: Whether to enable aggressive splitting on commas.
                            When enabled, text will be split on commas when buffer
                            exceeds aggressive_min_length. Default is False.
            aggressive_min_length: Minimum buffer length before aggressive splitting
                                  is applied. Default is 10.
        """
        self.on_sentence = on_sentence
        self.min_sentence_length = min_sentence_length
        self.aggressive_split = aggressive_split
        self.aggressive_min_length = aggressive_min_length
        self.text_buffer: str = ""
        self.emotion: Optional[str] = None
        self.emotion_extracted: bool = False
        self.logger = logging.getLogger(__name__)
    
    def feed(self, token: str) -> Optional[str]:
        """
        Feed a token into the processor and check for complete sentences.
        
        This method:
        1. Appends the token to the internal buffer
        2. On first call, attempts to extract an emotion tag from the buffer
        3. Checks if the buffer contains a sentence-ending delimiter
        4. If a complete sentence is found (and meets minimum length), 
           triggers the on_sentence callback and clears that portion of the buffer
        
        Args:
            token: A text token received from the LLM stream
            
        Returns:
            The detected emotion tag (only on first detection), or None
        """
        if not token:
            return None
        
        self.text_buffer += token
        detected_emotion = None
        
        # Try to extract emotion tag if not already done
        if not self.emotion_extracted:
            emotion, remaining_text = self.extract_emotion(self.text_buffer)
            if emotion:
                self.emotion = emotion
                self.emotion_extracted = True
                self.text_buffer = remaining_text
                detected_emotion = emotion
                self.logger.debug(f"Extracted emotion tag: [{emotion}]")
            elif len(self.text_buffer) > 30:
                # No emotion tag found after 30 chars, assume no tag present
                self.emotion_extracted = True
                self.logger.debug("No emotion tag found, proceeding without emotion")
        
        # Check for sentence boundaries and emit complete sentences
        self._process_sentences()
        
        return detected_emotion
    
    def _process_sentences(self) -> None:
        """
        Process the buffer to find and emit complete sentences.
        
        Scans the buffer for sentence-ending delimiters. When found,
        extracts the sentence (if it meets minimum length requirements)
        and invokes the on_sentence callback.
        
        When aggressive_split is enabled, also splits on commas when
        the buffer exceeds aggressive_min_length. Fragments shorter than
        MIN_FRAGMENT_LENGTH are merged with the next segment.
        """
        while True:
            # Find the first sentence delimiter in the buffer
            delimiter_pos = -1
            for i, char in enumerate(self.text_buffer):
                if char in self.SENTENCE_DELIMITERS:
                    delimiter_pos = i
                    break
            
            # If no standard delimiter found, try aggressive splitting
            if delimiter_pos == -1 and self.aggressive_split:
                if len(self.text_buffer) >= self.aggressive_min_length:
                    for i, char in enumerate(self.text_buffer):
                        if char in self.AGGRESSIVE_DELIMITERS and i >= self.aggressive_min_length:
                            # Check if the resulting fragment would be too short
                            potential_sentence = self.text_buffer[:i + 1].strip()
                            if len(potential_sentence) >= self.MIN_FRAGMENT_LENGTH:
                                delimiter_pos = i
                                self.logger.debug(f"Aggressive split at position {i}")
                                break
            
            if delimiter_pos == -1:
                # No delimiter found, wait for more tokens
                break
            
            # Extract the sentence including the delimiter
            sentence = self.text_buffer[:delimiter_pos + 1].strip()
            remaining = self.text_buffer[delimiter_pos + 1:]
            
            # Check if sentence meets minimum length requirement
            if len(sentence) >= self.min_sentence_length:
                # Additional check: avoid fragments shorter than MIN_FRAGMENT_LENGTH
                if len(sentence) < self.MIN_FRAGMENT_LENGTH:
                    # Fragment too short, keep in buffer and wait for more
                    self.logger.debug(f"Fragment too short ({len(sentence)} chars), waiting for more")
                    break
                
                self.logger.debug(f"Emitting sentence: {sentence[:50]}...")
                self.on_sentence(sentence)
                self.text_buffer = remaining.lstrip()
            else:
                # Sentence too short, keep it in buffer and wait for more
                # But only if there's more content coming (remaining is not empty)
                if remaining.strip():
                    # There's more content, so this short fragment should be combined
                    # with the next sentence
                    break
                else:
                    # No more content after this short sentence, emit it anyway
                    self.logger.debug(f"Emitting short sentence: {sentence}")
                    self.on_sentence(sentence)
                    self.text_buffer = remaining.lstrip()
                    break
    
    def flush(self) -> None:
        """
        Force output of any remaining text in the buffer.
        
        This should be called when the stream ends to ensure any
        remaining text (that didn't end with a delimiter) is still
        sent to the TTS pipeline.
        """
        remaining_text = self.text_buffer.strip()
        if remaining_text:
            self.logger.debug(f"Flushing remaining text: {remaining_text[:50]}...")
            self.on_sentence(remaining_text)
            self.text_buffer = ""
    
    def extract_emotion(self, text: str) -> tuple[Optional[str], str]:
        """
        Extract emotion tag from the beginning of text.
        
        Looks for a pattern like [happy], [sad], etc. at the start of the text.
        Only valid emotion tags are recognized.
        
        Args:
            text: Text that may start with an [emotion] tag
            
        Returns:
            A tuple of (emotion, remaining_text) where:
            - emotion is the extracted emotion string (e.g., 'happy') or None if not found
            - remaining_text is the text after the emotion tag, or the original text if no tag
        """
        match = self.EMOTION_PATTERN.match(text)
        if match:
            emotion = match.group(1).lower()
            if emotion in self.VALID_EMOTIONS:
                remaining_text = text[match.end():]
                return emotion, remaining_text
            else:
                self.logger.warning(f"Invalid emotion tag '{emotion}' found, ignoring")
                return None, text
        return None, text
    
    def reset(self) -> None:
        """
        Reset the processor state for processing a new response.
        
        Clears the buffer and resets emotion extraction state.
        """
        self.text_buffer = ""
        self.emotion = None
        self.emotion_extracted = False
        self.logger.debug("StreamProcessor reset")
    
    def get_current_emotion(self) -> Optional[str]:
        """
        Get the currently detected emotion.
        
        Returns:
            The emotion tag if one was detected, or None
        """
        return self.emotion
    
    def get_buffer_content(self) -> str:
        """
        Get the current content of the text buffer.
        
        Useful for debugging or displaying partial text.
        
        Returns:
            The current buffer content
        """
        return self.text_buffer
