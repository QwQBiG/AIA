
"""
基于Whisper的语音识别替代方案
Alternative ASR solution using Whisper when FunASR is not available
"""

import torch
import whisper
import numpy as np
from typing import Optional, Callable, List
import threading
import queue
import time
import logging
from dataclasses import dataclass

@dataclass
class StreamUpdate:
    """流式更新数据类"""
    partial_text: str
    confidence: float
    timestamp: float

@dataclass
class SentenceComplete:
    """句子完成数据类"""
    final_text: str
    confidence: float
    start_time: float
    end_time: float

class WhisperASR:
    """
    基于Whisper的语音识别引擎
    作为FunASR的替代方案
    """
    
    def __init__(self, model_size: str = "base"):
        """
        初始化Whisper ASR
        
        Args:
            model_size: 模型大小 ("tiny", "base", "small", "medium", "large")
        """
        self.logger = logging.getLogger(__name__)
        self.model_size = model_size
        self.model = None
        self.is_running = False
        self.audio_queue = queue.Queue()
        self.result_callback: Optional[Callable] = None
        self.sentence_callback: Optional[Callable] = None
        
        # 音频参数
        self.sample_rate = 16000
        self.chunk_duration = 2.0  # 2秒音频块
        self.chunk_samples = int(self.sample_rate * self.chunk_duration)
        
        # 缓冲区
        self.audio_buffer = np.array([], dtype=np.float32)
        self.min_audio_length = 1.0  # 最小音频长度（秒）
        
        # 工作线程
        self.worker_thread = None
        self.stop_event = threading.Event()
    
    def initialize(self) -> bool:
        """
        初始化Whisper模型
        
        Returns:
            初始化是否成功
        """
        try:
            self.logger.info(f"Loading Whisper model: {self.model_size}")
            self.model = whisper.load_model(self.model_size)
            self.logger.info("Whisper model loaded successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}")
            return False
    
    def set_callbacks(self, result_callback: Callable, sentence_callback: Callable):
        """设置回调函数"""
        self.result_callback = result_callback
        self.sentence_callback = sentence_callback
    
    def start_streaming(self) -> bool:
        """
        开始流式识别
        
        Returns:
            启动是否成功
        """
        if not self.model:
            self.logger.error("Model not initialized")
            return False
        
        if self.is_running:
            self.logger.warning("ASR already running")
            return True
        
        self.is_running = True
        self.stop_event.clear()
        
        # 启动工作线程
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        self.logger.info("Whisper ASR streaming started")
        return True
    
    def stop_streaming(self):
        """停止流式识别"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.stop_event.set()
        
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
        
        # 清空队列
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        self.audio_buffer = np.array([], dtype=np.float32)
        self.logger.info("Whisper ASR streaming stopped")
    
    def process_audio(self, audio_data: np.ndarray):
        """
        处理音频数据
        
        Args:
            audio_data: 音频数据 (16kHz, float32)
        """
        if not self.is_running:
            return
        
        try:
            # 音频预处理：降噪和标准化
            audio_data = self._preprocess_audio(audio_data)
            
            # 添加到缓冲区
            self.audio_buffer = np.concatenate([self.audio_buffer, audio_data])
            
            # 如果缓冲区足够大，放入队列处理
            if len(self.audio_buffer) >= self.chunk_samples:
                chunk = self.audio_buffer[:self.chunk_samples].copy()
                self.audio_buffer = self.audio_buffer[self.chunk_samples//2:]  # 50% 重叠
                
                if not self.audio_queue.full():
                    self.audio_queue.put(chunk)
                
        except Exception as e:
            self.logger.error(f"Error processing audio: {e}")
    
    def _preprocess_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """预处理音频数据以提高识别效果"""
        try:
            # 转换为 float32（如果还不是的话）
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
                # int16 范围归一化
                if audio_data.max() > 1.0 or audio_data.min() < -1.0:
                    audio_data = audio_data / 32768.0
            
            # 幅度标准化：避免过载，保留动态范围
            max_val = np.max(np.abs(audio_data))
            if max_val > 0.01:  # 有实际音频信号
                audio_data = audio_data / max_val * 0.9
            
            return audio_data
        except Exception as e:
            self.logger.warning(f"Audio preprocessing failed: {e}")
            return audio_data
    
    def _worker_loop(self):
        """工作线程主循环"""
        while self.is_running and not self.stop_event.is_set():
            try:
                # 获取音频块
                audio_chunk = self.audio_queue.get(timeout=0.1)
                
                # 检查音频长度
                if len(audio_chunk) < int(self.sample_rate * self.min_audio_length):
                    continue
                
                # 使用Whisper进行识别
                start_time = time.time()
                result = self.model.transcribe(
                    audio_chunk,
                    language="zh",  # 中文
                    task="transcribe",
                    fp16=torch.cuda.is_available(),
                    verbose=False,
                    initial_prompt="以下是普通话的句子。",  # 中文提示
                    temperature=0.0,  # 降低随机性
                    beam_size=5,  # 使用beam search提高准确率
                    best_of=1,  # 减少延迟，从5降到1
                    patience=1.0  # 耐心等待更好结果
                )
                
                process_time = time.time() - start_time
                
                # 提取文本和置信度
                text = result.get("text", "").strip()
                
                if text and len(text) > 1:  # 过滤太短的结果
                    # 计算平均置信度
                    segments = result.get("segments", [])
                    if segments:
                        avg_confidence = sum(seg.get("no_speech_prob", 0.5) for seg in segments) / len(segments)
                        confidence = 1.0 - avg_confidence  # 转换为置信度
                    else:
                        confidence = 0.8  # 默认置信度
                    
                    # 发送流式更新
                    if self.result_callback:
                        update = StreamUpdate(
                            partial_text=text,
                            confidence=confidence,
                            timestamp=time.time()
                        )
                        self.result_callback(update)
                    
                    # 发送完整句子
                    if self.sentence_callback:
                        sentence = SentenceComplete(
                            final_text=text,
                            confidence=confidence,
                            start_time=start_time,
                            end_time=time.time()
                        )
                        self.sentence_callback(sentence)
                    
                    self.logger.debug(f"ASR result: '{text}' (confidence: {confidence:.2f}, time: {process_time:.2f}s)")
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error in ASR worker loop: {e}")
                time.sleep(0.1)

def get_whisper_asr(model_size: str = "base") -> WhisperASR:
    """获取Whisper ASR实例"""
    return WhisperASR(model_size)

# 检查是否可以使用FunASR
def is_funasr_available() -> bool:
    """检查FunASR是否可用"""
    try:
        import funasr
        return True
    except ImportError:
        return False

# 检查是否可以使用Whisper
def is_whisper_available() -> bool:
    """检查Whisper是否可用"""
    try:
        import whisper
        return True
    except ImportError:
        return False
