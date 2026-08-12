"""
全双工音频缓冲优化模块

实现智能音频缓冲策略,优化语音识别延迟和准确性,
目标: 降低语音识别延迟,减少音频块丢弃。
"""

import logging
import time
import numpy as np
from collections import deque
from typing import Optional, List, Tuple
from dataclasses import dataclass
import threading

logger = logging.getLogger(__name__)


@dataclass
class AudioChunk:
    """音频数据块"""
    data: np.ndarray
    timestamp: float
    sample_rate: int
    chunk_id: int


@dataclass
class BufferStats:
    """缓冲区统计"""
    buffer_size: int
    buffer_capacity: int
    utilization: float  # 利用率 0.0-1.0
    total_chunks: int
    dropped_chunks: int
    avg_chunk_interval: float
    buffer_full_events: int


class AdaptiveBuffer:
    """
    自适应音频缓冲区

    特性:
    1. 动态调整缓冲区大小
    2. 智能预填充策略
    3. 优先级队列管理
    4. 丢弃策略优化
    """

    def __init__(self,
                 initial_capacity: int = 10,
                 min_capacity: int = 5,
                 max_capacity: int = 20,
                 target_utilization: float = 0.7):
        """
        初始化自适应缓冲区

        Args:
            initial_capacity: 初始缓冲区容量
            min_capacity: 最小容量
            max_capacity: 最大容量
            target_utilization: 目标利用率(0.0-1.0)
        """
        self.min_capacity = min_capacity
        self.max_capacity = max_capacity
        self.target_utilization = target_utilization
        self.current_capacity = initial_capacity

        # 主缓冲区
        self.buffer: deque = deque(maxlen=initial_capacity)
        self.buffer_lock = threading.Lock()

        # 统计信息
        self.total_chunks = 0
        self.dropped_chunks = 0
        self.buffer_full_events = 0
        self.chunk_intervals = deque(maxlen=100)

        # 自适应控制
        self.utilization_history = deque(maxlen=50)
        self.last_adjustment_time = 0.0
        self.adjustment_interval = 5.0  # 每5秒调整一次

        logger.info(f"AdaptiveBuffer initialized: capacity={initial_capacity}, "
                   f"min={min_capacity}, max={max_capacity}, target={target_utilization:.2f}")

    def add_chunk(self, chunk: AudioChunk) -> bool:
        """
        添加音频块到缓冲区

        Args:
            chunk: 音频数据块

        Returns:
            bool: 是否成功添加(如果缓冲区已满,可能丢弃)
        """
        with self.buffer_lock:
            self.total_chunks += 1

            # 检查缓冲区是否已满
            if len(self.buffer) >= self.current_capacity:
                # 自适应策略: 根据音频重要性决定是否丢弃
                should_drop = self._should_drop_chunk(chunk)

                if should_drop:
                    self.dropped_chunks += 1
                    logger.debug(f"Audio chunk dropped (buffer full): "
                               f"capacity={self.current_capacity}, dropped={self.dropped_chunks}")
                    return False
                else:
                    # 移除最旧的块,添加新块
                    self.buffer.popleft()
                    self.buffer_full_events += 1

            # 添加新块
            self.buffer.append(chunk)

            # 记录时间间隔
            self._record_chunk_interval(chunk.timestamp)

            # 更新利用率
            self._update_utilization()

            return True

    def get_chunks(self, count: int) -> List[AudioChunk]:
        """
        从缓冲区获取指定数量的音频块

        Args:
            count: 要获取的块数量

        Returns:
            音频块列表
        """
        with self.buffer_lock:
            if count <= 0 or len(self.buffer) == 0:
                return []

            # 获取最新的count个块
            actual_count = min(count, len(self.buffer))
            result = list(self.buffer)[-actual_count:]

            return result

    def get_all_chunks(self) -> List[AudioChunk]:
        """
        获取缓冲区所有音频块

        Returns:
            所有音频块列表
        """
        with self.buffer_lock:
            return list(self.buffer)

    def clear(self):
        """清空缓冲区"""
        with self.buffer_lock:
            self.buffer.clear()
            logger.debug("Audio buffer cleared")

    def _should_drop_chunk(self, chunk: AudioChunk) -> bool:
        """
        决定是否应该丢弃音频块

        策略:
        1. 如果音频能量低(静音),优先丢弃
        2. 如果缓冲区严重过载,丢弃最旧的块

        Args:
            chunk: 音频块

        Returns:
            bool: 是否应该丢弃
        """
        # 计算音频能量
        audio_float = chunk.data.astype(np.float32) / 32768.0
        energy = np.sqrt(np.mean(audio_float ** 2))

        # 静音阈值
        silence_threshold = 0.01

        # 如果是静音,可以丢弃
        if energy < silence_threshold:
            return True

        # 如果缓冲区严重过载(>90%容量),丢弃最旧的块
        if len(self.buffer) > self.current_capacity * 0.9:
            return True

        return False

    def _record_chunk_interval(self, timestamp: float):
        """记录音频块时间间隔"""
        if hasattr(self, '_last_timestamp') and self._last_timestamp > 0:
            interval = timestamp - self._last_timestamp
            self.chunk_intervals.append(interval)

        self._last_timestamp = timestamp

    def _update_utilization(self):
        """更新利用率历史"""
        utilization = len(self.buffer) / self.current_capacity
        self.utilization_history.append(utilization)

    def auto_adjust_capacity(self):
        """
        自动调整缓冲区容量

        根据历史利用率动态调整容量,
        目标是保持在目标利用率附近。
        """
        current_time = time.time()

        # 检查是否到达调整时间
        if current_time - self.last_adjustment_time < self.adjustment_interval:
            return

        # 计算平均利用率
        if len(self.utilization_history) == 0:
            return

        avg_utilization = sum(self.utilization_history) / len(self.utilization_history)

        # 决定调整方向
        new_capacity = self.current_capacity

        if avg_utilization > self.target_utilization + 0.1:
            # 利用率过高,增加容量
            new_capacity = min(self.current_capacity + 1, self.max_capacity)
        elif avg_utilization < self.target_utilization - 0.1:
            # 利用率过低,减少容量
            new_capacity = max(self.current_capacity - 1, self.min_capacity)

        # 应用调整
        if new_capacity != self.current_capacity:
            logger.info(f"Adjusting buffer capacity: {self.current_capacity} -> {new_capacity} "
                       f"(avg_utilization={avg_utilization:.2f})")

            # 更新缓冲区容量
            with self.buffer_lock:
                # 保存当前数据
                current_data = list(self.buffer)

                # 创建新的deque
                self.current_capacity = new_capacity
                self.buffer = deque(maxlen=new_capacity)

                # 恢复数据
                for chunk in current_data:
                    self.buffer.append(chunk)

            self.last_adjustment_time = current_time

    def get_stats(self) -> BufferStats:
        """
        获取缓冲区统计信息

        Returns:
            缓冲区统计数据
        """
        with self.buffer_lock:
            utilization = len(self.buffer) / self.current_capacity if self.current_capacity > 0 else 0.0

            avg_interval = 0.0
            if len(self.chunk_intervals) > 0:
                avg_interval = sum(self.chunk_intervals) / len(self.chunk_intervals)

            return BufferStats(
                buffer_size=len(self.buffer),
                buffer_capacity=self.current_capacity,
                utilization=utilization,
                total_chunks=self.total_chunks,
                dropped_chunks=self.dropped_chunks,
                avg_chunk_interval=avg_interval,
                buffer_full_events=self.buffer_full_events
            )


class SmartPreFill:
    """
    智能预填充策略

    在音频流开始前预填充缓冲区,
    减少初始延迟。
    """

    def __init__(self, buffer: AdaptiveBuffer, pre_fill_target: int = 5):
        """
        初始化智能预填充

        Args:
            buffer: 自适应缓冲区
            pre_fill_target: 预填充目标块数
        """
        self.buffer = buffer
        self.pre_fill_target = pre_fill_target
        self.is_pre_filling = False
        self.pre_fill_chunks = []

        logger.info(f"SmartPreFill initialized: target={pre_fill_target} chunks")

    def start_pre_fill(self):
        """开始预填充"""
        self.is_pre_filling = True
        self.pre_fill_chunks = []
        logger.info("Starting pre-fill...")

    def add_pre_fill_chunk(self, chunk: AudioChunk):
        """
        添加预填充块

        Args:
            chunk: 音频块
        """
        if not self.is_pre_filling:
            return

        self.pre_fill_chunks.append(chunk)

        # 检查是否达到目标
        if len(self.pre_fill_chunks) >= self.pre_fill_target:
            self._flush_pre_fill()

    def _flush_pre_fill(self):
        """刷新预填充块到缓冲区"""
        logger.info(f"Pre-fill complete: {len(self.pre_fill_chunks)} chunks")

        # 将预填充块添加到缓冲区
        for chunk in self.pre_fill_chunks:
            self.buffer.add_chunk(chunk)

        # 重置状态
        self.is_pre_filling = False
        self.pre_fill_chunks = []

    def cancel_pre_fill(self):
        """取消预填充"""
        self.is_pre_filling = False
        self.pre_fill_chunks = []
        logger.info("Pre-fill cancelled")

    def is_complete(self) -> bool:
        """检查预填充是否完成"""
        return not self.is_pre_filling


class BufferOptimizer:
    """
    缓冲区优化器

    整合自适应缓冲区和智能预填充,
    提供统一的缓冲区优化接口。
    """

    def __init__(self,
                 initial_capacity: int = 10,
                 min_capacity: int = 5,
                 max_capacity: int = 20,
                 target_utilization: float = 0.7,
                 pre_fill_target: int = 5):
        """
        初始化缓冲区优化器

        Args:
            initial_capacity: 初始容量
            min_capacity: 最小容量
            max_capacity: 最大容量
            target_utilization: 目标利用率
            pre_fill_target: 预填充目标
        """
        self.adaptive_buffer = AdaptiveBuffer(
            initial_capacity=initial_capacity,
            min_capacity=min_capacity,
            max_capacity=max_capacity,
            target_utilization=target_utilization
        )

        self.smart_pre_fill = SmartPreFill(
            buffer=self.adaptive_buffer,
            pre_fill_target=pre_fill_target
        )

        logger.info("BufferOptimizer initialized")

    def add_chunk(self, chunk: AudioChunk) -> bool:
        """添加音频块"""
        # 如果正在预填充,添加到预填充队列
        if self.smart_pre_fill.is_pre_filling:
            self.smart_pre_fill.add_pre_fill_chunk(chunk)
            return True

        # 否则添加到主缓冲区
        return self.adaptive_buffer.add_chunk(chunk)

    def get_chunks(self, count: int) -> List[AudioChunk]:
        """获取音频块"""
        return self.adaptive_buffer.get_chunks(count)

    def clear(self):
        """清空缓冲区"""
        self.adaptive_buffer.clear()
        self.smart_pre_fill.cancel_pre_fill()

    def get_stats(self) -> BufferStats:
        """获取统计信息"""
        return self.adaptive_buffer.get_stats()

    def optimize(self):
        """优化缓冲区"""
        # 自动调整容量
        self.adaptive_buffer.auto_adjust_capacity()
