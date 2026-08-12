#!/usr/bin/env python3
"""
Performance Measurement Tool for AI VTuber System

This script measures key performance metrics for the streaming and pipelining
optimization, including:
- First token response time (time to receive first token from LLM)
- First audio playback time (time from user input to first audio playing)
- End-to-end latency comparison between streaming and non-streaming modes

Usage:
    python tools/measure_performance.py
    python tools/measure_performance.py --config custom_config.json
    python tools/measure_performance.py --iterations 5
    python tools/measure_performance.py --test-message "你好"
    python tools/measure_performance.py --skip-warmup
    python tools/measure_performance.py --json

Requirements:
    - Ollama service must be running
    - GPT-SoVITS service must be running (or Edge-TTS fallback enabled)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import SystemConfig, load_config
from src.llm_client import LLMClient, StreamHandler
from src.tts_player import TTSPlayer
from src.stream_processor import StreamProcessor
from src.tts_pipeline import TTSPipeline


@dataclass
class PerformanceMetrics:
    """Container for performance measurement results."""
    # LLM metrics
    first_token_time: float = 0.0  # Time to receive first token (seconds)
    emotion_detection_time: float = 0.0  # Time to detect emotion tag (seconds)
    full_response_time: float = 0.0  # Time to receive complete response (seconds)
    
    # TTS metrics
    first_audio_generation_time: float = 0.0  # Time to generate first audio (seconds)
    first_audio_playback_start: float = 0.0  # Time from start to first audio playing (seconds)
    
    # Overall metrics
    total_tokens: int = 0
    total_sentences: int = 0
    response_length: int = 0
    
    # Mode info
    mode: str = "streaming"  # "streaming" or "non-streaming"
    test_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output."""
        return asdict(self)


class PerformanceMeasurementHandler(StreamHandler):
    """StreamHandler implementation that records timing metrics."""
    
    def __init__(self, start_time: float):
        self.start_time = start_time
        self.first_token_time: Optional[float] = None
        self.emotion_detection_time: Optional[float] = None
        self.complete_time: Optional[float] = None
        self.token_count = 0
        self.detected_emotion: Optional[str] = None
        self.received_text = ""
    
    def on_emotion_detected(self, emotion: str) -> None:
        """Record time when emotion is detected."""
        if self.emotion_detection_time is None:
            self.emotion_detection_time = time.perf_counter() - self.start_time
        self.detected_emotion = emotion
    
    def on_token_received(self, token: str) -> None:
        """Record time when first token is received."""
        if self.first_token_time is None:
            self.first_token_time = time.perf_counter() - self.start_time
        self.token_count += 1
        self.received_text += token
    
    def on_stream_complete(self) -> None:
        """Record time when stream completes."""
        self.complete_time = time.perf_counter() - self.start_time


class PerformanceMeasurer:
    """Main class for measuring system performance."""
    
    DEFAULT_TEST_MESSAGE = "你好，请简单介绍一下你自己。"
    
    def __init__(self, config: SystemConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.llm_client: Optional[LLMClient] = None
        self.tts_player: Optional[TTSPlayer] = None
    
    async def initialize(self) -> bool:
        """Initialize LLM client and TTS player."""
        try:
            # Initialize LLM client
            self.llm_client = LLMClient(
                base_url=self.config.ollama_url,
                model=self.config.ollama_model
            )
            
            # Test LLM connection
            connected = await self.llm_client.connect()
            if not connected:
                self.logger.error("Failed to connect to Ollama service")
                return False
            
            self.logger.info(f"Connected to Ollama at {self.config.ollama_url}")
            
            # Initialize TTS player
            self.tts_player = TTSPlayer(
                voice=self.config.tts_voice,
                config=self.config
            )
            self.logger.info("TTS player initialized")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return False
    
    async def warmup(self, timeout: float = 30.0) -> Dict[str, bool]:
        """
        Perform warmup to load models into memory.
        
        Args:
            timeout: Maximum time to wait for warmup (seconds)
            
        Returns:
            Dictionary with warmup status for each component
        """
        results = {"llm": False, "tts": False}
        
        self.logger.info("Starting warmup...")
        warmup_start = time.perf_counter()
        
        try:
            # Warmup LLM
            self.logger.info("Warming up LLM...")
            llm_start = time.perf_counter()
            await self.llm_client.generate_response("你好", return_structured=False)
            llm_time = time.perf_counter() - llm_start
            results["llm"] = True
            self.logger.info(f"LLM warmup completed in {llm_time:.2f}s")
            
        except Exception as e:
            self.logger.warning(f"LLM warmup failed: {e}")
        
        try:
            # Warmup TTS
            self.logger.info("Warming up TTS...")
            tts_start = time.perf_counter()
            audio_path = await self.tts_player.generate_audio("你好")
            tts_time = time.perf_counter() - tts_start
            self.tts_player.cleanup_temp_file(audio_path)
            results["tts"] = True
            self.logger.info(f"TTS warmup completed in {tts_time:.2f}s")
            
        except Exception as e:
            self.logger.warning(f"TTS warmup failed: {e}")
        
        total_time = time.perf_counter() - warmup_start
        self.logger.info(f"Warmup completed in {total_time:.2f}s - LLM: {results['llm']}, TTS: {results['tts']}")
        
        return results

    async def measure_streaming_mode(self, test_message: str) -> PerformanceMetrics:
        """
        Measure performance in streaming mode.
        
        Args:
            test_message: Message to send to LLM
            
        Returns:
            PerformanceMetrics with timing data
        """
        metrics = PerformanceMetrics(mode="streaming", test_message=test_message)
        
        self.logger.info(f"Measuring streaming mode with message: {test_message}")
        
        # Track sentences for TTS timing
        sentences: List[str] = []
        first_sentence_time: Optional[float] = None
        first_audio_gen_time: Optional[float] = None
        
        def on_sentence(sentence: str):
            nonlocal first_sentence_time
            if first_sentence_time is None:
                first_sentence_time = time.perf_counter() - start_time
            sentences.append(sentence)
        
        # Create stream processor
        stream_processor = StreamProcessor(
            on_sentence=on_sentence,
            min_sentence_length=self.config.performance.stream_chunk_min_size
        )
        
        # Create measurement handler
        start_time = time.perf_counter()
        handler = PerformanceMeasurementHandler(start_time)
        
        try:
            # Enable streaming mode
            self.llm_client.enable_streaming = True
            
            # Generate streaming response
            response = await self.llm_client.generate_response_stream(
                test_message, 
                handler
            )
            
            # Record LLM metrics
            metrics.first_token_time = handler.first_token_time or 0.0
            metrics.emotion_detection_time = handler.emotion_detection_time or 0.0
            metrics.full_response_time = handler.complete_time or 0.0
            metrics.total_tokens = handler.token_count
            metrics.response_length = len(response)
            
            # Process response through stream processor to get sentences
            stream_processor.reset()
            for char in response:
                stream_processor.feed(char)
            stream_processor.flush()
            
            metrics.total_sentences = len(sentences)
            
            # Measure first audio generation time
            if sentences:
                self.logger.info(f"Generating audio for first sentence: {sentences[0][:30]}...")
                audio_start = time.perf_counter()
                try:
                    audio_path = await self.tts_player.generate_audio(sentences[0])
                    metrics.first_audio_generation_time = time.perf_counter() - audio_start
                    
                    # Calculate time from start to first audio ready
                    # In real pipeline: first_token_time + time_to_first_sentence + audio_gen_time
                    metrics.first_audio_playback_start = (
                        metrics.first_token_time + 
                        (first_sentence_time or 0.0) + 
                        metrics.first_audio_generation_time
                    )
                    
                    self.tts_player.cleanup_temp_file(audio_path)
                except Exception as e:
                    self.logger.warning(f"Audio generation failed: {e}")
            
            self.logger.info(f"Streaming mode measurement complete")
            
        except Exception as e:
            self.logger.error(f"Streaming measurement failed: {e}")
            raise
        
        return metrics
    
    async def measure_non_streaming_mode(self, test_message: str) -> PerformanceMetrics:
        """
        Measure performance in non-streaming mode (baseline).
        
        Args:
            test_message: Message to send to LLM
            
        Returns:
            PerformanceMetrics with timing data
        """
        metrics = PerformanceMetrics(mode="non-streaming", test_message=test_message)
        
        self.logger.info(f"Measuring non-streaming mode with message: {test_message}")
        
        start_time = time.perf_counter()
        
        try:
            # Disable streaming mode
            self.llm_client.enable_streaming = False
            
            # Generate non-streaming response
            response = await self.llm_client.generate_response(
                test_message, 
                return_structured=True
            )
            
            response_time = time.perf_counter() - start_time
            
            # In non-streaming mode, first token = full response
            metrics.first_token_time = response_time
            metrics.full_response_time = response_time
            
            # Extract text from response
            if isinstance(response, dict):
                text = response.get('text', '')
                emotion = response.get('emotion', 'neutral')
                metrics.emotion_detection_time = response_time  # Emotion detected at end
            else:
                text = str(response)
            
            metrics.response_length = len(text)
            
            # Count sentences
            sentences = []
            def on_sentence(s):
                sentences.append(s)
            
            processor = StreamProcessor(on_sentence=on_sentence)
            for char in text:
                processor.feed(char)
            processor.flush()
            
            metrics.total_sentences = len(sentences)
            
            # Measure audio generation for full text
            if text:
                self.logger.info(f"Generating audio for full response...")
                audio_start = time.perf_counter()
                try:
                    audio_path = await self.tts_player.generate_audio(text[:100])  # Limit for fair comparison
                    metrics.first_audio_generation_time = time.perf_counter() - audio_start
                    metrics.first_audio_playback_start = response_time + metrics.first_audio_generation_time
                    self.tts_player.cleanup_temp_file(audio_path)
                except Exception as e:
                    self.logger.warning(f"Audio generation failed: {e}")
            
            self.logger.info(f"Non-streaming mode measurement complete")
            
        except Exception as e:
            self.logger.error(f"Non-streaming measurement failed: {e}")
            raise
        
        return metrics
    
    async def run_benchmark(
        self, 
        test_message: str,
        iterations: int = 3,
        skip_warmup: bool = False
    ) -> Dict[str, Any]:
        """
        Run complete performance benchmark.
        
        Args:
            test_message: Message to use for testing
            iterations: Number of iterations for each mode
            skip_warmup: Skip warmup phase
            
        Returns:
            Dictionary with benchmark results
        """
        results = {
            "config": {
                "ollama_url": self.config.ollama_url,
                "ollama_model": self.config.ollama_model,
                "test_message": test_message,
                "iterations": iterations,
                "streaming_enabled": self.config.performance.enable_streaming,
                "sentence_chunking_enabled": self.config.performance.enable_sentence_chunking,
            },
            "warmup": None,
            "streaming_results": [],
            "non_streaming_results": [],
            "summary": {}
        }
        
        # Warmup
        if not skip_warmup:
            warmup_results = await self.warmup()
            results["warmup"] = warmup_results
            
            if not warmup_results["llm"]:
                self.logger.error("LLM warmup failed, benchmark may be inaccurate")
        
        # Run streaming mode measurements
        self.logger.info(f"\n{'='*60}")
        self.logger.info("Running STREAMING mode measurements...")
        self.logger.info(f"{'='*60}")
        
        for i in range(iterations):
            self.logger.info(f"\nIteration {i+1}/{iterations}")
            try:
                metrics = await self.measure_streaming_mode(test_message)
                results["streaming_results"].append(metrics.to_dict())
                
                # Brief pause between iterations
                await asyncio.sleep(1.0)
            except Exception as e:
                self.logger.error(f"Streaming iteration {i+1} failed: {e}")
        
        # Run non-streaming mode measurements
        self.logger.info(f"\n{'='*60}")
        self.logger.info("Running NON-STREAMING mode measurements...")
        self.logger.info(f"{'='*60}")
        
        for i in range(iterations):
            self.logger.info(f"\nIteration {i+1}/{iterations}")
            try:
                metrics = await self.measure_non_streaming_mode(test_message)
                results["non_streaming_results"].append(metrics.to_dict())
                
                # Brief pause between iterations
                await asyncio.sleep(1.0)
            except Exception as e:
                self.logger.error(f"Non-streaming iteration {i+1} failed: {e}")
        
        # Calculate summary statistics
        results["summary"] = self._calculate_summary(results)
        
        return results

    def _calculate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate summary statistics from benchmark results."""
        summary = {
            "streaming": {},
            "non_streaming": {},
            "improvement": {}
        }
        
        # Calculate streaming averages
        streaming_data = results["streaming_results"]
        if streaming_data:
            summary["streaming"] = {
                "avg_first_token_time": self._avg([d["first_token_time"] for d in streaming_data]),
                "avg_emotion_detection_time": self._avg([d["emotion_detection_time"] for d in streaming_data]),
                "avg_full_response_time": self._avg([d["full_response_time"] for d in streaming_data]),
                "avg_first_audio_generation_time": self._avg([d["first_audio_generation_time"] for d in streaming_data]),
                "avg_first_audio_playback_start": self._avg([d["first_audio_playback_start"] for d in streaming_data]),
                "iterations": len(streaming_data)
            }
        
        # Calculate non-streaming averages
        non_streaming_data = results["non_streaming_results"]
        if non_streaming_data:
            summary["non_streaming"] = {
                "avg_first_token_time": self._avg([d["first_token_time"] for d in non_streaming_data]),
                "avg_emotion_detection_time": self._avg([d["emotion_detection_time"] for d in non_streaming_data]),
                "avg_full_response_time": self._avg([d["full_response_time"] for d in non_streaming_data]),
                "avg_first_audio_generation_time": self._avg([d["first_audio_generation_time"] for d in non_streaming_data]),
                "avg_first_audio_playback_start": self._avg([d["first_audio_playback_start"] for d in non_streaming_data]),
                "iterations": len(non_streaming_data)
            }
        
        # Calculate improvements
        if streaming_data and non_streaming_data:
            s = summary["streaming"]
            ns = summary["non_streaming"]
            
            if ns["avg_first_token_time"] > 0:
                summary["improvement"]["first_token_speedup"] = (
                    ns["avg_first_token_time"] / s["avg_first_token_time"]
                    if s["avg_first_token_time"] > 0 else 0
                )
                summary["improvement"]["first_token_reduction_seconds"] = (
                    ns["avg_first_token_time"] - s["avg_first_token_time"]
                )
            
            if ns["avg_first_audio_playback_start"] > 0:
                summary["improvement"]["first_audio_speedup"] = (
                    ns["avg_first_audio_playback_start"] / s["avg_first_audio_playback_start"]
                    if s["avg_first_audio_playback_start"] > 0 else 0
                )
                summary["improvement"]["first_audio_reduction_seconds"] = (
                    ns["avg_first_audio_playback_start"] - s["avg_first_audio_playback_start"]
                )
        
        return summary
    
    @staticmethod
    def _avg(values: List[float]) -> float:
        """Calculate average of non-zero values."""
        non_zero = [v for v in values if v > 0]
        return sum(non_zero) / len(non_zero) if non_zero else 0.0


def print_results(results: Dict[str, Any], json_output: bool = False) -> None:
    """Print benchmark results in human-readable or JSON format."""
    if json_output:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return
    
    print("\n" + "=" * 70)
    print("PERFORMANCE BENCHMARK RESULTS")
    print("=" * 70)
    
    # Config info
    config = results.get("config", {})
    print(f"\nConfiguration:")
    print(f"  Model: {config.get('ollama_model', 'N/A')}")
    print(f"  Test Message: {config.get('test_message', 'N/A')[:50]}...")
    print(f"  Iterations: {config.get('iterations', 'N/A')}")
    
    # Warmup status
    warmup = results.get("warmup")
    if warmup:
        print(f"\nWarmup Status:")
        print(f"  LLM: {'✓' if warmup.get('llm') else '✗'}")
        print(f"  TTS: {'✓' if warmup.get('tts') else '✗'}")
    
    summary = results.get("summary", {})
    
    # Streaming results
    streaming = summary.get("streaming", {})
    if streaming:
        print(f"\n{'─' * 70}")
        print("STREAMING MODE (Optimized)")
        print(f"{'─' * 70}")
        print(f"  First Token Time:        {streaming.get('avg_first_token_time', 0):.3f}s")
        print(f"  Emotion Detection Time:  {streaming.get('avg_emotion_detection_time', 0):.3f}s")
        print(f"  Full Response Time:      {streaming.get('avg_full_response_time', 0):.3f}s")
        print(f"  First Audio Gen Time:    {streaming.get('avg_first_audio_generation_time', 0):.3f}s")
        print(f"  First Audio Playback:    {streaming.get('avg_first_audio_playback_start', 0):.3f}s")
    
    # Non-streaming results
    non_streaming = summary.get("non_streaming", {})
    if non_streaming:
        print(f"\n{'─' * 70}")
        print("NON-STREAMING MODE (Baseline)")
        print(f"{'─' * 70}")
        print(f"  First Token Time:        {non_streaming.get('avg_first_token_time', 0):.3f}s")
        print(f"  Emotion Detection Time:  {non_streaming.get('avg_emotion_detection_time', 0):.3f}s")
        print(f"  Full Response Time:      {non_streaming.get('avg_full_response_time', 0):.3f}s")
        print(f"  First Audio Gen Time:    {non_streaming.get('avg_first_audio_generation_time', 0):.3f}s")
        print(f"  First Audio Playback:    {non_streaming.get('avg_first_audio_playback_start', 0):.3f}s")
    
    # Improvement summary
    improvement = summary.get("improvement", {})
    if improvement:
        print(f"\n{'─' * 70}")
        print("IMPROVEMENT SUMMARY")
        print(f"{'─' * 70}")
        
        first_token_speedup = improvement.get("first_token_speedup", 0)
        first_token_reduction = improvement.get("first_token_reduction_seconds", 0)
        if first_token_speedup > 0:
            print(f"  First Token Speedup:     {first_token_speedup:.1f}x faster ({first_token_reduction:.2f}s saved)")
        
        first_audio_speedup = improvement.get("first_audio_speedup", 0)
        first_audio_reduction = improvement.get("first_audio_reduction_seconds", 0)
        if first_audio_speedup > 0:
            print(f"  First Audio Speedup:     {first_audio_speedup:.1f}x faster ({first_audio_reduction:.2f}s saved)")
    
    # Target comparison
    print(f"\n{'─' * 70}")
    print("TARGET COMPARISON")
    print(f"{'─' * 70}")
    print("  Expected targets (from design doc):")
    print("    - First text response: 1-2s (was 14-22s)")
    print("    - First audio playback: 5-8s (was 30-40s)")
    print("    - Emotion trigger: 1-2s (was 30s+)")
    
    if streaming:
        first_token = streaming.get('avg_first_token_time', 0)
        first_audio = streaming.get('avg_first_audio_playback_start', 0)
        emotion_time = streaming.get('avg_emotion_detection_time', 0)
        
        print(f"\n  Actual results:")
        print(f"    - First text response: {first_token:.2f}s {'✓' if first_token <= 2 else '(target: ≤2s)'}")
        print(f"    - First audio playback: {first_audio:.2f}s {'✓' if first_audio <= 8 else '(target: ≤8s)'}")
        print(f"    - Emotion trigger: {emotion_time:.2f}s {'✓' if emotion_time <= 2 else '(target: ≤2s)'}")
    
    print("\n" + "=" * 70)


def save_benchmark_results(results: Dict[str, Any], output_path: str) -> None:
    """
    Save benchmark results to a JSON file.
    
    Args:
        results: Benchmark results dictionary
        output_path: Path to save the results
    """
    # Add timestamp to results
    results["timestamp"] = datetime.now().isoformat()
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {output_path}")


def generate_comparison_report(results: Dict[str, Any]) -> str:
    """
    Generate a detailed comparison report in markdown format.
    
    Args:
        results: Benchmark results dictionary
        
    Returns:
        Markdown formatted report string
    """
    report = []
    report.append("# Performance Comparison Report: Streaming vs Non-Streaming")
    report.append("")
    report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Configuration
    config = results.get("config", {})
    report.append("## Test Configuration")
    report.append("")
    report.append(f"- **Model:** {config.get('ollama_model', 'N/A')}")
    report.append(f"- **Test Message:** {config.get('test_message', 'N/A')}")
    report.append(f"- **Iterations:** {config.get('iterations', 'N/A')}")
    report.append(f"- **Streaming Enabled:** {config.get('streaming_enabled', 'N/A')}")
    report.append(f"- **Sentence Chunking:** {config.get('sentence_chunking_enabled', 'N/A')}")
    report.append("")
    
    # Warmup status
    warmup = results.get("warmup")
    if warmup:
        report.append("## Warmup Status")
        report.append("")
        report.append(f"- **LLM Warmup:** {'✓ Success' if warmup.get('llm') else '✗ Failed'}")
        report.append(f"- **TTS Warmup:** {'✓ Success' if warmup.get('tts') else '✗ Failed'}")
        report.append("")
    
    summary = results.get("summary", {})
    
    # Results table
    report.append("## Performance Metrics Comparison")
    report.append("")
    report.append("| Metric | Streaming Mode | Non-Streaming Mode | Improvement |")
    report.append("|--------|---------------|-------------------|-------------|")
    
    streaming = summary.get("streaming", {})
    non_streaming = summary.get("non_streaming", {})
    improvement = summary.get("improvement", {})
    
    metrics = [
        ("First Token Time", "avg_first_token_time", "first_token_reduction_seconds"),
        ("Emotion Detection Time", "avg_emotion_detection_time", None),
        ("Full Response Time", "avg_full_response_time", None),
        ("First Audio Generation", "avg_first_audio_generation_time", None),
        ("First Audio Playback", "avg_first_audio_playback_start", "first_audio_reduction_seconds"),
    ]
    
    for label, key, improvement_key in metrics:
        s_val = streaming.get(key, 0)
        ns_val = non_streaming.get(key, 0)
        
        if improvement_key and improvement_key in improvement:
            imp_val = improvement[improvement_key]
            imp_str = f"-{imp_val:.2f}s" if imp_val > 0 else f"+{abs(imp_val):.2f}s"
        elif s_val > 0 and ns_val > 0:
            diff = ns_val - s_val
            imp_str = f"-{diff:.2f}s" if diff > 0 else f"+{abs(diff):.2f}s"
        else:
            imp_str = "N/A"
        
        report.append(f"| {label} | {s_val:.3f}s | {ns_val:.3f}s | {imp_str} |")
    
    report.append("")
    
    # Target comparison
    report.append("## Target Verification")
    report.append("")
    report.append("| Target | Expected | Actual | Status |")
    report.append("|--------|----------|--------|--------|")
    
    if streaming:
        first_token = streaming.get('avg_first_token_time', 0)
        first_audio = streaming.get('avg_first_audio_playback_start', 0)
        emotion_time = streaming.get('avg_emotion_detection_time', 0)
        
        # First text response target: 1-2s
        status = "✓ PASS" if first_token <= 2 else "✗ FAIL"
        report.append(f"| First Text Response | ≤2s | {first_token:.2f}s | {status} |")
        
        # First audio playback target: 5-8s
        status = "✓ PASS" if first_audio <= 8 else "✗ FAIL"
        report.append(f"| First Audio Playback | ≤8s | {first_audio:.2f}s | {status} |")
        
        # Emotion trigger target: 1-2s
        status = "✓ PASS" if emotion_time <= 2 else "✗ FAIL"
        report.append(f"| Emotion Trigger | ≤2s | {emotion_time:.2f}s | {status} |")
    
    report.append("")
    
    # Speedup summary
    if improvement:
        report.append("## Speedup Summary")
        report.append("")
        
        first_token_speedup = improvement.get("first_token_speedup", 0)
        first_audio_speedup = improvement.get("first_audio_speedup", 0)
        
        if first_token_speedup > 0:
            report.append(f"- **First Token Speedup:** {first_token_speedup:.1f}x faster")
        if first_audio_speedup > 0:
            report.append(f"- **First Audio Speedup:** {first_audio_speedup:.1f}x faster")
        report.append("")
    
    # Raw data
    report.append("## Raw Iteration Data")
    report.append("")
    
    report.append("### Streaming Mode Iterations")
    report.append("")
    for i, data in enumerate(results.get("streaming_results", []), 1):
        report.append(f"**Iteration {i}:**")
        report.append(f"- First Token: {data.get('first_token_time', 0):.3f}s")
        report.append(f"- Emotion Detection: {data.get('emotion_detection_time', 0):.3f}s")
        report.append(f"- Full Response: {data.get('full_response_time', 0):.3f}s")
        report.append(f"- First Audio Playback: {data.get('first_audio_playback_start', 0):.3f}s")
        report.append("")
    
    report.append("### Non-Streaming Mode Iterations")
    report.append("")
    for i, data in enumerate(results.get("non_streaming_results", []), 1):
        report.append(f"**Iteration {i}:**")
        report.append(f"- First Token: {data.get('first_token_time', 0):.3f}s")
        report.append(f"- Emotion Detection: {data.get('emotion_detection_time', 0):.3f}s")
        report.append(f"- Full Response: {data.get('full_response_time', 0):.3f}s")
        report.append(f"- First Audio Playback: {data.get('first_audio_playback_start', 0):.3f}s")
        report.append("")
    
    return "\n".join(report)


async def main():
    """Main entry point for the performance measurement tool."""
    parser = argparse.ArgumentParser(
        description="Measure AI VTuber system performance metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/measure_performance.py
  python tools/measure_performance.py --iterations 5
  python tools/measure_performance.py --test-message "你好，今天天气怎么样？"
  python tools/measure_performance.py --skip-warmup --json
  python tools/measure_performance.py --save-results results.json
  python tools/measure_performance.py --generate-report
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        default="config.json",
        help="Path to configuration file (default: config.json)"
    )
    
    parser.add_argument(
        "--iterations", "-n",
        type=int,
        default=3,
        help="Number of iterations for each mode (default: 3)"
    )
    
    parser.add_argument(
        "--test-message", "-m",
        default=PerformanceMeasurer.DEFAULT_TEST_MESSAGE,
        help="Test message to send to LLM"
    )
    
    parser.add_argument(
        "--skip-warmup",
        action="store_true",
        help="Skip warmup phase (not recommended for accurate results)"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress messages"
    )
    
    parser.add_argument(
        "--save-results", "-s",
        type=str,
        default=None,
        help="Save results to JSON file (e.g., results.json)"
    )
    
    parser.add_argument(
        "--generate-report", "-r",
        action="store_true",
        help="Generate a markdown comparison report"
    )
    
    parser.add_argument(
        "--report-output", "-o",
        type=str,
        default="performance_report.md",
        help="Output path for markdown report (default: performance_report.md)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    
    # Load configuration
    try:
        if os.path.exists(args.config):
            config = load_config(args.config)
            logger.info(f"Loaded configuration from {args.config}")
        else:
            config = SystemConfig()
            logger.warning(f"Config file {args.config} not found, using defaults")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Create measurer and initialize
    measurer = PerformanceMeasurer(config, logger)
    
    if not await measurer.initialize():
        logger.error("Failed to initialize performance measurer")
        sys.exit(1)
    
    # Run benchmark
    try:
        results = await measurer.run_benchmark(
            test_message=args.test_message,
            iterations=args.iterations,
            skip_warmup=args.skip_warmup
        )
        
        # Print results
        print_results(results, json_output=args.json)
        
        # Save results to JSON if requested
        if args.save_results:
            save_benchmark_results(results, args.save_results)
        
        # Generate markdown report if requested
        if args.generate_report:
            report = generate_comparison_report(results)
            with open(args.report_output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\nMarkdown report saved to: {args.report_output}")
        
    except KeyboardInterrupt:
        logger.info("\nBenchmark interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
