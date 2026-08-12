"""
Warmup Manager for AI VTuber System

This module handles system warmup to reduce first-interaction latency.
It pre-loads LLM and TTS models into memory during system startup.

Requirements covered:
- 3.1: LLM warmup on system start
- 3.2: TTS warmup on system start
- 3.3: Warmup status logging
- 3.4: Non-blocking warmup (continue startup on failure)
"""

import asyncio
import logging
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.llm_client import LLMClient
    from src.tts_player import TTSPlayer


class WarmupManager:
    """
    Manages system warmup for LLM and TTS components.
    
    Warmup pre-loads models into memory to reduce latency on first user interaction.
    Warmup failures are logged but do not block system startup.
    """
    
    # Short test messages for warmup
    LLM_WARMUP_MESSAGE = "你好"
    TTS_WARMUP_TEXT = "你好"
    
    def __init__(
        self, 
        llm_client: "LLMClient", 
        tts_player: "TTSPlayer",
        timeout: float = 10.0
    ):
        """
        Initialize the WarmupManager.
        
        Args:
            llm_client: LLMClient instance for LLM warmup
            tts_player: TTSPlayer instance for TTS warmup
            timeout: Maximum time to wait for warmup (seconds)
        """
        self.llm_client = llm_client
        self.tts_player = tts_player
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        
        # Warmup status tracking
        self._warmup_results: Dict[str, bool] = {
            "llm": False,
            "tts": False
        }
        self._warmup_completed = False
    
    async def warmup(self) -> Dict[str, bool]:
        """
        Execute system warmup for LLM and TTS components.
        
        Runs warmup tasks in parallel with a timeout. Failures are logged
        but do not raise exceptions (non-blocking warmup per Requirement 3.4).
        
        Returns:
            Dict with warmup results: {"llm": True/False, "tts": True/False}
        """
        self.logger.info("=== Starting System Warmup ===")
        self.logger.info(f"Warmup timeout: {self.timeout}s")
        
        try:
            # Run LLM and TTS warmup in parallel with timeout
            async with asyncio.timeout(self.timeout):
                llm_task = asyncio.create_task(self._warmup_llm())
                tts_task = asyncio.create_task(self._warmup_tts())
                
                # Wait for both tasks to complete
                results = await asyncio.gather(
                    llm_task, 
                    tts_task, 
                    return_exceptions=True
                )
                
                # Process results
                self._warmup_results["llm"] = (
                    results[0] is True if not isinstance(results[0], Exception) else False
                )
                self._warmup_results["tts"] = (
                    results[1] is True if not isinstance(results[1], Exception) else False
                )
                
        except asyncio.TimeoutError:
            self.logger.warning(f"Warmup timed out after {self.timeout}s")
            # Results remain False for any incomplete warmup
        except Exception as e:
            self.logger.error(f"Unexpected error during warmup: {e}")
        
        self._warmup_completed = True
        self._log_warmup_summary()
        
        return self._warmup_results
    
    async def _warmup_llm(self) -> bool:
        """
        Warmup the LLM by sending a short test request.
        
        This loads the model into GPU memory for faster subsequent responses.
        
        Returns:
            bool: True if warmup successful, False otherwise
        """
        self.logger.info("Warming up LLM...")
        
        try:
            # Send a simple request to load the model
            # Use non-streaming mode for warmup (simpler and faster)
            response = await self.llm_client.generate_response(
                self.LLM_WARMUP_MESSAGE, 
                return_structured=False
            )
            
            if response:
                self.logger.info("✓ LLM warmup successful - model loaded into memory")
                return True
            else:
                self.logger.warning("✗ LLM warmup returned empty response")
                return False
                
        except Exception as e:
            self.logger.warning(f"✗ LLM warmup failed: {e}")
            return False
    
    async def _warmup_tts(self) -> bool:
        """
        Warmup the TTS by generating a short test audio.
        
        This loads the TTS model and initializes audio processing.
        
        Returns:
            bool: True if warmup successful, False otherwise
        """
        self.logger.info("Warming up TTS...")
        
        try:
            # Generate a short test audio
            audio_path = await self.tts_player.generate_audio(self.TTS_WARMUP_TEXT)
            
            if audio_path:
                self.logger.info("✓ TTS warmup successful - model loaded")
                # Clean up the test audio file
                self.tts_player.cleanup_temp_file(audio_path)
                return True
            else:
                self.logger.warning("✗ TTS warmup returned no audio path")
                return False
                
        except Exception as e:
            self.logger.warning(f"✗ TTS warmup failed: {e}")
            return False
    
    def _log_warmup_summary(self) -> None:
        """Log a summary of warmup results (Requirement 3.3)."""
        self.logger.info("=== Warmup Summary ===")
        
        successful = sum(1 for v in self._warmup_results.values() if v)
        total = len(self._warmup_results)
        
        for component, success in self._warmup_results.items():
            status = "✓ Ready" if success else "✗ Not warmed up"
            self.logger.info(f"  {component.upper()}: {status}")
        
        if successful == total:
            self.logger.info(f"Warmup completed: {successful}/{total} components ready")
            self.logger.info("System is optimized for fast first response")
        elif successful > 0:
            self.logger.warning(f"Partial warmup: {successful}/{total} components ready")
            self.logger.warning("First interaction may have some delay")
        else:
            self.logger.warning("Warmup failed: No components warmed up")
            self.logger.warning("First interaction will have higher latency")
    
    @property
    def is_warmed_up(self) -> bool:
        """Check if warmup has been completed (regardless of success)."""
        return self._warmup_completed
    
    @property
    def warmup_results(self) -> Dict[str, bool]:
        """Get the warmup results."""
        return self._warmup_results.copy()
    
    def get_status(self) -> Dict[str, any]:
        """
        Get detailed warmup status.
        
        Returns:
            Dict with warmup status information
        """
        return {
            "completed": self._warmup_completed,
            "results": self._warmup_results.copy(),
            "llm_ready": self._warmup_results.get("llm", False),
            "tts_ready": self._warmup_results.get("tts", False),
            "all_ready": all(self._warmup_results.values())
        }
