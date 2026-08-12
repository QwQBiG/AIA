#!/usr/bin/env python3
"""
Test script to verify hotkey functionality
"""

import sys
import os
import logging

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.config import load_config
from src.safety_manager import SafetyManager

def test_safety_manager_hotkey():
    """Test SafetyManager F9 hotkey setup"""
    print("Testing SafetyManager F9 hotkey setup...")
    
    try:
        # Load config
        config = load_config("config.json")
        
        # Get safety config
        safety_config = {
            'enable_emergency_hotkey': True,
            'emergency_key': 'F9',  # Use 'F9' instead of '<f9>' for testing
            'enable_tts_announcement': False  # Disable TTS for testing
        }
        
        # Create SafetyManager
        safety_manager = SafetyManager(config=safety_config)
        
        # Test initialization
        print(f"✓ SafetyManager created")
        print(f"  Emergency key: {safety_manager.emergency_key}")
        print(f"  Hotkey enabled: {safety_manager.hotkey_enabled}")
        print(f"  Emergency active: {safety_manager.emergency_active}")
        
        # Test emergency stop
        print("\nTesting emergency stop...")
        safety_manager.trigger_emergency_stop()
        print(f"  Emergency active after trigger: {safety_manager.emergency_active}")
        
        # Test reset
        print("\nTesting emergency reset...")
        safety_manager.reset_emergency_state()
        print(f"  Emergency active after reset: {safety_manager.emergency_active}")
        
        print("✓ SafetyManager test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ SafetyManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_emotion_hotkey_config():
    """Test emotion hotkey configuration"""
    print("\nTesting emotion hotkey configuration...")
    
    try:
        # Load config
        config = load_config("config.json")
        
        # Check emotion hotkey mapping
        emotion_hotkey_map = getattr(config, 'emotion_hotkey_map', {})
        print(f"✓ Emotion hotkey map loaded: {emotion_hotkey_map}")
        
        # Verify expected mappings
        expected_emotions = ['neutral', 'happy', 'angry', 'sad', 'surprised']
        expected_keys = ['F1', 'F2', 'F3', 'F4', 'F5']
        
        for emotion, key in zip(expected_emotions, expected_keys):
            if emotion in emotion_hotkey_map:
                actual_key = emotion_hotkey_map[emotion]
                print(f"  {emotion}: {actual_key} (expected: {key})")
                if actual_key == key:
                    print(f"    ✓ Correct mapping")
                else:
                    print(f"    ⚠ Different mapping")
            else:
                print(f"  {emotion}: NOT FOUND (expected: {key})")
        
        print("✓ Emotion hotkey configuration test completed")
        return True
        
    except Exception as e:
        print(f"✗ Emotion hotkey configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("=== Hotkey Functionality Test ===")
    
    # Test SafetyManager
    safety_test = test_safety_manager_hotkey()
    
    # Test emotion hotkey config
    emotion_test = test_emotion_hotkey_config()
    
    # Summary
    print("\n=== Test Summary ===")
    if safety_test:
        print("✓ SafetyManager F9 hotkey: PASS")
    else:
        print("✗ SafetyManager F9 hotkey: FAIL")
    
    if emotion_test:
        print("✓ Emotion hotkey configuration: PASS")
    else:
        print("✗ Emotion hotkey configuration: FAIL")
    
    if safety_test and emotion_test:
        print("\n🎉 All hotkey tests passed!")
        print("\nTo test the hotkeys in the actual application:")
        print("1. Run: python main.py")
        print("2. Press F1-F5 to trigger emotions (when GUI has focus)")
        print("3. Press F9 to trigger emergency stop (global hotkey)")
        return 0
    else:
        print("\n❌ Some hotkey tests failed!")
        print("Please check the configuration and dependencies.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)