#!/usr/bin/env python3
"""
AI VTuber Configuration Validation Tool

This script validates the AI VTuber system configuration file, checking:
- Configuration file syntax and structure
- Emotion-to-hotkey mappings against available VTube Studio hotkeys
- GPT-SoVITS connectivity and service availability
- System requirements and dependencies

Usage:
    python tools/validate_config.py [--config CONFIG_FILE] [--fix-issues]

Requirements:
    - Valid configuration file (config.json by default)
    - VTube Studio running (for hotkey validation)
    - GPT-SoVITS service running (for voice cloning validation)
"""

import argparse
import asyncio
import json
import logging
import sys
import aiohttp
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import SystemConfig, load_config
from vts_client import VTSClient


class ConfigValidationResult:
    """Container for validation results"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.recommendations: List[str] = []
    
    def add_error(self, message: str) -> None:
        """Add an error message"""
        self.errors.append(message)
    
    def add_warning(self, message: str) -> None:
        """Add a warning message"""
        self.warnings.append(message)
    
    def add_info(self, message: str) -> None:
        """Add an info message"""
        self.info.append(message)
    
    def add_recommendation(self, message: str) -> None:
        """Add a recommendation"""
        self.recommendations.append(message)
    
    def has_errors(self) -> bool:
        """Check if there are any errors"""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if there are any warnings"""
        return len(self.warnings) > 0
    
    def is_valid(self) -> bool:
        """Check if configuration is valid (no errors)"""
        return not self.has_errors()


class ConfigValidator:
    """AI VTuber configuration validator"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the configuration validator
        
        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        self.config: Optional[SystemConfig] = None
        self.logger = self._setup_logging()
        self.result = ConfigValidationResult()
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the validator"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        # Create console handler if not already exists
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(levelname)s: %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    async def validate_all(self) -> ConfigValidationResult:
        """
        Perform comprehensive configuration validation
        
        Returns:
            ConfigValidationResult with all validation results
        """
        self.logger.info(f"Validating configuration file: {self.config_path}")
        
        # Step 1: Validate configuration file structure
        if not await self._validate_config_file():
            return self.result
        
        # Step 2: Validate basic configuration values
        await self._validate_basic_config()
        
        # Step 3: Validate emotional intelligence settings
        await self._validate_emotional_intelligence_config()
        
        # Step 4: Validate VTube Studio hotkey mappings
        await self._validate_vts_hotkey_mappings()
        
        # Step 5: Validate GPT-SoVITS connectivity
        await self._validate_sovits_connectivity()
        
        # Step 6: Generate recommendations
        await self._generate_recommendations()
        
        return self.result
    
    async def _validate_config_file(self) -> bool:
        """
        Validate configuration file exists and can be loaded
        
        Returns:
            True if config file is valid, False otherwise
        """
        try:
            # Check if file exists
            if not Path(self.config_path).exists():
                self.result.add_error(f"Configuration file not found: {self.config_path}")
                return False
            
            # Try to load configuration
            self.config = load_config(self.config_path)
            self.result.add_info(f"Configuration file loaded successfully: {self.config_path}")
            return True
            
        except ValueError as e:
            self.result.add_error(f"Invalid configuration file: {e}")
            return False
        except Exception as e:
            self.result.add_error(f"Failed to load configuration: {e}")
            return False
    
    async def _validate_basic_config(self) -> None:
        """Validate basic configuration values"""
        if not self.config:
            return
        
        # Validate Ollama configuration
        if not self.config.ollama_url:
            self.result.add_error("ollama_url is required")
        elif not self._is_valid_url(self.config.ollama_url):
            self.result.add_error(f"Invalid ollama_url format: {self.config.ollama_url}")
        
        if not self.config.ollama_model:
            self.result.add_error("ollama_model is required")
        
        # Validate TTS configuration
        if not self.config.tts_voice:
            self.result.add_error("tts_voice is required")
        
        # Validate VTS configuration
        if not isinstance(self.config.vts_port, int) or self.config.vts_port <= 0:
            self.result.add_error("vts_port must be a positive integer")
        
        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.config.log_level not in valid_log_levels:
            self.result.add_error(f"Invalid log_level. Must be one of: {valid_log_levels}")
        
        self.result.add_info("Basic configuration validation completed")
    
    async def _validate_emotional_intelligence_config(self) -> None:
        """Validate emotional intelligence specific configuration"""
        if not self.config:
            return
        
        # Check if emotional intelligence is enabled
        if not self.config.enable_emotional_intelligence:
            self.result.add_info("Emotional intelligence is disabled - skipping related validations")
            return
        
        # Validate GPT-SoVITS configuration
        if self.config.enable_voice_cloning:
            if not self.config.sovits_url:
                self.result.add_error("sovits_url is required when voice cloning is enabled")
            elif not self._is_valid_url(self.config.sovits_url):
                self.result.add_error(f"Invalid sovits_url format: {self.config.sovits_url}")
            
            if self.config.sovits_timeout <= 0:
                self.result.add_error("sovits_timeout must be positive")
            
            if not self.config.sovits_language:
                self.result.add_error("sovits_language is required when voice cloning is enabled")
        
        # Validate expression control configuration
        if self.config.enable_expression_control:
            if not isinstance(self.config.emotion_hotkey_map, dict):
                self.result.add_error("emotion_hotkey_map must be a dictionary when expression control is enabled")
            else:
                await self._validate_emotion_mappings()
            
            if self.config.expression_timeout <= 0:
                self.result.add_error("expression_timeout must be positive")
            
            valid_emotions = {"neutral", "happy", "angry", "sad", "surprised"}
            if self.config.default_emotion not in valid_emotions:
                self.result.add_error(f"default_emotion must be one of: {valid_emotions}")
        
        self.result.add_info("Emotional intelligence configuration validation completed")
    
    async def _validate_emotion_mappings(self) -> None:
        """Validate emotion to hotkey mappings"""
        if not self.config or not self.config.emotion_hotkey_map:
            return
        
        valid_emotions = {"neutral", "happy", "angry", "sad", "surprised"}
        
        # Check for required emotions
        for emotion in valid_emotions:
            if emotion not in self.config.emotion_hotkey_map:
                self.result.add_warning(f"Missing emotion mapping for '{emotion}'")
        
        # Check for invalid emotions
        for emotion in self.config.emotion_hotkey_map.keys():
            if emotion not in valid_emotions:
                self.result.add_error(f"Invalid emotion '{emotion}'. Valid emotions: {valid_emotions}")
        
        # Count mapped emotions
        mapped_count = sum(1 for hotkey_id in self.config.emotion_hotkey_map.values() if hotkey_id)
        if mapped_count == 0:
            self.result.add_warning("No emotions are mapped to hotkeys - expression control will not work")
        else:
            self.result.add_info(f"{mapped_count} emotions are mapped to hotkeys")
    
    async def _validate_vts_hotkey_mappings(self) -> None:
        """Validate VTube Studio hotkey mappings against available hotkeys"""
        if not self.config or not self.config.enable_expression_control:
            return
        
        if not self.config.emotion_hotkey_map:
            self.result.add_warning("No emotion hotkey mappings to validate")
            return
        
        try:
            self.logger.info("Connecting to VTube Studio to validate hotkey mappings...")
            
            # Create VTS client
            vts_client = VTSClient(port=self.config.vts_port, emotion_hotkey_map=self.config.emotion_hotkey_map)
            
            # Connect and authenticate
            if not await vts_client.connect():
                self.result.add_warning("Cannot connect to VTube Studio - hotkey validation skipped")
                self.result.add_recommendation("Ensure VTube Studio is running and API access is enabled")
                return
            
            if not await vts_client.authenticate():
                self.result.add_warning("Cannot authenticate with VTube Studio - hotkey validation skipped")
                self.result.add_recommendation("Accept the authentication request in VTube Studio")
                await vts_client.disconnect()
                return
            
            # Validate hotkey mappings
            validation_results = await vts_client.validate_hotkey_mappings(self.config.emotion_hotkey_map)
            
            valid_count = 0
            invalid_count = 0
            
            for emotion, is_valid in validation_results.items():
                hotkey_id = self.config.emotion_hotkey_map.get(emotion, "")
                
                if not hotkey_id:  # Empty mapping is valid
                    continue
                
                if is_valid:
                    valid_count += 1
                    self.result.add_info(f"Valid hotkey mapping: {emotion} -> {hotkey_id}")
                else:
                    invalid_count += 1
                    self.result.add_error(f"Invalid hotkey mapping: {emotion} -> {hotkey_id} (hotkey not found)")
            
            if invalid_count == 0:
                self.result.add_info(f"All {valid_count} hotkey mappings are valid")
            else:
                self.result.add_error(f"{invalid_count} invalid hotkey mappings found")
                self.result.add_recommendation("Run 'python tools/list_vts_hotkeys.py' to see available hotkeys")
            
            await vts_client.disconnect()
            
        except Exception as e:
            self.result.add_warning(f"VTube Studio hotkey validation failed: {e}")
            self.result.add_recommendation("Ensure VTube Studio is running and accessible")
    
    async def _validate_sovits_connectivity(self) -> None:
        """Validate GPT-SoVITS service connectivity"""
        if not self.config or not self.config.enable_voice_cloning:
            return
        
        try:
            self.logger.info("Testing GPT-SoVITS connectivity...")
            
            # Test basic connectivity
            timeout = aiohttp.ClientTimeout(total=self.config.sovits_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Try to connect to the service
                test_url = f"{self.config.sovits_url.rstrip('/')}/health"
                
                try:
                    async with session.get(test_url) as response:
                        if response.status == 200:
                            self.result.add_info("GPT-SoVITS service is accessible")
                        else:
                            self.result.add_warning(f"GPT-SoVITS service returned status {response.status}")
                except aiohttp.ClientConnectorError:
                    # Try the main endpoint if health endpoint doesn't exist
                    test_params = {
                        "text": "测试",
                        "text_lang": self.config.sovits_language
                    }
                    
                    try:
                        async with session.get(self.config.sovits_url, params=test_params) as response:
                            if response.status in [200, 400]:  # 400 might be expected for test text
                                self.result.add_info("GPT-SoVITS service is accessible")
                            else:
                                self.result.add_warning(f"GPT-SoVITS service returned status {response.status}")
                    except Exception:
                        self.result.add_error(f"Cannot connect to GPT-SoVITS service at {self.config.sovits_url}")
                        self.result.add_recommendation("Ensure GPT-SoVITS service is running and accessible")
                        
                        if self.config.fallback_to_edge_tts:
                            self.result.add_info("Edge-TTS fallback is enabled - voice generation will still work")
                        else:
                            self.result.add_warning("Edge-TTS fallback is disabled - voice generation may fail")
        
        except Exception as e:
            self.result.add_error(f"GPT-SoVITS connectivity test failed: {e}")
            self.result.add_recommendation("Check GPT-SoVITS service configuration and network connectivity")
    
    async def _generate_recommendations(self) -> None:
        """Generate setup and optimization recommendations"""
        if not self.config:
            return
        
        # Feature enablement recommendations
        if not self.config.enable_emotional_intelligence:
            self.result.add_recommendation("Consider enabling emotional intelligence for more engaging interactions")
        
        if self.config.enable_emotional_intelligence and not self.config.enable_voice_cloning:
            self.result.add_recommendation("Consider enabling voice cloning for character-specific voice")
        
        if self.config.enable_emotional_intelligence and not self.config.enable_expression_control:
            self.result.add_recommendation("Consider enabling expression control for visual emotion feedback")
        
        # Performance recommendations
        if self.config.sovits_timeout > 15.0:
            self.result.add_recommendation("Consider reducing sovits_timeout for better responsiveness")
        
        if self.config.expression_timeout > 1.0:
            self.result.add_recommendation("Consider reducing expression_timeout for more responsive expressions")
        
        # Configuration completeness recommendations
        if self.config.enable_expression_control and self.config.emotion_hotkey_map:
            empty_mappings = [emotion for emotion, hotkey_id in self.config.emotion_hotkey_map.items() if not hotkey_id]
            if empty_mappings:
                self.result.add_recommendation(f"Consider mapping hotkeys for emotions: {', '.join(empty_mappings)}")
    
    def _is_valid_url(self, url: str) -> bool:
        """
        Check if a URL is valid
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid, False otherwise
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def display_results(self, show_info: bool = True) -> None:
        """
        Display validation results
        
        Args:
            show_info: Whether to show info messages
        """
        print("\n" + "=" * 60)
        print("AI VTUBER CONFIGURATION VALIDATION RESULTS")
        print("=" * 60)
        
        # Display errors
        if self.result.errors:
            print(f"\n❌ ERRORS ({len(self.result.errors)}):")
            for i, error in enumerate(self.result.errors, 1):
                print(f"  {i}. {error}")
        
        # Display warnings
        if self.result.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.result.warnings)}):")
            for i, warning in enumerate(self.result.warnings, 1):
                print(f"  {i}. {warning}")
        
        # Display info messages
        if show_info and self.result.info:
            print(f"\n✅ INFO ({len(self.result.info)}):")
            for i, info in enumerate(self.result.info, 1):
                print(f"  {i}. {info}")
        
        # Display recommendations
        if self.result.recommendations:
            print(f"\n💡 RECOMMENDATIONS ({len(self.result.recommendations)}):")
            for i, recommendation in enumerate(self.result.recommendations, 1):
                print(f"  {i}. {recommendation}")
        
        # Display summary
        print(f"\n" + "=" * 60)
        if self.result.is_valid():
            print("✅ CONFIGURATION IS VALID")
            if self.result.warnings:
                print(f"   (with {len(self.result.warnings)} warnings)")
        else:
            print("❌ CONFIGURATION HAS ERRORS")
            print(f"   {len(self.result.errors)} errors, {len(self.result.warnings)} warnings")
        print("=" * 60)


async def main():
    """Main function for the configuration validator"""
    parser = argparse.ArgumentParser(
        description="Validate AI VTuber system configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/validate_config.py
  python tools/validate_config.py --config my_config.json
  python tools/validate_config.py --quiet
        """
    )
    
    parser.add_argument(
        "--config",
        default="config.json",
        help="Configuration file to validate (default: config.json)"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Show only errors and warnings (suppress info messages)"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )
    
    args = parser.parse_args()
    
    # Create validator
    validator = ConfigValidator(config_path=args.config)
    
    # Suppress logging if quiet mode
    if args.quiet:
        validator.logger.setLevel(logging.ERROR)
    
    # Validate configuration
    result = await validator.validate_all()
    
    # Display results
    if args.json:
        # Output JSON format
        json_result = {
            "valid": result.is_valid(),
            "errors": result.errors,
            "warnings": result.warnings,
            "info": result.info,
            "recommendations": result.recommendations
        }
        print(json.dumps(json_result, indent=2, ensure_ascii=False))
    else:
        # Display human-readable format
        validator.display_results(show_info=not args.quiet)
    
    # Exit with appropriate code
    if result.has_errors():
        sys.exit(1)
    elif result.has_warnings():
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nValidation cancelled by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error during validation: {e}", file=sys.stderr)
        sys.exit(1)