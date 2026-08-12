"""
TextProcessor Component

Process streaming ASR results and determine sentence boundaries.
Handles text normalization, confidence filtering, and clarification requests.
"""

import re
from typing import List
import logging

from .logging_config import get_component_logger

logger = get_component_logger("text_processor")

class TextProcessor:
    """Process streaming ASR results and manage text accumulation."""
    
    def __init__(self, confidence_threshold: float = 0.7):
        """
        Initialize text processor.
        
        Args:
            confidence_threshold: Minimum confidence for accepting transcription
        """
        self.confidence_threshold = confidence_threshold
        self.text_buffer = ""
        self.partial_text = ""
        
        # Filler words to filter (Chinese and English)
        self.filler_words = {
            "嗯", "呃", "那个", "这个", "就是", "然后", "uh", "um", "er", "like", "you know"
        }
        
        # Sentence boundary patterns
        self.sentence_endings = re.compile(r'[。！？.!?]+')
        
        logger.info(f"TextProcessor initialized with confidence_threshold={confidence_threshold}")
    
    def process_partial_text(self, text: str, confidence: float) -> None:
        """Process partial transcription result."""
        logger.debug(f"Processing partial text: '{text}' (confidence: {confidence})")
        
        if confidence < self.confidence_threshold:
            logger.debug("Low confidence text ignored")
            return
        
        # Clean and normalize text
        cleaned_text = self._normalize_text(text)
        self.partial_text = cleaned_text
        
        logger.debug(f"Partial text updated: '{cleaned_text}'")
    
    def detect_sentence_boundary(self, text: str) -> bool:
        """Detect if text represents a complete sentence."""
        if not text.strip():
            return False
        
        # Check for sentence ending punctuation
        has_ending = bool(self.sentence_endings.search(text))
        
        # Check for minimum length (avoid single character responses)
        has_min_length = len(text.strip()) >= 3
        
        is_complete = has_ending and has_min_length
        logger.debug(f"Sentence boundary check: '{text}' -> {is_complete}")
        
        return is_complete
    
    def get_accumulated_text(self) -> str:
        """Get current accumulated text buffer."""
        return self.text_buffer
    
    def clear_buffer(self) -> None:
        """Clear text accumulation buffer."""
        logger.debug("Clearing text buffer")
        self.text_buffer = ""
        self.partial_text = ""
    
    def filter_filler_words(self, text: str) -> str:
        """Remove filler words and sounds from transcribed text."""
        words = text.split()
        filtered_words = [word for word in words if word not in self.filler_words]
        filtered_text = " ".join(filtered_words)
        
        if filtered_text != text:
            logger.debug(f"Filtered filler words: '{text}' -> '{filtered_text}'")
        
        return filtered_text
    
    def request_clarification(self, low_confidence_text: str) -> str:
        """Generate clarification request for low-confidence transcriptions."""
        clarification_templates = [
            "抱歉，我没有听清楚，你能再说一遍吗？",
            "Sorry, I didn't catch that. Could you repeat?",
            "我听到了一些声音，但不太确定你说的是什么。",
            "Could you speak a bit clearer? I'm having trouble understanding."
        ]
        
        # Simple selection based on detected language
        if any(ord(char) > 127 for char in low_confidence_text):
            # Contains non-ASCII characters, likely Chinese
            return clarification_templates[0]
        else:
            # ASCII only, likely English
            return clarification_templates[1]
    
    def _normalize_text(self, text: str) -> str:
        """Clean and normalize transcribed text."""
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', text.strip())
        
        # Filter filler words
        normalized = self.filter_filler_words(normalized)
        
        return normalized
    
    def add_to_buffer(self, text: str) -> None:
        """Add text to the accumulation buffer."""
        if text.strip():
            if self.text_buffer:
                self.text_buffer += " " + text
            else:
                self.text_buffer = text
            logger.debug(f"Added to buffer: '{text}' -> Total: '{self.text_buffer}'")