"""
Entity Extractor implementation for the AI VTuber RAG system.

This module provides Named Entity Recognition (NER) capabilities for extracting
entities from conversation text, including user names, preferences, and factual
information using pattern matching and keyword detection.
"""

import re
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Set, Tuple
from dataclasses import dataclass

from .data_models import Entity, EntityType, PreferenceType, Fact


@dataclass
class ExtractionPattern:
    """Pattern definition for entity extraction."""
    pattern: str
    entity_type: EntityType
    confidence: float
    category: Optional[str] = None


class EntityExtractor:
    """
    Named Entity Recognition (NER) component for extracting entities from conversation text.
    
    Implements basic NER functionality using pattern matching and keyword detection
    to extract user names, preferences (likes/dislikes), and factual information
    from conversation text as specified in Requirements 3.1, 3.2, 3.3, 3.4.
    """
    
    def __init__(self):
        """Initialize the EntityExtractor with pattern definitions and keyword lists."""
        self.logger = logging.getLogger(__name__)
        
        # ============================================================================
        # USER NAME EXTRACTION PATTERNS
        # ============================================================================
        
        # Patterns for extracting user names from conversation
        self.name_patterns = [
            # Direct name statements - improved to handle more variations
            r"(?:my name is|i'm|i am|call me)\s+([A-Z][a-z]+)(?:\s|$|[.,!?])",
            r"(?:name's|name is)\s+([A-Z][a-z]+)(?:\s|$|[.,!?])",
            r"i'm called\s+([A-Z][a-z]+)(?:\s|$|[.,!?])",  # Separate pattern for "I'm called"
            
            # Introductions
            r"(?:hi,?\s+i'm|hello,?\s+i'm|hey,?\s+i'm)\s+([A-Z][a-z]+)(?:\s|$|[.,!?])",
            
            # Possessive forms - only when clearly indicating user's own preference
            r"([A-Z][a-z]+)'s\s+(?:favorite|preference|choice)",
            
            # Third person references - more restrictive to avoid false positives
            r"(?:this is|meet)\s+([A-Z][a-z]+)(?:\s|$|[.,!?])"
        ]
        
        # Negative patterns - contexts where names should NOT be extracted
        self.name_negative_patterns = [
            r"my name is not\s+",           # "My name is not important"
            r"i wish my name was",          # Hypothetical
            r"if my name was",              # Hypothetical
            r"you can call me\s+(?:dr|mr|mrs|ms|prof|professor)\.",  # Titles
            r"my friends call me",          # Indirect references
            r"i am known as",               # Indirect references
        ]
        
        # Patterns that should be excluded from name extraction (but don't block the whole sentence)
        self.name_exclusion_patterns = [
            r"(?:my\s+)?dog'?s?\s+name\s+is\s+([A-Z][a-z]+)",    # "My dog's name is Buddy"
            r"(?:the\s+)?character'?s?\s+name\s+is\s+([A-Z][a-z]+)",  # "The character's name is Romeo"
            r"(?:my\s+)?cat'?s?\s+name\s+is\s+([A-Z][a-z]+)",    # "My cat's name is Whiskers"
            r"(?:my\s+)?pet'?s?\s+name\s+is\s+([A-Z][a-z]+)",    # "My pet's name is Max"
        ]
        
        # Common names to help with validation (expanded list)
        self.common_names = {
            'alex', 'sam', 'jordan', 'taylor', 'casey', 'riley', 'avery', 'quinn',
            'john', 'jane', 'mike', 'sarah', 'david', 'lisa', 'chris', 'anna',
            'james', 'mary', 'robert', 'patricia', 'michael', 'jennifer', 'william',
            'elizabeth', 'daniel', 'maria', 'matthew', 'susan', 'anthony', 'margaret',
            'tom', 'tim', 'jim', 'kim', 'ben', 'jen', 'dan', 'ann', 'joe', 'amy',
            'bob', 'rob', 'ron', 'don', 'jon', 'ken', 'len', 'ray', 'jay', 'may',
            'ace', 'max', 'rex', 'leo', 'eli', 'ava', 'eva', 'ivy', 'zoe', 'mia',
            'noah', 'liam', 'emma', 'olivia', 'sophia', 'jackson', 'aiden', 'lucas',
            'mason', 'ethan', 'alexander', 'henry', 'jacob', 'logan', 'luke', 'owen',
            'sebastian', 'jack', 'carter', 'wyatt', 'julian', 'grayson', 'matthew',
            'isabella', 'charlotte', 'amelia', 'harper', 'evelyn', 'abigail', 'emily',
            'elizabeth', 'mila', 'ella', 'avery', 'sofia', 'camila', 'aria', 'scarlett'
        }
        
        # ============================================================================
        # PREFERENCE EXTRACTION PATTERNS AND KEYWORDS
        # ============================================================================
        
        # Enhanced positive preference indicators (LIKE) with more comprehensive patterns
        self.like_patterns = [
            # Direct positive statements
            r"i (?:love|adore|absolutely love|really love|truly love)\s+([^.,!?]+?)(?:\.|!|,|$)",
            r"i (?:enjoy|like|really like|quite like|prefer|am fond of|am into|am crazy about|am obsessed with)\s+([^.,!?]+?)(?:\.|!|,|$)",
            r"i'm (?:a fan of|crazy about|passionate about|obsessed with|really into)\s+([^.,!?]+?)(?:\.|!|,|$)",
            
            # Superlative and strong positive expressions
            r"([^.,!?]+?)\s+(?:is|are)\s+(?:amazing|awesome|incredible|fantastic|wonderful|perfect|the best|outstanding|excellent|brilliant|marvelous)(?:\.|!|,|$)",
            r"([^.,!?]+?)\s+(?:rocks|rules|is incredible|is perfect|is the best|is amazing|is fantastic)(?:\.|!|,|$)",
            
            # Favorite patterns - enhanced
            r"my (?:favorite|favourite)\s+([^.,!?]+?)(?:\s+is\s+([^.,!?]+?))?(?:\.|!|,|$)",
            r"([^.,!?]+?)\s+is\s+my (?:favorite|favourite)(?:\.|!|,|$)",
            
            # Comparative preferences
            r"i prefer\s+([^.,!?]+?)\s+(?:over|to|rather than)(?:\.|!|,|$)",
            r"([^.,!?]+?)\s+is\s+(?:better than|superior to|way better than)(?:\.|!|,|$)",
            
            # Emotional responses
            r"([^.,!?]+?)\s+makes me (?:happy|excited|joyful|thrilled)(?:\.|!|,|$)",
            r"i get (?:excited|thrilled|happy) about\s+([^.,!?]+?)(?:\.|!|,|$)"
        ]
        
        # Enhanced negative preference indicators (DISLIKE) with more comprehensive patterns
        self.dislike_patterns = [
            # Direct negative statements
            r"i (?:hate|despise|loathe|detest|absolutely hate|really hate|truly hate)\s+([^.,!?]+?)(?:\.|!|,|$)",
            r"i (?:dislike|can't stand|cannot stand|don't like|do not like|am not fond of|am not into)\s+([^.,!?]+?)(?:\.|!|,|$)",
            r"i'm (?:not a fan of|not into|sick of|tired of|fed up with)\s+([^.,!?]+?)(?:\.|!|,|$)",
            
            # Strong negative expressions
            r"([^.,!?]+?)\s+(?:is|are)\s+(?:terrible|awful|horrible|disgusting|revolting|repulsive|the worst|gross|nasty|dreadful)(?:\.|!|,|$)",
            r"([^.,!?]+?)\s+(?:sucks|is terrible|is awful|is disgusting|is horrible|is the worst|is gross)(?:\.|!|,|$)",
            
            # Emotional negative responses
            r"([^.,!?]+?)\s+makes me (?:sick|angry|upset|frustrated|annoyed)(?:\.|!|,|$)",
            r"i get (?:angry|upset|frustrated|annoyed) (?:about|with)\s+([^.,!?]+?)(?:\.|!|,|$)",
            
            # Avoidance patterns
            r"i (?:avoid|stay away from|won't touch)\s+([^.,!?]+?)(?:\.|!|,|$)",
            r"i would never (?:eat|try|use|do)\s+([^.,!?]+?)(?:\.|!|,|$)"
        ]
        
        # Enhanced neutral preference indicators with more nuanced patterns
        self.neutral_patterns = [
            # Qualified positive (lukewarm)
            r"i (?:sometimes|occasionally|might|could)\s+(?:like|enjoy)\s+([^.,!?]+?)(?:\.|!|,|$)",
            r"([^.,!?]+?)\s+(?:is|are)\s+(?:okay|fine|alright|not bad|decent|average|so-so)(?:\.|!|,|$)",
            
            # Explicit neutrality
            r"i'm (?:neutral about|indifferent to|ambivalent about)\s+([^.,!?]+?)(?:\.|!|,|$)",
            r"i (?:don't mind|have no opinion about|am indifferent to)\s+([^.,!?]+?)(?:\.|!|,|$)",
            
            # Conditional preferences
            r"([^.,!?]+?)\s+(?:depends|varies|can be good|can be bad)(?:\.|!|,|$)",
            r"i have mixed feelings about\s+([^.,!?]+?)(?:\.|!|,|$)",
            
            # Moderate expressions
            r"([^.,!?]+?)\s+is\s+(?:pretty good|quite nice|rather nice|fairly good)(?:\.|!|,|$)",
            r"i (?:sort of|kind of|somewhat)\s+(?:like|enjoy)\s+([^.,!?]+?)(?:\.|!|,|$)"
        ]
        
        # ============================================================================
        # ENHANCED FACT EXTRACTION PATTERNS
        # ============================================================================
        
        # Enhanced fact extraction patterns with comprehensive coverage and confidence scoring
        self.fact_patterns = [
            # ========== AGE PATTERNS ==========
            # Direct age statements - highest confidence
            (r"i(?:'m|\s+am)\s+(\d+)\s+years?\s+old", "personal", "age", 0.95),
            (r"my age is\s+(\d+)", "personal", "age", 0.9),
            (r"i(?:'m|\s+am)\s+(\d+)", "personal", "age", 0.85),  # "I'm 25"
            (r"i just turned\s+(\d+)", "personal", "age", 0.9),
            (r"i'm turning\s+(\d+)", "personal", "age", 0.85),
            (r"when i was\s+(\d+)", "personal", "age", 0.7),  # Past age reference
            
            # ========== LOCATION PATTERNS ==========
            # Current location - high confidence
            (r"i (?:live|am living|reside)\s+(?:in|at)\s+([A-Z][a-zA-Z\s,'-]+?)(?:\s*[.,!?]|$)", "personal", "location", 0.9),
            (r"my (?:city|hometown|home|address) is\s+([A-Z][a-zA-Z\s,'-]+?)(?:\s*[.,!?]|$)", "personal", "location", 0.9),
            (r"i'm (?:from|based in|located in)\s+([A-Z][a-zA-Z\s,'-]+?)(?:\s*[.,!?]|$)", "personal", "location", 0.85),
            (r"i'm currently in\s+([A-Z][a-zA-Z\s,'-]+?)(?:\s*[.,!?]|$)", "personal", "location", 0.8),
            (r"i moved to\s+([A-Z][a-zA-Z\s,'-]+?)(?:\s*[.,!?]|$)", "personal", "location", 0.8),
            (r"i grew up in\s+([A-Z][a-zA-Z\s,'-]+?)(?:\s*[.,!?]|$)", "personal", "location", 0.75),
            
            # ========== OCCUPATION PATTERNS ==========
            # Current job - high confidence
            (r"i (?:work|am working)\s+(?:as\s+)?(?:a|an)\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "professional", "occupation", 0.9),
            (r"my (?:job|work|career|profession) is\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "professional", "occupation", 0.9),
            (r"i'm (?:a|an)\s+([a-zA-Z\s]+?)(?:\s+(?:by|for)\s+profession)?(?:\s*[.,!?]|$)", "professional", "occupation", 0.85),
            (r"i'm employed as\s+(?:a|an)\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "professional", "occupation", 0.85),
            (r"my profession is\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "professional", "occupation", 0.9),
            (r"i do\s+([a-zA-Z\s]+?)\s+for (?:work|a living)(?:\s*[.,!?]|$)", "professional", "occupation", 0.8),
            (r"i used to (?:work as|be)\s+(?:a|an)\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "professional", "occupation", 0.7),  # Past occupation
            
            # ========== EDUCATION PATTERNS ==========
            # Current and past education
            (r"i (?:study|am studying|major in)\s+([a-zA-Z\s]+?)(?:\s+at|\s*[.,!?]|$)", "professional", "education", 0.9),
            (r"my major is\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "professional", "education", 0.9),
            (r"i (?:studied|majored in)\s+([a-zA-Z\s]+?)(?:\s+at|\s*[.,!?]|$)", "professional", "education", 0.85),
            (r"i have a (?:degree|bachelor's|master's|phd) in\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "professional", "education", 0.9),
            (r"i graduated (?:with|in)\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "professional", "education", 0.85),
            (r"i'm (?:pursuing|getting)\s+(?:a|my)\s+([a-zA-Z\s]+?)\s+degree(?:\s*[.,!?]|$)", "professional", "education", 0.85),
            (r"i went to\s+([A-Z][a-zA-Z\s]+?)\s+(?:university|college|school)(?:\s*[.,!?]|$)", "professional", "education", 0.8),
            
            # ========== HOBBY/ACTIVITY PATTERNS ==========
            # Hobbies and interests
            (r"i (?:play|do|practice|enjoy)\s+([a-zA-Z\s]+?)(?:\s+(?:regularly|often|sometimes))?(?:\s*[.,!?]|$)", "hobby", "activity", 0.8),
            (r"my (?:hobby|hobbies|interest|passion) (?:is|are|include)\s+([a-zA-Z\s,]+?)(?:\s*[.,!?]|$)", "hobby", "activity", 0.9),
            (r"i'm (?:into|interested in|passionate about)\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "hobby", "activity", 0.8),
            (r"i spend (?:my )?(?:free )?time\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "hobby", "activity", 0.75),
            (r"in my spare time,? i\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "hobby", "activity", 0.8),
            (r"i love (?:to\s+)?([a-zA-Z\s]+?)(?:\s+in my free time)?(?:\s*[.,!?]|$)", "hobby", "activity", 0.75),
            (r"i used to (?:play|do)\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "hobby", "activity", 0.7),  # Past hobby
            
            # ========== FAMILY PATTERNS ==========
            # Family members and relationships
            (r"i have\s+(?:a|an|\d+)\s+([a-zA-Z\s]+?)(?:\s+named|\s*[.,!?]|$)", "personal", "family", 0.8),
            (r"my\s+([a-zA-Z\s]+?)\s+(?:is|are|lives?)(?:\s*[.,!?]|$)", "personal", "family", 0.75),
            (r"i'm (?:married|single|divorced|engaged)(?:\s+to\s+([a-zA-Z\s]+?))?(?:\s*[.,!?]|$)", "personal", "relationship_status", 0.9),
            (r"i have\s+(\d+)\s+(?:kids|children|sons|daughters)(?:\s*[.,!?]|$)", "personal", "family", 0.9),
            (r"my (?:spouse|partner|husband|wife) is\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "personal", "family", 0.85),
            (r"i live with my\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "personal", "family", 0.75),
            
            # ========== PHYSICAL CHARACTERISTICS ==========
            # Physical attributes
            (r"i'm\s+(\d+(?:\.\d+)?)\s+(?:feet|ft)\s+(?:tall|high)(?:\s*[.,!?]|$)", "personal", "height", 0.9),
            (r"i'm\s+(\d+(?:\.\d+)?)\s+(?:meters?|m)\s+tall(?:\s*[.,!?]|$)", "personal", "height", 0.9),
            (r"my height is\s+(\d+(?:\.\d+)?)\s+(?:feet|ft|meters?|m)(?:\s*[.,!?]|$)", "personal", "height", 0.9),
            (r"i have\s+(brown|blue|green|hazel|gray|black)\s+eyes(?:\s*[.,!?]|$)", "personal", "eye_color", 0.85),
            (r"my eyes are\s+(brown|blue|green|hazel|gray|black)(?:\s*[.,!?]|$)", "personal", "eye_color", 0.85),
            (r"i have\s+(brown|black|blonde|red|gray|white)\s+hair(?:\s*[.,!?]|$)", "personal", "hair_color", 0.85),
            (r"my hair is\s+(brown|black|blonde|red|gray|white)(?:\s*[.,!?]|$)", "personal", "hair_color", 0.85),
            
            # ========== PREFERENCES AND TRAITS ==========
            # Personal preferences that are factual
            (r"i'm\s+(left|right)\s+handed(?:\s*[.,!?]|$)", "personal", "handedness", 0.9),
            (r"i'm (?:a\s+)?(vegetarian|vegan|pescatarian)(?:\s*[.,!?]|$)", "personal", "diet", 0.9),
            (r"i (?:speak|am fluent in)\s+([a-zA-Z\s,]+?)(?:\s*[.,!?]|$)", "personal", "languages", 0.85),
            (r"my native language is\s+([a-zA-Z\s]+?)(?:\s*[.,!?]|$)", "personal", "languages", 0.9),
            (r"i was born (?:in|on)\s+([a-zA-Z\s,\d]+?)(?:\s*[.,!?]|$)", "personal", "birthplace", 0.85),
            
            # ========== CONTACT INFORMATION ==========
            # Contact details (be careful with privacy)
            (r"my (?:email|email address) is\s+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?:\s*[.,!?]|$)", "personal", "email", 0.95),
            (r"you can (?:email|contact) me at\s+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?:\s*[.,!?]|$)", "personal", "email", 0.9),
            (r"my phone (?:number )?is\s+([\d\s\-\(\)]+?)(?:\s*[.,!?]|$)", "personal", "phone", 0.9),
        ]
        
        # Enhanced fact validation rules
        self.fact_validation_rules = {
            'age': {
                'min_value': 1,
                'max_value': 120,
                'type': 'numeric'
            },
            'height': {
                'min_value': 0.5,  # meters or feet
                'max_value': 3.0,
                'type': 'numeric'
            },
            'location': {
                'min_length': 2,
                'max_length': 100,
                'type': 'text',
                'invalid_words': ['the', 'and', 'or', 'but', 'in', 'on', 'at']
            },
            'occupation': {
                'min_length': 2,
                'max_length': 50,
                'type': 'text',
                'invalid_words': ['the', 'and', 'or', 'but']
            },
            'education': {
                'min_length': 2,
                'max_length': 50,
                'type': 'text'
            },
            'activity': {
                'min_length': 2,
                'max_length': 50,
                'type': 'text'
            },
            'family': {
                'min_length': 2,
                'max_length': 30,
                'type': 'text'
            },
            'email': {
                'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
                'type': 'email'
            },
            'phone': {
                'min_length': 7,
                'max_length': 20,
                'type': 'text'
            }
        }
        
        # ============================================================================
        # CONFIDENCE SCORING WEIGHTS
        # ============================================================================
        
        self.confidence_weights = {
            'direct_statement': 0.9,      # "My name is John"
            'possessive_form': 0.8,       # "John's favorite"
            'pattern_match': 0.7,         # Pattern-based extraction
            'keyword_match': 0.6,         # Keyword-based extraction
            'context_clue': 0.5,          # Contextual inference
            'uncertain': 0.3              # Low confidence extraction
        }
        
        # Track extracted entities for conflict resolution
        self.entity_history: Dict[str, List[Entity]] = {}
        
        self.logger.info("EntityExtractor initialized with pattern-based NER capabilities")
    
    def extract_entities(self, text: str) -> List[Entity]:
        """
        Extract all entities from the given text.
        
        Implements comprehensive entity extraction using pattern matching
        and keyword detection as specified in Requirements 3.1, 3.2, 3.3.
        
        Args:
            text: Input text to extract entities from
            
        Returns:
            List of extracted entities with confidence scores
        """
        if not text or len(text.strip()) < 3:
            return []
        
        entities = []
        text_lower = text.lower().strip()
        
        try:
            # Extract user names
            name_entities = self._extract_user_names(text)
            entities.extend(name_entities)
            
            # Extract preferences (likes, dislikes, neutral)
            preference_entities = self._extract_preferences(text)
            entities.extend(preference_entities)
            
            # Extract factual information
            fact_entities = self._extract_facts(text)
            entities.extend(fact_entities)
            
            # Remove duplicates and merge similar entities
            entities = self._deduplicate_entities(entities)
            
            # Update entity history for conflict resolution
            for entity in entities:
                if entity.name not in self.entity_history:
                    self.entity_history[entity.name] = []
                self.entity_history[entity.name].append(entity)
            
            self.logger.debug(f"Extracted {len(entities)} entities from text: '{text[:50]}...'")
            
            return entities
            
        except Exception as e:
            self.logger.error(f"Failed to extract entities from text: {e}")
            return []
    
    def _extract_user_names(self, text: str) -> List[Entity]:
        """
        Extract user names from conversation text.
        
        Args:
            text: Input text
            
        Returns:
            List of user name entities
        """
        names = []
        text_lower = text.lower()
        
        # First check if text contains negative patterns that should prevent name extraction
        for negative_pattern in self.name_negative_patterns:
            if re.search(negative_pattern, text_lower):
                self.logger.debug(f"Skipping name extraction due to negative pattern: {negative_pattern}")
                return names  # Return empty list if negative pattern found
        
        # Get names to exclude (pet names, character names, etc.)
        excluded_names = set()
        for exclusion_pattern in self.name_exclusion_patterns:
            matches = re.finditer(exclusion_pattern, text, re.IGNORECASE)
            for match in matches:
                excluded_names.add(match.group(1).strip().lower())
        
        for pattern in self.name_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                name = match.group(1).strip()
                
                # Skip if this name should be excluded
                if name.lower() in excluded_names:
                    self.logger.debug(f"Excluding name '{name}' as it matches exclusion pattern")
                    continue
                
                # Validate the extracted name
                if self._is_valid_name(name):
                    confidence = self._calculate_name_confidence(name, pattern, text)
                    
                    entity = Entity(
                        name=name,
                        entity_type=EntityType.USER_NAME,
                        value=name,
                        confidence=confidence,
                        first_mentioned=datetime.now(),
                        last_updated=datetime.now(),
                        related_memories=[]
                    )
                    
                    names.append(entity)
                    self.logger.debug(f"Extracted user name: '{name}' with confidence {confidence:.2f}")
        
        return names
    
    def _extract_preferences(self, text: str) -> List[Entity]:
        """
        Extract user preferences (likes, dislikes, neutral) from text.
        
        Args:
            text: Input text
            
        Returns:
            List of preference entities
        """
        preferences = []
        
        # Special handling for "my favorite X is Y" pattern
        favorite_pattern = r"my favorite\s+[^.,!?]+?\s+is\s+([^.,!?]+?)(?:\.|!|,|$)"
        matches = re.finditer(favorite_pattern, text, re.IGNORECASE)
        for match in matches:
            preference_item = match.group(1).strip()
            if self._is_valid_preference(preference_item):
                entity = self._create_preference_entity(
                    preference_item, PreferenceType.LIKE, favorite_pattern, text
                )
                preferences.append(entity)
        
        # Extract likes
        for pattern in self.like_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                preference_item = match.group(1).strip()
                if self._is_valid_preference(preference_item):
                    entity = self._create_preference_entity(
                        preference_item, PreferenceType.LIKE, pattern, text
                    )
                    preferences.append(entity)
        
        # Extract dislikes
        for pattern in self.dislike_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                preference_item = match.group(1).strip()
                if self._is_valid_preference(preference_item):
                    entity = self._create_preference_entity(
                        preference_item, PreferenceType.DISLIKE, pattern, text
                    )
                    preferences.append(entity)
        
        # Extract neutral preferences
        for pattern in self.neutral_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                preference_item = match.group(1).strip()
                if self._is_valid_preference(preference_item):
                    entity = self._create_preference_entity(
                        preference_item, PreferenceType.NEUTRAL, pattern, text
                    )
                    preferences.append(entity)
        
        return preferences
    
    def _extract_facts(self, text: str) -> List[Entity]:
        """
        Extract factual information from text with enhanced patterns and confidence scoring.
        
        This method implements comprehensive fact extraction using:
        - Enhanced pattern matching for various fact types
        - Context-aware confidence scoring
        - Sophisticated validation for different fact categories
        - Proper categorization (personal, professional, hobby)
        
        Args:
            text: Input text
            
        Returns:
            List of fact entities with confidence scores
        """
        facts = []
        
        for pattern_info in self.fact_patterns:
            if len(pattern_info) == 4:
                pattern, category, fact_type, base_confidence = pattern_info
            else:
                # Fallback for old format
                pattern, category, fact_type = pattern_info
                base_confidence = 0.7
            
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                fact_value = match.group(1).strip()
                
                if self._is_valid_fact_enhanced(fact_value, fact_type):
                    # Calculate enhanced confidence score
                    confidence = self._calculate_fact_confidence_enhanced(
                        fact_value, fact_type, pattern, text, base_confidence
                    )
                    
                    entity = Entity(
                        name=f"{fact_type}_{fact_value}",
                        entity_type=EntityType.FACT,
                        value=fact_value,
                        confidence=confidence,
                        first_mentioned=datetime.now(),
                        last_updated=datetime.now(),
                        related_memories=[]
                    )
                    
                    facts.append(entity)
                    self.logger.debug(f"Extracted fact: {fact_type}='{fact_value}' (category: {category}) with confidence {confidence:.2f}")
        
        return facts
    
    def _create_preference_entity(self, preference_item: str, preference_type: PreferenceType, 
                                pattern: str, text: str) -> Entity:
        """
        Create a preference entity with appropriate confidence scoring and validation.
        
        This method creates preference entities using the enhanced categorization system
        to ensure accurate preference type assignment and confidence scoring.
        """
        # Use the enhanced categorization to validate and potentially correct the preference type
        validated_preference_type = self.categorize_preference(text, preference_item)
        
        # If the pattern-based extraction differs significantly from categorization, use categorization
        if preference_type != validated_preference_type:
            self.logger.debug(f"Preference type corrected for '{preference_item}': {preference_type} -> {validated_preference_type}")
            preference_type = validated_preference_type
        
        confidence = self._calculate_preference_confidence(preference_item, pattern, text, preference_type)
        
        entity = Entity(
            name=f"{preference_type.value}_{preference_item}",
            entity_type=EntityType.PREFERENCE,
            value=f"{preference_type.value}: {preference_item}",
            confidence=confidence,
            first_mentioned=datetime.now(),
            last_updated=datetime.now(),
            related_memories=[]
        )
        
        self.logger.debug(f"Created preference entity: {preference_type.value} '{preference_item}' with confidence {confidence:.2f}")
        return entity
    
    def _is_valid_name(self, name: str) -> bool:
        """Validate if the extracted string is likely a valid name."""
        if not name or len(name) < 2 or len(name) > 50:
            return False
        
        # Check if it's a common name or follows name patterns
        name_lower = name.lower()
        
        # Reject common non-names and invalid words first
        non_names = {
            'user', 'person', 'someone', 'anybody', 'everyone', 'nobody',
            'called', 'known', 'not', 'dr', 'mr', 'mrs', 'ms', 'prof', 'professor',
            'the', 'and', 'but', 'or', 'so', 'yet', 'for', 'nor'
        }
        if name_lower in non_names:
            return False
        
        # Check against common names
        if name_lower in self.common_names:
            return True
        
        # Check name patterns (starts with capital, contains only letters and spaces)
        if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', name):
            # Additional validation for proper names
            if len(name) >= 3:  # Require at least 3 characters for non-common names
                return True
        
        # Reject single letters or very short names that aren't common
        if len(name) < 3 and name_lower not in self.common_names:
            return False
        
        return True
    
    def _is_valid_preference(self, preference: str) -> bool:
        """Validate if the extracted string is likely a valid preference."""
        if not preference or len(preference) < 2 or len(preference) > 100:
            return False
        
        # Remove common noise words
        noise_words = {'it', 'that', 'this', 'them', 'they', 'something', 'anything'}
        if preference.lower().strip() in noise_words:
            return False
        
        # Check for reasonable content (not just punctuation or numbers)
        if re.match(r'^[^\w\s]*$', preference):
            return False
        
        return True
    
    def _is_valid_fact_enhanced(self, fact_value: str, fact_type: str) -> bool:
        """
        Enhanced validation for extracted facts using comprehensive rules.
        
        Args:
            fact_value: The extracted fact value
            fact_type: The type of fact (age, location, occupation, etc.)
            
        Returns:
            True if the fact is valid, False otherwise
        """
        if not fact_value or len(fact_value.strip()) == 0:
            return False
        
        fact_value = fact_value.strip()
        
        # Get validation rules for this fact type
        rules = self.fact_validation_rules.get(fact_type, {})
        
        # Type-specific validation
        if fact_type == "age":
            try:
                age = int(fact_value)
                return rules.get('min_value', 1) <= age <= rules.get('max_value', 120)
            except ValueError:
                return False
        
        elif fact_type == "height":
            try:
                height = float(fact_value)
                return rules.get('min_value', 0.5) <= height <= rules.get('max_value', 3.0)
            except ValueError:
                return False
        
        elif fact_type == "email":
            pattern = rules.get('pattern', r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
            return bool(re.match(pattern, fact_value))
        
        elif fact_type in ["location", "occupation", "education", "activity", "family"]:
            # Text-based validation
            min_len = rules.get('min_length', 2)
            max_len = rules.get('max_length', 100)
            
            if not (min_len <= len(fact_value) <= max_len):
                return False
            
            # Check for invalid words (too generic)
            invalid_words = rules.get('invalid_words', [])
            if fact_value.lower() in invalid_words:
                return False
            
            # Check for reasonable content (not just punctuation or numbers)
            if re.match(r'^[^\w\s]*$', fact_value):
                return False
            
            # Location-specific validation
            if fact_type == "location":
                # Should start with capital letter for proper nouns
                if not fact_value[0].isupper():
                    return False
                
                # Reject obviously invalid locations
                invalid_locations = {'here', 'there', 'somewhere', 'nowhere', 'anywhere'}
                if fact_value.lower() in invalid_locations:
                    return False
            
            # Occupation-specific validation
            elif fact_type == "occupation":
                # Reject obviously invalid occupations
                invalid_occupations = {'person', 'human', 'someone', 'nobody', 'everybody'}
                if fact_value.lower() in invalid_occupations:
                    return False
            
            return True
        
        elif fact_type in ["eye_color", "hair_color"]:
            # Color validation
            valid_colors = {
                'eye_color': {'brown', 'blue', 'green', 'hazel', 'gray', 'black'},
                'hair_color': {'brown', 'black', 'blonde', 'red', 'gray', 'white'}
            }
            return fact_value.lower() in valid_colors.get(fact_type, set())
        
        elif fact_type == "handedness":
            return fact_value.lower() in {'left', 'right'}
        
        elif fact_type == "diet":
            return fact_value.lower() in {'vegetarian', 'vegan', 'pescatarian'}
        
        elif fact_type == "relationship_status":
            return fact_value.lower() in {'married', 'single', 'divorced', 'engaged'}
        
        elif fact_type == "phone":
            # Basic phone number validation
            min_len = rules.get('min_length', 7)
            max_len = rules.get('max_length', 20)
            
            # Remove common phone number formatting
            clean_phone = re.sub(r'[\s\-\(\)]', '', fact_value)
            
            # Should contain mostly digits
            if not re.match(r'^\+?[\d\s\-\(\)]+$', fact_value):
                return False
            
            return min_len <= len(clean_phone) <= max_len
        
        # Default validation for unknown types
        return len(fact_value) >= 1 and len(fact_value) <= 100
    
    def _calculate_fact_confidence_enhanced(self, fact_value: str, fact_type: str, 
                                          pattern: str, text: str, base_confidence: float) -> float:
        """
        Calculate enhanced confidence score for extracted facts.
        
        This method implements sophisticated confidence scoring based on:
        - Statement directness and clarity
        - Context analysis around the fact
        - Fact type-specific confidence adjustments
        - Pattern strength and specificity
        
        Args:
            fact_value: The extracted fact value
            fact_type: The type of fact
            pattern: The regex pattern that matched
            text: The original text
            base_confidence: Base confidence from pattern definition
            
        Returns:
            Confidence score between 0.1 and 1.0
        """
        confidence = base_confidence
        text_lower = text.lower()
        
        # ========== DIRECTNESS ANALYSIS ==========
        # Boost confidence for direct, first-person statements
        direct_indicators = ['my', 'i am', "i'm", 'i have', 'i live', 'i work', 'i study']
        if any(indicator in text_lower for indicator in direct_indicators):
            confidence += 0.05
        
        # Boost for very direct statements
        very_direct = ['my name is', 'i am', 'my age is', 'my job is', 'i live in']
        if any(indicator in text_lower for indicator in very_direct):
            confidence += 0.1
        
        # ========== CONTEXT ANALYSIS ==========
        # Reduce confidence for uncertain language
        uncertain_indicators = ['maybe', 'perhaps', 'i think', 'probably', 'might be', 'could be']
        if any(indicator in text_lower for indicator in uncertain_indicators):
            confidence -= 0.2
        
        # Reduce confidence for past tense (less current)
        past_indicators = ['used to', 'was', 'were', 'had been', 'previously']
        if any(indicator in text_lower for indicator in past_indicators):
            confidence -= 0.1
        
        # Boost confidence for current/present statements
        present_indicators = ['currently', 'now', 'at the moment', 'these days', 'right now']
        if any(indicator in text_lower for indicator in present_indicators):
            confidence += 0.1
        
        # ========== FACT TYPE-SPECIFIC ADJUSTMENTS ==========
        if fact_type == "age":
            # Age is usually very factual
            confidence += 0.05
            
            # Check for reasonable age context
            try:
                age_val = int(fact_value)
                if 13 <= age_val <= 80:  # Most common age range for users
                    confidence += 0.05
                elif age_val < 13 or age_val > 80:
                    confidence -= 0.1  # Less common ages
            except ValueError:
                pass
        
        elif fact_type == "location":
            # Location confidence based on specificity
            if ',' in fact_value:  # City, State or City, Country
                confidence += 0.1
            
            # Check for common location words
            location_words = ['city', 'town', 'state', 'country', 'province']
            if any(word in text_lower for word in location_words):
                confidence += 0.05
        
        elif fact_type == "occupation":
            # Professional titles are usually factual
            professional_words = ['work', 'job', 'career', 'profession', 'employed']
            if any(word in text_lower for word in professional_words):
                confidence += 0.05
            
            # Common occupation validation
            common_occupations = {
                'teacher', 'doctor', 'nurse', 'engineer', 'programmer', 'developer',
                'manager', 'student', 'lawyer', 'designer', 'writer', 'artist'
            }
            if fact_value.lower() in common_occupations:
                confidence += 0.05
        
        elif fact_type == "education":
            # Education statements are usually factual
            education_words = ['study', 'major', 'degree', 'university', 'college', 'school']
            if any(word in text_lower for word in education_words):
                confidence += 0.05
        
        elif fact_type in ["eye_color", "hair_color", "handedness", "diet"]:
            # Physical characteristics and personal traits are usually very factual
            confidence += 0.1
        
        elif fact_type == "email":
            # Email addresses are very factual when provided
            confidence += 0.1
        
        # ========== PATTERN STRENGTH ANALYSIS ==========
        # Boost confidence for longer, more specific patterns
        if len(pattern) > 50:  # Complex patterns are usually more specific
            confidence += 0.05
        
        # Boost confidence for patterns with multiple capture groups or specific formatting
        if r'\d+' in pattern:  # Patterns expecting numbers (age, phone, etc.)
            confidence += 0.05
        
        # ========== CONTEXT WINDOW ANALYSIS ==========
        # Analyze the context around the extracted fact
        fact_pos = text_lower.find(fact_value.lower())
        if fact_pos != -1:
            # Get context before and after the fact
            context_start = max(0, fact_pos - 20)
            context_end = min(len(text), fact_pos + len(fact_value) + 20)
            context = text_lower[context_start:context_end]
            
            # Boost confidence if fact is surrounded by relevant context
            relevant_context = {
                'age': ['old', 'years', 'birthday', 'born'],
                'location': ['live', 'from', 'city', 'town', 'country'],
                'occupation': ['work', 'job', 'employed', 'career'],
                'education': ['study', 'school', 'university', 'degree'],
                'activity': ['play', 'hobby', 'enjoy', 'practice']
            }
            
            context_words = relevant_context.get(fact_type, [])
            if any(word in context for word in context_words):
                confidence += 0.05
        
        # ========== FINAL ADJUSTMENTS ==========
        # Ensure confidence is within valid range
        confidence = min(1.0, max(0.1, confidence))
        
        # Apply slight randomness reduction for very high confidence to be conservative
        if confidence > 0.95:
            confidence = 0.95
        
        return confidence
    
    def _calculate_name_confidence(self, name: str, pattern: str, text: str) -> float:
        """Calculate confidence score for extracted name."""
        base_confidence = self.confidence_weights['pattern_match']
        
        # Boost confidence for common names
        if name.lower() in self.common_names:
            base_confidence += 0.1
        
        # Boost confidence for direct statements
        if any(phrase in text.lower() for phrase in ['my name is', "i'm", 'call me']):
            base_confidence = self.confidence_weights['direct_statement']
        
        # Reduce confidence for very short or very long names
        if len(name) < 3:
            base_confidence -= 0.2
        elif len(name) > 20:
            base_confidence -= 0.1
        
        return min(1.0, max(0.1, base_confidence))
    
    def _calculate_preference_confidence(self, preference: str, pattern: str, text: str, preference_type: PreferenceType = None) -> float:
        """
        Calculate confidence score for extracted preference with enhanced scoring.
        
        Args:
            preference: The preference item
            pattern: The regex pattern that matched
            text: The original text
            preference_type: The categorized preference type (optional)
            
        Returns:
            Confidence score between 0.1 and 1.0
        """
        base_confidence = self.confidence_weights['pattern_match']
        
        # Boost confidence for strong preference indicators
        strong_indicators = ['love', 'hate', 'favorite', 'best', 'worst', 'amazing', 'terrible', 'obsessed', 'can\'t stand']
        moderate_indicators = ['like', 'dislike', 'enjoy', 'prefer', 'good', 'bad', 'great', 'awful']
        weak_indicators = ['okay', 'fine', 'sometimes', 'occasionally', 'maybe', 'sort of', 'kind of']
        
        text_lower = text.lower()
        
        # Adjust confidence based on strength of sentiment indicators
        if any(indicator in text_lower for indicator in strong_indicators):
            base_confidence += 0.2
        elif any(indicator in text_lower for indicator in moderate_indicators):
            base_confidence += 0.1
        elif any(indicator in text_lower for indicator in weak_indicators):
            base_confidence -= 0.1
        
        # Boost confidence for direct statements
        direct_patterns = ['my favorite', 'i love', 'i hate', 'i absolutely', 'i really']
        if any(pattern in text_lower for pattern in direct_patterns):
            base_confidence += 0.15
        
        # Reduce confidence for very generic preferences
        generic_prefs = ['things', 'stuff', 'something', 'anything', 'everything', 'nothing']
        if preference.lower() in generic_prefs:
            base_confidence -= 0.4
        
        # Reduce confidence for very short preferences (likely incomplete extraction)
        if len(preference.strip()) < 3:
            base_confidence -= 0.3
        
        # Boost confidence if preference type is strongly indicated
        if preference_type:
            if preference_type == PreferenceType.LIKE and any(word in text_lower for word in ['love', 'favorite', 'amazing', 'best']):
                base_confidence += 0.1
            elif preference_type == PreferenceType.DISLIKE and any(word in text_lower for word in ['hate', 'terrible', 'worst', 'disgusting']):
                base_confidence += 0.1
            elif preference_type == PreferenceType.NEUTRAL and any(word in text_lower for word in ['okay', 'neutral', 'sometimes', 'mixed']):
                base_confidence += 0.05
        
        # Penalize if there are conflicting sentiment indicators
        positive_count = sum(1 for word in ['love', 'like', 'enjoy', 'great', 'amazing', 'favorite'] if word in text_lower)
        negative_count = sum(1 for word in ['hate', 'dislike', 'terrible', 'awful', 'worst'] if word in text_lower)
        
        if positive_count > 0 and negative_count > 0:
            base_confidence -= 0.2  # Conflicting sentiments reduce confidence
        
        return min(1.0, max(0.1, base_confidence))
    
    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """Remove duplicate entities and merge similar ones."""
        if not entities:
            return []
        
        # Group entities by type and name
        entity_groups: Dict[str, List[Entity]] = {}
        
        for entity in entities:
            key = f"{entity.entity_type.value}_{entity.name.lower()}"
            if key not in entity_groups:
                entity_groups[key] = []
            entity_groups[key].append(entity)
        
        # Keep the entity with highest confidence from each group
        deduplicated = []
        for group in entity_groups.values():
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                # Keep the one with highest confidence
                best_entity = max(group, key=lambda e: e.confidence)
                deduplicated.append(best_entity)
        
        return deduplicated
    
    def update_user_preferences(self, text: str, entities: List[Entity]) -> None:
        """
        Update user preferences based on extracted entities.
        
        Args:
            text: Original text
            entities: List of extracted entities
        """
        try:
            preference_entities = [e for e in entities if e.entity_type == EntityType.PREFERENCE]
            
            for entity in preference_entities:
                # Update entity history
                if entity.name not in self.entity_history:
                    self.entity_history[entity.name] = []
                
                # Check for conflicts with existing preferences
                existing_entities = self.entity_history[entity.name]
                if existing_entities:
                    resolved_entity = self.resolve_entity_conflicts(existing_entities[-1], text)
                    self.entity_history[entity.name].append(resolved_entity)
                else:
                    self.entity_history[entity.name].append(entity)
            
            self.logger.debug(f"Updated preferences for {len(preference_entities)} entities")
            
        except Exception as e:
            self.logger.error(f"Failed to update user preferences: {e}")
    
    def get_preference_confidence(self, preference: str) -> float:
        """
        Get confidence score for a specific preference.
        
        Args:
            preference: Preference to check
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        try:
            # Look for preference in entity history
            for entity_name, entity_list in self.entity_history.items():
                if preference.lower() in entity_name.lower():
                    if entity_list:
                        return entity_list[-1].confidence  # Return latest confidence
            
            return 0.0
            
        except Exception as e:
            self.logger.error(f"Failed to get preference confidence for '{preference}': {e}")
            return 0.0
    
    def extract_user_name(self, text: str) -> Optional[str]:
        """
        Extract user name from conversation text.
        
        Args:
            text: Input text
            
        Returns:
            Extracted user name or None if not found
        """
        try:
            name_entities = self._extract_user_names(text)
            
            if name_entities:
                # Return the name with highest confidence
                best_entity = max(name_entities, key=lambda e: e.confidence)
                return best_entity.value
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to extract user name: {e}")
            return None
    
    def categorize_preference(self, text: str, entity: str) -> PreferenceType:
        """
        Categorize a preference as LIKE, DISLIKE, or NEUTRAL based on comprehensive sentiment analysis.
        
        This method implements robust preference categorization using:
        - Pattern-based sentiment detection
        - Contextual analysis around the entity
        - Weighted scoring for different sentiment indicators
        - Confidence-based classification
        
        Args:
            text: Context text containing the preference expression
            entity: Entity to categorize (the subject of the preference)
            
        Returns:
            PreferenceType classification (LIKE, DISLIKE, or NEUTRAL)
        """
        try:
            text_lower = text.lower().strip()
            entity_lower = entity.lower().strip()
            
            # Enhanced sentiment indicators with weights
            strong_positive = {
                'love': 3.0, 'adore': 3.0, 'absolutely love': 3.5, 'obsessed with': 3.0,
                'crazy about': 2.5, 'passionate about': 2.5, 'amazing': 2.5, 'incredible': 2.5,
                'fantastic': 2.5, 'wonderful': 2.5, 'perfect': 2.5, 'the best': 3.0,
                'favorite': 2.5, 'my favorite': 3.0, 'really love': 2.8
            }
            
            moderate_positive = {
                'like': 2.0, 'enjoy': 2.0, 'prefer': 2.0, 'really like': 2.5,
                'great': 2.0, 'awesome': 2.0, 'good': 1.8, 'nice': 1.5,
                'pretty good': 1.8, 'quite good': 1.8, 'really good': 2.2,
                'fond of': 2.0, 'into': 1.8, 'appreciate': 1.8
            }
            
            weak_positive = {
                'decent': 1.2, 'not bad': 1.2, 'pretty decent': 1.3,
                'quite nice': 1.4, 'rather good': 1.3
            }
            
            strong_negative = {
                'hate': -3.0, 'despise': -3.0, 'loathe': -3.0, 'detest': -3.0,
                'can\'t stand': -3.0, 'absolutely hate': -3.5, 'disgusting': -2.8,
                'terrible': -2.5, 'awful': -2.5, 'horrible': -2.5, 'the worst': -3.0,
                'gross': -2.5, 'revolting': -2.8, 'repulsive': -2.8
            }
            
            moderate_negative = {
                'dislike': -2.0, 'don\'t like': -2.0, 'not a fan': -2.0,
                'bad': -1.8, 'poor': -1.8, 'disappointing': -2.0,
                'not good': -1.8, 'not great': -1.8, 'unpleasant': -2.0,
                'annoying': -1.8, 'irritating': -1.8
            }
            
            weak_negative = {
                'meh': -1.2, 'not really': -1.2, 'not particularly': -1.2,
                'not so good': -1.5, 'could be better': -1.3
            }
            
            neutral_indicators = {
                'okay': 0.0, 'fine': 0.0, 'alright': 0.0, 'average': 0.0,
                'so-so': 0.0, 'neutral': 0.0, 'indifferent': 0.0,
                'sometimes': 0.0, 'occasionally': 0.0, 'maybe': 0.0,
                'not sure': 0.0, 'mixed feelings': 0.0, 'it depends': 0.0
            }
            
            # Calculate sentiment score with contextual analysis
            sentiment_score = 0.0
            context_window = 10  # Words around the entity to consider
            
            # Find entity position in text for contextual analysis
            entity_pos = text_lower.find(entity_lower)
            if entity_pos == -1:
                # Entity not found directly, use whole text
                context_text = text_lower
            else:
                # Extract context around the entity
                words = text_lower.split()
                entity_words = entity_lower.split()
                
                # Find entity word position
                entity_word_pos = -1
                for i, word in enumerate(words):
                    if any(ew in word for ew in entity_words):
                        entity_word_pos = i
                        break
                
                if entity_word_pos != -1:
                    start_pos = max(0, entity_word_pos - context_window)
                    end_pos = min(len(words), entity_word_pos + len(entity_words) + context_window)
                    context_text = ' '.join(words[start_pos:end_pos])
                else:
                    context_text = text_lower
            
            # Score sentiment indicators with proximity weighting
            all_indicators = [
                (strong_positive, 1.0),
                (moderate_positive, 1.0),
                (weak_positive, 1.0),
                (strong_negative, 1.0),
                (moderate_negative, 1.0),
                (weak_negative, 1.0),
                (neutral_indicators, 1.0)
            ]
            
            for indicator_dict, base_weight in all_indicators:
                for phrase, score in indicator_dict.items():
                    if phrase in context_text:
                        # Apply proximity weighting - closer to entity gets higher weight
                        phrase_pos = context_text.find(phrase)
                        entity_pos_in_context = context_text.find(entity_lower)
                        
                        if entity_pos_in_context != -1 and phrase_pos != -1:
                            distance = abs(phrase_pos - entity_pos_in_context)
                            proximity_weight = max(0.5, 1.0 - (distance / 100.0))  # Closer = higher weight
                        else:
                            proximity_weight = 0.8  # Default weight when positions unclear
                        
                        weighted_score = score * base_weight * proximity_weight
                        sentiment_score += weighted_score
                        
                        self.logger.debug(f"Found '{phrase}' for '{entity}': score={score}, weight={proximity_weight:.2f}, contribution={weighted_score:.2f}")
            
            # Handle special patterns
            special_patterns = [
                (r"my favorite\s+[^.,!?]*?" + re.escape(entity_lower), 3.0),
                (r"i love\s+[^.,!?]*?" + re.escape(entity_lower), 2.8),
                (r"i hate\s+[^.,!?]*?" + re.escape(entity_lower), -2.8),
                (r"i can't stand\s+[^.,!?]*?" + re.escape(entity_lower), -3.0),
                (r"i'm obsessed with\s+[^.,!?]*?" + re.escape(entity_lower), 3.2),
                (r"i'm not a fan of\s+[^.,!?]*?" + re.escape(entity_lower), -2.2),
                (r"i'm neutral about\s+[^.,!?]*?" + re.escape(entity_lower), 0.0),
                (r"i sometimes like\s+[^.,!?]*?" + re.escape(entity_lower), 0.5),
                (r"i occasionally enjoy\s+[^.,!?]*?" + re.escape(entity_lower), 0.5)
            ]
            
            for pattern, pattern_score in special_patterns:
                if re.search(pattern, context_text):
                    sentiment_score += pattern_score
                    self.logger.debug(f"Special pattern matched for '{entity}': {pattern_score}")
            
            # Handle negations (flip sentiment if negated)
            negation_patterns = [
                r"not\s+[^.,!?]*?" + re.escape(entity_lower),
                r"don't\s+[^.,!?]*?" + re.escape(entity_lower),
                r"doesn't\s+[^.,!?]*?" + re.escape(entity_lower),
                r"never\s+[^.,!?]*?" + re.escape(entity_lower)
            ]
            
            for neg_pattern in negation_patterns:
                if re.search(neg_pattern, context_text):
                    # Check if this is a double negative (e.g., "not bad")
                    double_neg_patterns = [
                        r"not\s+bad", r"not\s+terrible", r"not\s+awful",
                        r"not\s+horrible", r"not\s+the\s+worst"
                    ]
                    
                    is_double_negative = any(re.search(dn_pattern, context_text) for dn_pattern in double_neg_patterns)
                    
                    if not is_double_negative and sentiment_score != 0:
                        sentiment_score *= -0.8  # Flip and slightly reduce intensity
                        self.logger.debug(f"Negation detected for '{entity}', flipped sentiment: {sentiment_score}")
            
            # Classify based on sentiment score with confidence thresholds
            confidence_threshold_high = 2.0
            confidence_threshold_low = 0.8
            
            self.logger.debug(f"Final sentiment score for '{entity}': {sentiment_score}")
            
            if sentiment_score >= confidence_threshold_low:
                return PreferenceType.LIKE
            elif sentiment_score <= -confidence_threshold_low:
                return PreferenceType.DISLIKE
            else:
                return PreferenceType.NEUTRAL
                
        except Exception as e:
            self.logger.error(f"Failed to categorize preference for '{entity}': {e}")
            return PreferenceType.NEUTRAL
    
    def extract_facts(self, text: str) -> List[Fact]:
        """
        Extract factual information from text with enhanced patterns and confidence scoring.
        
        This method implements comprehensive fact extraction using:
        - Enhanced pattern matching for various fact types
        - Context-aware confidence scoring
        - Sophisticated validation for different fact categories
        - Proper categorization (personal, professional, hobby)
        
        Args:
            text: Input text
            
        Returns:
            List of extracted facts with confidence scores
        """
        try:
            facts = []
            
            for pattern_info in self.fact_patterns:
                if len(pattern_info) == 4:
                    pattern, category, fact_type, base_confidence = pattern_info
                else:
                    # Fallback for old format
                    pattern, category, fact_type = pattern_info
                    base_confidence = 0.7
                
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    fact_value = match.group(1).strip()
                    
                    if self._is_valid_fact_enhanced(fact_value, fact_type):
                        # Calculate enhanced confidence score
                        confidence = self._calculate_fact_confidence_enhanced(
                            fact_value, fact_type, pattern, text, base_confidence
                        )
                        
                        fact = Fact(
                            content=f"{fact_type}: {fact_value}",
                            confidence=confidence,
                            source_memory_id="",  # Will be set by caller
                            verified=False,
                            category=category
                        )
                        
                        facts.append(fact)
                        self.logger.debug(f"Extracted fact: {fact_type}='{fact_value}' (category: {category}) with confidence {confidence:.2f}")
            
            self.logger.debug(f"Extracted {len(facts)} facts from text")
            return facts
            
        except Exception as e:
            self.logger.error(f"Failed to extract facts: {e}")
            return []
    
    def resolve_entity_conflicts(self, existing_entity: Entity, new_info: str) -> Entity:
        """
        Resolve conflicts between existing entity information and new information.
        
        This method implements sophisticated entity conflict resolution using:
        - Multi-factor decision making (confidence, recency, context)
        - Entity type-specific resolution strategies
        - Preference evolution tracking for likes/dislikes
        - Fact verification and correction handling
        - Name change detection and validation
        - Entity history maintenance for tracking changes
        
        Args:
            existing_entity: Previously extracted entity
            new_info: New information that might conflict
            
        Returns:
            Resolved entity with updated information
        """
        try:
            # Extract new entities from the new information
            new_entities = self.extract_entities(new_info)
            
            # Find entities that might conflict with the existing entity
            conflicting_entities = self._detect_entity_conflicts(existing_entity, new_entities, new_info)
            
            if not conflicting_entities:
                # No conflict detected, return existing entity with updated timestamp
                existing_entity.last_updated = datetime.now()
                return existing_entity
            
            # Select the best conflicting entity for resolution
            new_entity = self._select_best_conflicting_entity(conflicting_entities, new_info)
            
            # Apply entity type-specific resolution strategy
            resolved_entity = self._apply_resolution_strategy(existing_entity, new_entity, new_info)
            
            # Update entity history for tracking changes
            self._update_entity_history(existing_entity, resolved_entity, new_info)
            
            return resolved_entity
                
        except Exception as e:
            self.logger.error(f"Failed to resolve entity conflicts: {e}")
            return existing_entity
    
    def _detect_entity_conflicts(self, existing_entity: Entity, new_entities: List[Entity], new_info: str) -> List[Entity]:
        """
        Detect conflicts between existing entity and new entities using sophisticated algorithms.
        
        This method implements enhanced conflict detection that goes beyond simple name matching:
        - Semantic similarity for entity values
        - Context-aware conflict detection
        - Entity type-specific conflict rules
        - Preference contradiction detection
        
        Args:
            existing_entity: The existing entity to check against
            new_entities: List of newly extracted entities
            new_info: The original text containing new information
            
        Returns:
            List of entities that conflict with the existing entity
        """
        conflicting_entities = []
        
        for new_entity in new_entities:
            # Direct type and name match (traditional conflict)
            if (new_entity.entity_type == existing_entity.entity_type and 
                new_entity.name.lower() == existing_entity.name.lower()):
                conflicting_entities.append(new_entity)
                continue
            
            # Entity type-specific conflict detection
            if existing_entity.entity_type == EntityType.USER_NAME:
                # Name conflicts: detect name changes or corrections
                if (new_entity.entity_type == EntityType.USER_NAME and 
                    self._is_name_conflict(existing_entity, new_entity, new_info)):
                    conflicting_entities.append(new_entity)
            
            elif existing_entity.entity_type == EntityType.PREFERENCE:
                # Preference conflicts: detect contradictory preferences
                if (new_entity.entity_type == EntityType.PREFERENCE and 
                    self._is_preference_conflict(existing_entity, new_entity, new_info)):
                    conflicting_entities.append(new_entity)
            
            elif existing_entity.entity_type == EntityType.FACT:
                # Fact conflicts: detect contradictory facts
                if (new_entity.entity_type == EntityType.FACT and 
                    self._is_fact_conflict(existing_entity, new_entity, new_info)):
                    conflicting_entities.append(new_entity)
        
        return conflicting_entities
    
    def _is_name_conflict(self, existing_entity: Entity, new_entity: Entity, context: str) -> bool:
        """
        Detect if two name entities conflict (name change, correction, etc.).
        
        Args:
            existing_entity: Existing name entity
            new_entity: New name entity
            context: Context text
            
        Returns:
            True if entities conflict, False otherwise
        """
        existing_name = existing_entity.value.lower().strip()
        new_name = new_entity.value.lower().strip()
        
        # Same name, no conflict
        if existing_name == new_name:
            return False
        
        context_lower = context.lower()
        
        # Detect explicit name changes or corrections
        name_change_indicators = [
            'my name is actually', 'call me', 'i prefer', 'my real name',
            'my name changed', 'i go by', 'please call me', 'actually my name'
        ]
        
        # Check if context suggests a name change/correction
        if any(indicator in context_lower for indicator in name_change_indicators):
            return True
        
        # Check for nickname/full name relationships
        # If one name is contained in the other, it might be a nickname/full name pair
        if (existing_name in new_name or new_name in existing_name) and abs(len(existing_name) - len(new_name)) > 2:
            return True
        
        return False
    
    def _is_preference_conflict(self, existing_entity: Entity, new_entity: Entity, context: str) -> bool:
        """
        Detect if two preference entities conflict (contradictory preferences).
        
        Args:
            existing_entity: Existing preference entity
            new_entity: New preference entity
            context: Context text
            
        Returns:
            True if entities conflict, False otherwise
        """
        # Extract preference types and items from entity values
        existing_parts = existing_entity.value.split(': ', 1)
        new_parts = new_entity.value.split(': ', 1)
        
        if len(existing_parts) != 2 or len(new_parts) != 2:
            return False
        
        existing_type, existing_item = existing_parts
        new_type, new_item = new_parts
        
        # Same preference item
        if existing_item.lower().strip() == new_item.lower().strip():
            # Check if preference types conflict (like vs dislike)
            if existing_type != new_type:
                # Direct contradiction (like -> dislike or vice versa)
                if ((existing_type == 'like' and new_type == 'dislike') or
                    (existing_type == 'dislike' and new_type == 'like')):
                    return True
        
        # Check for semantic similarity in preference items
        # (e.g., "pizza" vs "italian food" might be related)
        if self._are_preferences_semantically_related(existing_item, new_item):
            if existing_type != new_type:
                return True
        
        return False
    
    def _is_fact_conflict(self, existing_entity: Entity, new_entity: Entity, context: str) -> bool:
        """
        Detect if two fact entities conflict (contradictory facts).
        
        Args:
            existing_entity: Existing fact entity
            new_entity: New fact entity
            context: Context text
            
        Returns:
            True if entities conflict, False otherwise
        """
        # Extract fact types from entity names
        existing_fact_type = existing_entity.name.split('_')[0] if '_' in existing_entity.name else ''
        new_fact_type = new_entity.name.split('_')[0] if '_' in new_entity.name else ''
        
        # Same fact type but different values
        if existing_fact_type == new_fact_type and existing_fact_type:
            existing_value = existing_entity.value.lower().strip()
            new_value = new_entity.value.lower().strip()
            
            if existing_value != new_value:
                # Check for explicit corrections in context
                correction_indicators = [
                    'actually', 'correction', 'i meant', 'sorry', 'i misspoke',
                    'let me correct', 'that\'s wrong', 'i was wrong'
                ]
                
                context_lower = context.lower()
                if any(indicator in context_lower for indicator in correction_indicators):
                    return True
                
                # For certain fact types, any difference is a conflict
                conflicting_fact_types = ['age', 'location', 'occupation', 'email', 'phone']
                if existing_fact_type in conflicting_fact_types:
                    return True
        
        return False
    
    def _are_preferences_semantically_related(self, item1: str, item2: str) -> bool:
        """
        Check if two preference items are semantically related.
        
        This is a simple implementation that could be enhanced with
        word embeddings or semantic similarity models in the future.
        
        Args:
            item1: First preference item
            item2: Second preference item
            
        Returns:
            True if items are semantically related
        """
        item1_lower = item1.lower().strip()
        item2_lower = item2.lower().strip()
        
        # Simple keyword-based semantic relationships
        food_keywords = ['pizza', 'pasta', 'italian', 'food', 'restaurant', 'cuisine']
        music_keywords = ['music', 'song', 'band', 'artist', 'album', 'genre']
        sport_keywords = ['football', 'soccer', 'basketball', 'sport', 'game', 'team']
        
        semantic_groups = [food_keywords, music_keywords, sport_keywords]
        
        for group in semantic_groups:
            item1_in_group = any(keyword in item1_lower for keyword in group)
            item2_in_group = any(keyword in item2_lower for keyword in group)
            
            if item1_in_group and item2_in_group:
                return True
        
        # Check for substring relationships
        if item1_lower in item2_lower or item2_lower in item1_lower:
            return True
        
        return False
    
    def _select_best_conflicting_entity(self, conflicting_entities: List[Entity], context: str) -> Entity:
        """
        Select the best conflicting entity for resolution based on multiple factors.
        
        Args:
            conflicting_entities: List of conflicting entities
            context: Context text
            
        Returns:
            The best conflicting entity to use for resolution
        """
        if len(conflicting_entities) == 1:
            return conflicting_entities[0]
        
        # Score each entity based on multiple factors
        scored_entities = []
        
        for entity in conflicting_entities:
            score = entity.confidence  # Base score from confidence
            
            # Boost score for more recent entities (higher timestamp)
            # This is a simple heuristic since all new entities have current timestamp
            score += 0.1
            
            # Boost score for entities with explicit correction indicators in context
            correction_indicators = [
                'actually', 'correction', 'i meant', 'sorry', 'let me correct',
                'my real', 'i prefer', 'call me', 'please'
            ]
            
            context_lower = context.lower()
            correction_boost = sum(0.05 for indicator in correction_indicators if indicator in context_lower)
            score += correction_boost
            
            # Boost score for more specific/detailed information
            if len(entity.value) > 10:  # Longer values might be more specific
                score += 0.05
            
            scored_entities.append((entity, score))
        
        # Return entity with highest score
        best_entity = max(scored_entities, key=lambda x: x[1])[0]
        return best_entity
    
    def _apply_resolution_strategy(self, existing_entity: Entity, new_entity: Entity, context: str) -> Entity:
        """
        Apply entity type-specific resolution strategy.
        
        Args:
            existing_entity: Existing entity
            new_entity: New conflicting entity
            context: Context text
            
        Returns:
            Resolved entity
        """
        if existing_entity.entity_type == EntityType.USER_NAME:
            return self._resolve_name_conflict(existing_entity, new_entity, context)
        elif existing_entity.entity_type == EntityType.PREFERENCE:
            return self._resolve_preference_conflict(existing_entity, new_entity, context)
        elif existing_entity.entity_type == EntityType.FACT:
            return self._resolve_fact_conflict(existing_entity, new_entity, context)
        else:
            # Default resolution: use confidence-based decision
            return self._resolve_by_confidence(existing_entity, new_entity)
    
    def _resolve_name_conflict(self, existing_entity: Entity, new_entity: Entity, context: str) -> Entity:
        """
        Resolve name conflicts with special handling for name changes and corrections.
        
        Args:
            existing_entity: Existing name entity
            new_entity: New name entity
            context: Context text
            
        Returns:
            Resolved name entity
        """
        context_lower = context.lower()
        
        # Strong indicators that the new name should be preferred
        strong_change_indicators = [
            'my name is actually', 'my real name is', 'call me', 'i prefer',
            'please call me', 'i go by'
        ]
        
        # Check for strong name change indicators
        if any(indicator in context_lower for indicator in strong_change_indicators):
            return self._create_resolved_entity(existing_entity, new_entity, "Name change/correction detected")
        
        # If new name has much higher confidence, prefer it
        if new_entity.confidence > existing_entity.confidence + 0.2:
            return self._create_resolved_entity(existing_entity, new_entity, "Higher confidence name")
        
        # If existing name has higher confidence, keep it
        if existing_entity.confidence > new_entity.confidence + 0.1:
            existing_entity.last_updated = datetime.now()
            self.logger.debug(f"Kept existing name '{existing_entity.value}' due to higher confidence")
            return existing_entity
        
        # Default: prefer the new name if confidence is similar (recency bias)
        return self._create_resolved_entity(existing_entity, new_entity, "Recency bias for similar confidence")
    
    def _resolve_preference_conflict(self, existing_entity: Entity, new_entity: Entity, context: str) -> Entity:
        """
        Resolve preference conflicts with handling for preference evolution.
        
        Args:
            existing_entity: Existing preference entity
            new_entity: New preference entity
            context: Context text
            
        Returns:
            Resolved preference entity
        """
        context_lower = context.lower()
        
        # Extract preference types
        existing_parts = existing_entity.value.split(': ', 1)
        new_parts = new_entity.value.split(': ', 1)
        
        if len(existing_parts) == 2 and len(new_parts) == 2:
            existing_type, existing_item = existing_parts
            new_type, new_item = new_parts
            
            # Check for explicit preference change indicators
            change_indicators = [
                'i changed my mind', 'i don\'t like', 'i no longer', 'i used to like',
                'i used to hate', 'now i like', 'now i hate', 'actually i'
            ]
            
            if any(indicator in context_lower for indicator in change_indicators):
                return self._create_resolved_entity(existing_entity, new_entity, "Explicit preference change")
            
            # If it's a direct contradiction (like -> dislike or vice versa)
            if existing_item.lower() == new_item.lower() and existing_type != new_type:
                # Prefer the new preference if it has reasonable confidence
                if new_entity.confidence >= 0.6:
                    return self._create_resolved_entity(existing_entity, new_entity, "Preference contradiction resolved")
        
        # Use confidence-based resolution for other cases
        return self._resolve_by_confidence(existing_entity, new_entity)
    
    def _resolve_fact_conflict(self, existing_entity: Entity, new_entity: Entity, context: str) -> Entity:
        """
        Resolve fact conflicts with handling for corrections and updates.
        
        Args:
            existing_entity: Existing fact entity
            new_entity: New fact entity
            context: Context text
            
        Returns:
            Resolved fact entity
        """
        context_lower = context.lower()
        
        # Strong indicators for fact corrections
        correction_indicators = [
            'actually', 'correction', 'i meant', 'sorry', 'i misspoke',
            'let me correct', 'that\'s wrong', 'i was wrong', 'i made a mistake'
        ]
        
        if any(indicator in context_lower for indicator in correction_indicators):
            return self._create_resolved_entity(existing_entity, new_entity, "Fact correction detected")
        
        # For certain fact types, prefer more recent information
        fact_type = existing_entity.name.split('_')[0] if '_' in existing_entity.name else ''
        
        # Facts that commonly change and should prefer recent information
        changeable_facts = ['location', 'occupation', 'age', 'relationship_status']
        
        if fact_type in changeable_facts:
            # Prefer new information if confidence is reasonable
            if new_entity.confidence >= 0.7:
                return self._create_resolved_entity(existing_entity, new_entity, f"Updated {fact_type}")
        
        # For stable facts (like birthplace, education), prefer higher confidence
        stable_facts = ['birthplace', 'education', 'eye_color', 'hair_color']
        
        if fact_type in stable_facts:
            # Only update if new information has significantly higher confidence
            if new_entity.confidence > existing_entity.confidence + 0.3:
                return self._create_resolved_entity(existing_entity, new_entity, f"Higher confidence {fact_type}")
        
        # Default confidence-based resolution
        return self._resolve_by_confidence(existing_entity, new_entity)
    
    def _resolve_by_confidence(self, existing_entity: Entity, new_entity: Entity) -> Entity:
        """
        Resolve conflict based on confidence scores with recency bias.
        
        Args:
            existing_entity: Existing entity
            new_entity: New entity
            
        Returns:
            Resolved entity
        """
        # Apply small recency bias to new information
        adjusted_new_confidence = new_entity.confidence + 0.05
        
        if adjusted_new_confidence > existing_entity.confidence:
            return self._create_resolved_entity(existing_entity, new_entity, "Higher confidence with recency bias")
        else:
            existing_entity.last_updated = datetime.now()
            self.logger.debug(f"Kept existing entity '{existing_entity.name}' due to higher confidence")
            return existing_entity
    
    def _create_resolved_entity(self, existing_entity: Entity, new_entity: Entity, reason: str) -> Entity:
        """
        Create a resolved entity by merging existing and new entity information.
        
        Args:
            existing_entity: Existing entity
            new_entity: New entity
            reason: Reason for resolution
            
        Returns:
            Resolved entity
        """
        resolved_entity = Entity(
            name=existing_entity.name,  # Keep original name for consistency
            entity_type=existing_entity.entity_type,
            value=new_entity.value,  # Use new value
            confidence=max(new_entity.confidence, existing_entity.confidence * 0.9),  # Boost confidence slightly
            first_mentioned=existing_entity.first_mentioned,  # Keep original timestamp
            last_updated=datetime.now(),  # Update to current time
            related_memories=existing_entity.related_memories  # Keep memory references
        )
        
        self.logger.debug(f"Resolved entity conflict for '{existing_entity.name}': {reason}. "
                         f"Updated value from '{existing_entity.value}' to '{new_entity.value}'")
        
        return resolved_entity
    
    def _update_entity_history(self, existing_entity: Entity, resolved_entity: Entity, context: str) -> None:
        """
        Update entity history for tracking changes over time.
        
        Args:
            existing_entity: Original entity
            resolved_entity: Resolved entity
            context: Context that caused the change
        """
        try:
            entity_key = f"{existing_entity.entity_type.value}_{existing_entity.name.lower()}"
            
            # Initialize history if not exists
            if entity_key not in self.entity_history:
                self.entity_history[entity_key] = []
            
            # Add the resolved entity to history
            self.entity_history[entity_key].append(resolved_entity)
            
            # Keep only recent history (last 10 entries) to prevent memory bloat
            if len(self.entity_history[entity_key]) > 10:
                self.entity_history[entity_key] = self.entity_history[entity_key][-10:]
            
            # Log significant changes
            if existing_entity.value != resolved_entity.value:
                self.logger.info(f"Entity history updated for '{existing_entity.name}': "
                               f"'{existing_entity.value}' -> '{resolved_entity.value}'")
            
        except Exception as e:
            self.logger.error(f"Failed to update entity history: {e}")