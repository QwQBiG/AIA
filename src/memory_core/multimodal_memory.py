"""
多模态记忆系统增强

支持文本、语音、视觉三种模态的记忆存储和检索,
实现智能的记忆优先级和自动清理。
"""

import logging
import time
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

from .memory_core import MemoryCore
from .data_models import Memory, MemoryType


logger = logging.getLogger(__name__)


class ModalityType(Enum):
    """记忆模态类型"""
    TEXT = "text"
    AUDIO = "audio"
    VISUAL = "visual"
    MULTIMODAL = "multimodal"


@dataclass
class MultimodalMemory:
    """多模态记忆"""
    memory_id: str
    modality: ModalityType
    text_content: Optional[str] = None
    audio_features: Optional[Dict] = None
    visual_features: Optional[Dict] = None
    timestamp: float = field(default_factory=time.time)
    importance_score: float = 0.5  # 0.0-1.0
    access_count: int = 0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class MultimodalMemorySystem:
    """
    多模态记忆系统

    功能:
    1. 多模态记忆存储(文本+语音+视觉)
    2. 记忆优先级自动调整
    3. 记忆过期和自动清理
    4. 记忆搜索和标签系统
    5. 跨模态关联检索
    """

    def __init__(self, memory_core: MemoryCore, max_memories: int = 1000):
        """
        初始化多模态记忆系统

        Args:
            memory_core: 基础记忆核心
            max_memories: 最大记忆数量
        """
        self.memory_core = memory_core
        self.max_memories = max_memories

        # 多模态记忆存储
        self.multimodal_memories: Dict[str, MultimodalMemory] = {}

        # 记忆标签索引
        self.tag_index: Dict[str, List[str]] = {}

        # 重要性计算参数
        self.importance_weights = {
            'content_length': 0.3,
            'entity_count': 0.2,
            'interaction_type': 0.2,
            'access_frequency': 0.3
        }

        # 自动清理配置
        self.auto_cleanup_enabled = True
        self.cleanup_interval = 3600  # 1小时
        self.last_cleanup_time = 0.0

        # 统计信息
        self.stats = {
            'total_memories': 0,
            'by_modality': {
                ModalityType.TEXT: 0,
                ModalityType.AUDIO: 0,
                ModalityType.VISUAL: 0,
                ModalityType.MULTIMODAL: 0
            },
            'cleanup_count': 0,
            'priority_adjustments': 0
        }

        logger.info(f"MultimodalMemorySystem initialized: max_memories={max_memories}")

    def add_text_memory(self,
                       text: str,
                       memory_type: MemoryType = MemoryType.INTERACTION,
                       importance: Optional[float] = None) -> str:
        """
        添加文本记忆

        Args:
            text: 文本内容
            memory_type: 记忆类型
            importance: 重要性(0.0-1.0),None表示自动计算

        Returns:
            记忆ID
        """
        # 计算重要性(如果未提供)
        if importance is None:
            importance = self._calculate_importance(text=text, modality=ModalityType.TEXT)

        # 创建多模态记忆
        memory = MultimodalMemory(
            memory_id=self._generate_memory_id(),
            modality=ModalityType.TEXT,
            text_content=text,
            importance_score=importance,
            timestamp=time.time()
        )

        # 存储记忆
        self._store_memory(memory)

        logger.debug(f"Text memory added: {memory.memory_id} (importance={importance:.2f})")

        return memory.memory_id

    def add_audio_memory(self,
                        text: str,
                        audio_features: Dict,
                        importance: Optional[float] = None) -> str:
        """
        添加语音记忆

        Args:
            text: 转录文本
            audio_features: 音频特征
            importance: 重要性

        Returns:
            记忆ID
        """
        if importance is None:
            importance = self._calculate_importance(
                text=text,
                modality=ModalityType.AUDIO,
                entity_count=len(audio_features.get('entities', []))
            )

        memory = MultimodalMemory(
            memory_id=self._generate_memory_id(),
            modality=ModalityType.AUDIO,
            text_content=text,
            audio_features=audio_features,
            importance_score=importance,
            timestamp=time.time()
        )

        self._store_memory(memory)

        logger.debug(f"Audio memory added: {memory.memory_id}")

        return memory.memory_id

    def add_visual_memory(self,
                         description: str,
                         visual_features: Dict,
                         importance: Optional[float] = None) -> str:
        """
        添加视觉记忆

        Args:
            description: 描述文本
            visual_features: 视觉特征
            importance: 重要性

        Returns:
            记忆ID
        """
        if importance is None:
            importance = self._calculate_importance(
                text=description,
                modality=ModalityType.VISUAL,
                entity_count=len(visual_features.get('objects', []))
            )

        memory = MultimodalMemory(
            memory_id=self._generate_memory_id(),
            modality=ModalityType.VISUAL,
            text_content=description,
            visual_features=visual_features,
            importance_score=importance,
            timestamp=time.time()
        )

        self._store_memory(memory)

        logger.debug(f"Visual memory added: {memory.memory_id}")

        return memory.memory_id

    def add_multimodal_memory(self,
                            text: str,
                            audio_features: Optional[Dict] = None,
                            visual_features: Optional[Dict] = None,
                            importance: Optional[float] = None) -> str:
        """
        添加多模态记忆

        Args:
            text: 文本内容
            audio_features: 音频特征(可选)
            visual_features: 视觉特征(可选)
            importance: 重要性

        Returns:
            记忆ID
        """
        has_audio = audio_features is not None
        has_visual = visual_features is not None

        if importance is None:
            entity_count = 0
            if audio_features:
                entity_count += len(audio_features.get('entities', []))
            if visual_features:
                entity_count += len(visual_features.get('objects', []))

            importance = self._calculate_importance(
                text=text,
                modality=ModalityType.MULTIMODAL,
                entity_count=entity_count
            )

        memory = MultimodalMemory(
            memory_id=self._generate_memory_id(),
            modality=ModalityType.MULTIMODAL,
            text_content=text,
            audio_features=audio_features,
            visual_features=visual_features,
            importance_score=importance,
            timestamp=time.time()
        )

        self._store_memory(memory)

        logger.debug(f"Multimodal memory added: {memory.memory_id}")

        return memory.memory_id

    def _store_memory(self, memory: MultimodalMemory):
        """
        存储记忆

        Args:
            memory: 多模态记忆对象
        """
        # 检查是否超过最大数量
        if len(self.multimodal_memories) >= self.max_memories:
            # 触发清理
            self._cleanup_memories()

        # 存储记忆
        self.multimodal_memories[memory.memory_id] = memory

        # 更新统计
        self.stats['total_memories'] += 1
        self.stats['by_modality'][memory.modality] += 1

        # 更新标签索引
        if memory.tags:
            for tag in memory.tags:
                if tag not in self.tag_index:
                    self.tag_index[tag] = []
                self.tag_index[tag].append(memory.memory_id)

    def retrieve_by_modality(self,
                           modality: ModalityType,
                           top_k: int = 10,
                           min_importance: float = 0.0) -> List[MultimodalMemory]:
        """
        按模态检索记忆

        Args:
            modality: 模态类型
            top_k: 返回数量
            min_importance: 最小重要性

        Returns:
            记忆列表
        """
        # 按重要性排序
        memories = [
            mem for mem in self.multimodal_memories.values()
            if mem.modality == modality and mem.importance_score >= min_importance
        ]

        # 排序并返回top_k
        memories.sort(key=lambda m: m.importance_score, reverse=True)

        return memories[:top_k]

    def search_by_tags(self,
                      tags: List[str],
                      top_k: int = 10) -> List[MultimodalMemory]:
        """
        按标签搜索记忆

        Args:
            tags: 标签列表
            top_k: 返回数量

        Returns:
            记忆列表
        """
        # 收集匹配的记忆ID
        matching_ids = set()

        for tag in tags:
            if tag in self.tag_index:
                matching_ids.update(self.tag_index[tag])

        # 转换为记忆对象
        memories = [
            self.multimodal_memories[mem_id]
            for mem_id in matching_ids
            if mem_id in self.multimodal_memories
        ]

        # 按重要性排序
        memories.sort(key=lambda m: m.importance_score, reverse=True)

        return memories[:top_k]

    def adjust_priorities(self):
        """
        自动调整记忆优先级

        基于访问频率和时间衰减调整重要性。
        """
        current_time = time.time()

        for memory in self.multimodal_memories.values():
            # 访问频率因子
            access_factor = 1.0 + (memory.access_count * 0.1)

            # 时间衰减因子
            age = current_time - memory.timestamp
            time_decay = np.exp(-age / (30 * 24 * 3600))  # 30天半衰期

            # 调整重要性
            original_importance = memory.importance_score
            memory.importance_score = original_importance * access_factor * time_decay

            # 限制范围
            memory.importance_score = max(0.1, min(1.0, memory.importance_score))

        self.stats['priority_adjustments'] += 1

        logger.debug(f"Priorities adjusted for {len(self.multimodal_memories)} memories")

    def _cleanup_memories(self):
        """
        清理过期和低重要性的记忆

        保留策略:
        1. 保留高重要性记忆
        2. 保留最近访问的记忆
        3. 按照模态平衡保留
        """
        if not self.auto_cleanup_enabled:
            return

        current_time = time.time()
        memories_to_remove = []

        # 识别需要清理的记忆
        for memory in self.multimodal_memories.values():
            # 检查是否过期(30天未访问)
            age = current_time - memory.timestamp
            if age > 30 * 24 * 3600 and memory.importance_score < 0.3:
                memories_to_remove.append(memory.memory_id)
                continue

            # 如果仍然超过最大数量,删除最低重要性的
            if len(self.multimodal_memories) > self.max_memories * 0.9:
                if memory.importance_score < 0.2:
                    memories_to_remove.append(memory.memory_id)

        # 执行删除
        for mem_id in memories_to_remove:
            self._remove_memory(mem_id)

        self.stats['cleanup_count'] += 1
        self.last_cleanup_time = current_time

        if memories_to_remove:
            logger.info(f"Cleaned up {len(memories_to_remove)} memories")

    def _remove_memory(self, memory_id: str):
        """
        移除记忆

        Args:
            memory_id: 记忆ID
        """
        if memory_id not in self.multimodal_memories:
            return

        memory = self.multimodal_memories[memory_id]

        # 更新统计
        self.stats['total_memories'] -= 1
        self.stats['by_modality'][memory.modality] -= 1

        # 移除标签索引
        for tag in memory.tags:
            if tag in self.tag_index and memory_id in self.tag_index[tag]:
                self.tag_index[tag].remove(memory_id)
                if not self.tag_index[tag]:
                    del self.tag_index[tag]

        # 移除记忆
        del self.multimodal_memories[memory_id]

    def _calculate_importance(self,
                              text: str,
                              modality: ModalityType,
                              entity_count: int = 0) -> float:
        """
        计算记忆重要性

        Args:
            text: 文本内容
            modality: 模态类型
            entity_count: 实体数量

        Returns:
            重要性分数(0.0-1.0)
        """
        # 内容长度因子
        length_factor = min(len(text) / 500, 1.0)

        # 实体数量因子
        entity_factor = min(entity_count / 10, 1.0)

        # 模态因子(多模态更重要)
        modality_factor = 1.0
        if modality == ModalityType.MULTIMODAL:
            modality_factor = 1.2
        elif modality in [ModalityType.AUDIO, ModalityType.VISUAL]:
            modality_factor = 1.1

        # 加权计算
        importance = (
            self.importance_weights['content_length'] * length_factor +
            self.importance_weights['entity_count'] * entity_factor +
            self.importance_weights['interaction_type'] * modality_factor
        )

        # 归一化到0.0-1.0
        importance = max(0.1, min(1.0, importance))

        return importance

    def _generate_memory_id(self) -> str:
        """生成唯一的记忆ID"""
        import uuid
        return f"mm_{uuid.uuid4().hex[:16]}_{int(time.time())}"

    def get_stats(self) -> Dict[str, Any]:
        """
        获取系统统计信息

        Returns:
            统计数据字典
        """
        return {
            'total_memories': self.stats['total_memories'],
            'by_modality': {
                k.value: v for k, v in self.stats['by_modality'].items()
            },
            'cleanup_count': self.stats['cleanup_count'],
            'priority_adjustments': self.stats['priority_adjustments'],
            'tag_count': len(self.tag_index),
            'last_cleanup_time': self.last_cleanup_time
        }

    def clear_all(self):
        """清空所有记忆"""
        self.multimodal_memories.clear()
        self.tag_index.clear()
        self.stats['total_memories'] = 0
        for k in self.stats['by_modality']:
            self.stats['by_modality'][k] = 0

        logger.info("All multimodal memories cleared")
