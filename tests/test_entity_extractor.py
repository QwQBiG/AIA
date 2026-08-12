"""
Unit tests for the EntityExtractor class.

Tests the Named Entity Recognition (NER) capabilities including user name extraction,
preference categorization, and fact extraction using pattern matching and keyword detection.
"""

import pytest
from datetime import datetime
from src.memory_core.entity_extractor import EntityExtractor
from src.memory_core.data_models import Entity, EntityType, PreferenceType, Fact


class TestEntityExtractor:
    """Test suite for EntityExtractor functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = EntityExtractor()
    
    def test_initialization(self):
        """Test EntityExtractor initialization."""
        assert self.extractor is not None
        assert hasattr(self.extractor, 'name_patterns')
        assert hasattr(self.extractor, 'like_patterns')
        assert hasattr(self.extractor, 'dislike_patterns')
        assert hasattr(self.extractor, 'fact_patterns')
        assert hasattr(self.extractor, 'entity_history')
    
    # ============================================================================
    # USER NAME EXTRACTION TESTS
    # ============================================================================
    
    def test_extract_user_name_direct_statement(self):
        """Test extracting user name from direct statements."""
        test_cases = [
            "My name is John",
            "I'm Sarah",
            "I am Michael",
            "Call me Alex",
            "Hi, I'm Jessica"
        ]
        
        expected_names = ["John", "Sarah", "Michael", "Alex", "Jessica"]
        
        for text, expected_name in zip(test_cases, expected_names):
            result = self.extractor.extract_user_name(text)
            assert result == expected_name, f"Failed to extract '{expected_name}' from '{text}'"
    
    def test_extract_user_name_possessive_form(self):
        """Test extracting user name from possessive forms."""
        text = "John's favorite food is pizza"
        result = self.extractor.extract_user_name(text)
        assert result == "John"
    
    def test_extract_user_name_invalid_cases(self):
        """Test that invalid names are not extracted."""
        invalid_cases = [
            "I am 25 years old",  # Number, not name
            "My name is user",    # Generic term
            "Call me X",          # Too short
            "I'm someone",        # Generic term
            ""                    # Empty string
        ]
        
        for text in invalid_cases:
            result = self.extractor.extract_user_name(text)
            assert result is None, f"Should not extract name from '{text}'"
    
    def test_extract_entities_user_names(self):
        """Test extracting user name entities."""
        text = "Hi, I'm Alice and I love programming"
        entities = self.extractor.extract_entities(text)
        
        name_entities = [e for e in entities if e.entity_type == EntityType.USER_NAME]
        assert len(name_entities) >= 1
        assert name_entities[0].value == "Alice"
        assert name_entities[0].confidence > 0.5
    
    # ============================================================================
    # PREFERENCE EXTRACTION TESTS
    # ============================================================================
    
    def test_extract_preferences_likes(self):
        """Test extracting positive preferences."""
        test_cases = [
            ("I love pizza", "pizza", PreferenceType.LIKE),
            ("My favorite color is blue", "color is blue", PreferenceType.LIKE),
            ("I really like chocolate", "chocolate", PreferenceType.LIKE),
            ("Coffee is amazing", "Coffee", PreferenceType.LIKE),
            ("I'm a fan of jazz music", "jazz music", PreferenceType.LIKE)
        ]
        
        for text, expected_item, expected_type in test_cases:
            entities = self.extractor.extract_entities(text)
            preference_entities = [e for e in entities if e.entity_type == EntityType.PREFERENCE]
            
            assert len(preference_entities) >= 1, f"No preferences found in '{text}'"
            
            # Check if any preference entity contains the expected item
            found = any(expected_item.lower() in entity.value.lower() for entity in preference_entities)
            assert found, f"Expected preference '{expected_item}' not found in '{text}'"
    
    def test_extract_preferences_dislikes(self):
        """Test extracting negative preferences."""
        test_cases = [
            ("I hate broccoli", "broccoli", PreferenceType.DISLIKE),
            ("Spicy food is terrible", "Spicy food", PreferenceType.DISLIKE),
            ("I can't stand loud music", "loud music", PreferenceType.DISLIKE),
            ("Horror movies are awful", "Horror movies", PreferenceType.DISLIKE)
        ]
        
        for text, expected_item, expected_type in test_cases:
            entities = self.extractor.extract_entities(text)
            preference_entities = [e for e in entities if e.entity_type == EntityType.PREFERENCE]
            
            assert len(preference_entities) >= 1, f"No preferences found in '{text}'"
            
            # Check if any preference entity contains the expected item
            found = any(expected_item.lower() in entity.value.lower() for entity in preference_entities)
            assert found, f"Expected preference '{expected_item}' not found in '{text}'"
    
    def test_categorize_preference(self):
        """Test preference categorization."""
        test_cases = [
            ("I love ice cream", "ice cream", PreferenceType.LIKE),
            ("I hate vegetables", "vegetables", PreferenceType.DISLIKE),
            ("Pizza is okay", "pizza", PreferenceType.NEUTRAL),
            ("I sometimes enjoy reading", "reading", PreferenceType.NEUTRAL)
        ]
        
        for text, entity, expected_type in test_cases:
            result = self.extractor.categorize_preference(text, entity)
            assert result == expected_type, f"Expected {expected_type} for '{entity}' in '{text}', got {result}"
    
    def test_get_preference_confidence(self):
        """Test getting preference confidence scores."""
        # First, extract some preferences
        text = "I absolutely love chocolate and I hate broccoli"
        entities = self.extractor.extract_entities(text)
        
        # Update preferences
        self.extractor.update_user_preferences(text, entities)
        
        # Test confidence retrieval
        chocolate_confidence = self.extractor.get_preference_confidence("chocolate")
        broccoli_confidence = self.extractor.get_preference_confidence("broccoli")
        unknown_confidence = self.extractor.get_preference_confidence("unknown_item")
        
        assert chocolate_confidence > 0.0
        assert broccoli_confidence > 0.0
        assert unknown_confidence == 0.0
    
    # ============================================================================
    # FACT EXTRACTION TESTS
    # ============================================================================
    
    def test_extract_facts_age(self):
        """Test extracting age facts."""
        test_cases = [
            "I am 25 years old",
            "My age is 30",
            "I'm 22 years old"
        ]
        
        expected_ages = ["25", "30", "22"]
        
        for text, expected_age in zip(test_cases, expected_ages):
            facts = self.extractor.extract_facts(text)
            age_facts = [f for f in facts if "age" in f.content.lower()]
            
            assert len(age_facts) >= 1, f"No age facts found in '{text}'"
            assert expected_age in age_facts[0].content
    
    def test_extract_facts_location(self):
        """Test extracting location facts."""
        test_cases = [
            ("I live in New York", "New York"),
            ("I am from California", "California"),
            ("My city is Boston", "Boston")
        ]
        
        for text, expected_location in test_cases:
            facts = self.extractor.extract_facts(text)
            location_facts = [f for f in facts if "location" in f.content.lower()]
            
            assert len(location_facts) >= 1, f"No location facts found in '{text}'"
            assert expected_location in location_facts[0].content
    
    def test_extract_facts_occupation(self):
        """Test extracting occupation facts."""
        test_cases = [
            ("I work as a teacher", "teacher"),
            ("I'm a software engineer", "software engineer"),
            ("My job is doctor", "doctor")
        ]
        
        for text, expected_occupation in test_cases:
            facts = self.extractor.extract_facts(text)
            occupation_facts = [f for f in facts if "occupation" in f.content.lower()]
            
            assert len(occupation_facts) >= 1, f"No occupation facts found in '{text}'"
            assert expected_occupation in occupation_facts[0].content
    
    def test_extract_facts_invalid_age(self):
        """Test that invalid ages are not extracted."""
        invalid_cases = [
            "I am 200 years old",  # Too old
            "I am 0 years old",    # Too young
            "I am abc years old"   # Not a number
        ]
        
        for text in invalid_cases:
            facts = self.extractor.extract_facts(text)
            age_facts = [f for f in facts if "age" in f.content.lower()]
            assert len(age_facts) == 0, f"Should not extract age from '{text}'"
    
    # ============================================================================
    # ENTITY CONFLICT RESOLUTION TESTS
    # ============================================================================
    
    def test_resolve_entity_conflicts_higher_confidence(self):
        """Test resolving conflicts when new information has higher confidence."""
        # Create existing entity with lower confidence
        existing_entity = Entity(
            name="like_pizza",
            entity_type=EntityType.PREFERENCE,
            value="like: pizza",
            confidence=0.6,
            first_mentioned=datetime.now(),
            last_updated=datetime.now(),
            related_memories=[]
        )
        
        # New information with potentially higher confidence
        new_info = "I absolutely love pizza, it's amazing!"
        
        resolved_entity = self.extractor.resolve_entity_conflicts(existing_entity, new_info)
        
        # The resolved entity should maintain the same name and type
        assert resolved_entity.name == existing_entity.name
        assert resolved_entity.entity_type == existing_entity.entity_type
        assert resolved_entity.first_mentioned == existing_entity.first_mentioned
    
    def test_resolve_entity_conflicts_no_conflict(self):
        """Test resolving when there's no actual conflict."""
        existing_entity = Entity(
            name="like_pizza",
            entity_type=EntityType.PREFERENCE,
            value="like: pizza",
            confidence=0.8,
            first_mentioned=datetime.now(),
            last_updated=datetime.now(),
            related_memories=[]
        )
        
        # New information about different topic
        new_info = "I also enjoy reading books"
        
        resolved_entity = self.extractor.resolve_entity_conflicts(existing_entity, new_info)
        
        # Should return the same entity since no conflict
        assert resolved_entity.name == existing_entity.name
        assert resolved_entity.value == existing_entity.value
        assert resolved_entity.confidence == existing_entity.confidence
    
    # ============================================================================
    # COMPREHENSIVE ENTITY EXTRACTION TESTS
    # ============================================================================
    
    def test_extract_entities_comprehensive(self):
        """Test comprehensive entity extraction from complex text."""
        text = """
        Hi, I'm John and I'm 28 years old. I live in Seattle and work as a software engineer.
        I absolutely love pizza and chocolate, but I hate broccoli. 
        My favorite hobby is playing guitar.
        """
        
        entities = self.extractor.extract_entities(text)
        
        # Check that we extracted entities of different types
        name_entities = [e for e in entities if e.entity_type == EntityType.USER_NAME]
        preference_entities = [e for e in entities if e.entity_type == EntityType.PREFERENCE]
        fact_entities = [e for e in entities if e.entity_type == EntityType.FACT]
        
        assert len(name_entities) >= 1, "Should extract at least one name"
        assert len(preference_entities) >= 2, "Should extract at least two preferences"
        assert len(fact_entities) >= 2, "Should extract at least two facts"
        
        # Verify specific extractions
        assert any("John" in e.value for e in name_entities), "Should extract name 'John'"
        assert any("pizza" in e.value.lower() for e in preference_entities), "Should extract pizza preference"
        assert any("28" in e.value for e in fact_entities), "Should extract age 28"
    
    def test_extract_entities_empty_input(self):
        """Test extraction with empty or invalid input."""
        test_cases = ["", "   ", "a", "12"]
        
        for text in test_cases:
            entities = self.extractor.extract_entities(text)
            assert isinstance(entities, list), f"Should return list for input '{text}'"
    
    def test_update_user_preferences(self):
        """Test updating user preferences."""
        text = "I love chocolate and I hate vegetables"
        entities = self.extractor.extract_entities(text)
        
        # Update preferences
        self.extractor.update_user_preferences(text, entities)
        
        # Check that preferences were stored in history
        assert len(self.extractor.entity_history) > 0
        
        # Check that we can retrieve preference confidence
        chocolate_confidence = self.extractor.get_preference_confidence("chocolate")
        assert chocolate_confidence > 0.0
    
    # ============================================================================
    # VALIDATION TESTS
    # ============================================================================
    
    def test_is_valid_name(self):
        """Test name validation logic."""
        valid_names = ["John", "Sarah", "Michael Johnson", "Anna"]
        invalid_names = ["", "X", "user", "someone", "123", "a" * 60]
        
        for name in valid_names:
            assert self.extractor._is_valid_name(name), f"'{name}' should be valid"
        
        for name in invalid_names:
            assert not self.extractor._is_valid_name(name), f"'{name}' should be invalid"
    
    def test_is_valid_preference(self):
        """Test preference validation logic."""
        valid_prefs = ["pizza", "chocolate ice cream", "playing guitar", "reading books"]
        invalid_prefs = ["", "it", "that", "something", "a", "!!!", "x" * 150]
        
        for pref in valid_prefs:
            assert self.extractor._is_valid_preference(pref), f"'{pref}' should be valid"
        
        for pref in invalid_prefs:
            assert not self.extractor._is_valid_preference(pref), f"'{pref}' should be invalid"
    
    def test_is_valid_fact(self):
        """Test fact validation logic."""
        # Age facts
        assert self.extractor._is_valid_fact("25", "age")
        assert self.extractor._is_valid_fact("30", "age")
        assert not self.extractor._is_valid_fact("200", "age")  # Too old
        assert not self.extractor._is_valid_fact("0", "age")    # Too young
        
        # Location facts
        assert self.extractor._is_valid_fact("Seattle", "location")
        assert self.extractor._is_valid_fact("New York", "location")
        assert not self.extractor._is_valid_fact("x", "location")  # Too short
        
        # Occupation facts
        assert self.extractor._is_valid_fact("teacher", "occupation")
        assert self.extractor._is_valid_fact("software engineer", "occupation")
        assert not self.extractor._is_valid_fact("", "occupation")  # Empty
    
    # ============================================================================
    # CONFIDENCE SCORING TESTS
    # ============================================================================
    
    def test_confidence_scoring_names(self):
        """Test confidence scoring for name extraction."""
        high_confidence_cases = [
            "My name is John",
            "I'm Sarah",
            "Call me Michael"
        ]
        
        for text in high_confidence_cases:
            entities = self.extractor.extract_entities(text)
            name_entities = [e for e in entities if e.entity_type == EntityType.USER_NAME]
            
            if name_entities:
                assert name_entities[0].confidence > 0.7, f"Should have high confidence for '{text}'"
    
    def test_confidence_scoring_preferences(self):
        """Test confidence scoring for preference extraction."""
        high_confidence_cases = [
            "I absolutely love pizza",
            "I hate broccoli",
            "Pizza is my favorite food"
        ]
        
        for text in high_confidence_cases:
            entities = self.extractor.extract_entities(text)
            pref_entities = [e for e in entities if e.entity_type == EntityType.PREFERENCE]
            
            if pref_entities:
                assert pref_entities[0].confidence > 0.6, f"Should have reasonable confidence for '{text}'"
    
    def test_deduplication(self):
        """Test entity deduplication."""
        # Text that might generate duplicate entities
        text = "I love pizza. Pizza is amazing. I really love pizza."
        entities = self.extractor.extract_entities(text)
        
        # Check that we don't have excessive duplicates
        pizza_entities = [e for e in entities if "pizza" in e.value.lower()]
        
        # Should have some pizza entities but not excessive duplicates
        assert len(pizza_entities) >= 1, "Should extract pizza preferences"
        assert len(pizza_entities) <= 3, "Should not have excessive duplicates"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestEntityExtractorIntegration:
    """Integration tests for EntityExtractor with realistic scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = EntityExtractor()
    
    def test_conversation_scenario(self):
        """Test entity extraction from a realistic conversation scenario."""
        conversation_turns = [
            "Hi there! I'm Alex and I'm 26 years old.",
            "I live in Portland and work as a graphic designer.",
            "I absolutely love coffee and pizza, but I can't stand mushrooms.",
            "My favorite hobby is photography, and I also enjoy hiking.",
            "I studied art in college and I have a cat named Whiskers."
        ]
        
        all_entities = []
        for turn in conversation_turns:
            entities = self.extractor.extract_entities(turn)
            all_entities.extend(entities)
            self.extractor.update_user_preferences(turn, entities)
        
        # Verify we extracted comprehensive information
        name_entities = [e for e in all_entities if e.entity_type == EntityType.USER_NAME]
        preference_entities = [e for e in all_entities if e.entity_type == EntityType.PREFERENCE]
        fact_entities = [e for e in all_entities if e.entity_type == EntityType.FACT]
        
        assert len(name_entities) >= 1, "Should extract user name"
        assert len(preference_entities) >= 3, "Should extract multiple preferences"
        assert len(fact_entities) >= 3, "Should extract multiple facts"
        
        # Test preference confidence retrieval
        coffee_confidence = self.extractor.get_preference_confidence("coffee")
        mushroom_confidence = self.extractor.get_preference_confidence("mushrooms")
        
        assert coffee_confidence > 0.0, "Should have confidence for coffee preference"
        assert mushroom_confidence > 0.0, "Should have confidence for mushroom preference"
    
    def test_preference_conflict_resolution(self):
        """Test resolving conflicting preferences over time."""
        # Initial preference
        initial_text = "I like chocolate"
        initial_entities = self.extractor.extract_entities(initial_text)
        self.extractor.update_user_preferences(initial_text, initial_entities)
        
        # Conflicting preference with higher confidence
        conflicting_text = "Actually, I absolutely hate chocolate now"
        conflicting_entities = self.extractor.extract_entities(conflicting_text)
        
        # Find the chocolate preference entity
        chocolate_entities = [e for e in initial_entities if "chocolate" in e.value.lower()]
        if chocolate_entities:
            resolved = self.extractor.resolve_entity_conflicts(chocolate_entities[0], conflicting_text)
            
            # The resolved entity should reflect the conflict resolution
            assert resolved is not None
            assert resolved.last_updated > chocolate_entities[0].last_updated