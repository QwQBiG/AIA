"""
动态模板管理器

实现游戏模板的动态加载、扩展和坐标自适应学习,
大幅增强Agent系统的灵活性和适应性。
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import numpy as np
from collections import deque


logger = logging.getLogger(__name__)


@dataclass
class GameTemplate:
    """游戏模板"""
    template_id: str
    game_name: str
    template_type: str  # "action", "ui", "coordinate"
    template_data: Dict[str, Any]
    confidence: float = 1.0  # 模板置信度
    usage_count: int = 0
    last_used: float = 0.0
    adaptive_offset: tuple = (0, 0)  # 自适应坐标偏移


@dataclass
class CoordinateLearning:
    """坐标学习数据"""
    template_id: str
    original_coords: tuple
    corrected_coords: tuple
    confidence: float
    timestamp: float


class TemplateManager:
    """
    动态模板管理器

    功能:
    1. 动态模板加载(运行时加载/卸载)
    2. 模板扩展(用户自定义模板)
    3. 坐标自适应学习
    4. 模板置信度管理
    5. 模板性能监控
    """

    def __init__(self,
                 template_dir: str = "./assets/templates",
                 max_templates: int = 50):
        """
        初始化模板管理器

        Args:
            template_dir: 模板目录
            max_templates: 最大模板数量
        """
        self.template_dir = Path(template_dir)
        self.template_dir.mkdir(parents=True, exist_ok=True)

        self.max_templates = max_templates

        # 模板存储
        self.templates: Dict[str, GameTemplate] = {}

        # 坐标学习数据
        self.coordinate_learning: List[CoordinateLearning] = []

        # 模板性能统计
        self.template_stats: Dict[str, Dict[str, Any]] = {}

        # 加载所有内置模板
        self._load_builtin_templates()

        logger.info(f"TemplateManager initialized: dir={template_dir}, max={max_templates}")

    def load_template(self,
                     template_path: str,
                     template_id: Optional[str] = None) -> Optional[GameTemplate]:
        """
        从文件加载模板

        Args:
            template_path: 模板文件路径
            template_id: 模板ID(可选,自动生成)

        Returns:
            加载的模板对象
        """
        template_file = Path(template_path)

        if not template_file.exists():
            logger.error(f"Template file not found: {template_path}")
            return None

        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                template_data = json.load(f)

            # 生成模板ID
            if template_id is None:
                template_id = f"tpl_{template_file.stem}_{int(template_data.get('timestamp', 0))}"

            # 创建模板对象
            template = GameTemplate(
                template_id=template_id,
                game_name=template_data.get('game_name', 'Unknown'),
                template_type=template_data.get('type', 'action'),
                template_data=template_data,
                confidence=template_data.get('confidence', 1.0)
            )

            # 添加到存储
            self.templates[template_id] = template

            # 初始化统计
            self.template_stats[template_id] = {
                'success_rate': 1.0,
                'total_uses': 0,
                'successful_uses': 0,
                'avg_accuracy': 0.0
            }

            logger.info(f"Template loaded: {template_id} from {template_path}")

            return template

        except Exception as e:
            logger.error(f"Failed to load template {template_path}: {e}")
            return None

    def unload_template(self, template_id: str) -> bool:
        """
        卸载模板

        Args:
            template_id: 模板ID

        Returns:
            bool: 是否成功卸载
        """
        if template_id not in self.templates:
            logger.warning(f"Template not found: {template_id}")
            return False

        del self.templates[template_id]

        if template_id in self.template_stats:
            del self.template_stats[template_id]

        logger.info(f"Template unloaded: {template_id}")

        return True

    def get_template(self, template_id: str) -> Optional[GameTemplate]:
        """
        获取模板

        Args:
            template_id: 模板ID

        Returns:
            模板对象
        """
        template = self.templates.get(template_id)

        if template:
            # 更新使用统计
            template.usage_count += 1
            template.last_used = time.time()

        return template

    def get_templates_by_game(self, game_name: str) -> List[GameTemplate]:
        """
        按游戏名称获取模板

        Args:
            game_name: 游戏名称

        Returns:
            模板列表
        """
        return [
            template for template in self.templates.values()
            if template.game_name == game_name
        ]

    def get_templates_by_type(self, template_type: str) -> List[GameTemplate]:
        """
        按类型获取模板

        Args:
            template_type: 模板类型

        Returns:
            模板列表
        """
        return [
            template for template in self.templates.values()
            if template.template_type == template_type
        ]

    def add_custom_template(self,
                           template_id: str,
                           game_name: str,
                           template_type: str,
                           template_data: Dict[str, Any],
                           save_to_file: bool = True) -> GameTemplate:
        """
        添加自定义模板

        Args:
            template_id: 模板ID
            game_name: 游戏名称
            template_type: 模板类型
            template_data: 模板数据
            save_to_file: 是否保存到文件

        Returns:
            创建的模板对象
        """
        # 创建模板
        template = GameTemplate(
            template_id=template_id,
            game_name=game_name,
            template_type=template_type,
            template_data=template_data,
            confidence=template_data.get('confidence', 1.0)
        )

        # 存储模板
        self.templates[template_id] = template

        # 初始化统计
        self.template_stats[template_id] = {
            'success_rate': 1.0,
            'total_uses': 0,
            'successful_uses': 0,
            'avg_accuracy': 0.0
        }

        # 保存到文件
        if save_to_file:
            self._save_template_to_file(template)

        logger.info(f"Custom template added: {template_id}")

        return template

    def update_template_confidence(self,
                                  template_id: str,
                                  success: bool,
                                  accuracy: float = 1.0):
        """
        更新模板置信度

        Args:
            template_id: 模板ID
            success: 是否成功
            accuracy: 准确度(0.0-1.0)
        """
        if template_id not in self.template_stats:
            return

        stats = self.template_stats[template_id]

        # 更新统计
        stats['total_uses'] += 1

        if success:
            stats['successful_uses'] += 1

        # 计算成功率
        stats['success_rate'] = (
            stats['successful_uses'] / stats['total_uses']
        )

        # 更新平均准确度
        stats['avg_accuracy'] = (
            (stats['avg_accuracy'] * (stats['total_uses'] - 1) + accuracy) /
            stats['total_uses']
        )

        # 更新模板置信度(基于成功率和准确度)
        template = self.templates.get(template_id)
        if template:
            template.confidence = (
                stats['success_rate'] * 0.7 +
                stats['avg_accuracy'] * 0.3
            )

        logger.debug(f"Template confidence updated: {template_id} -> {template.confidence:.2f}")

    def learn_coordinate_adaptation(self,
                                    template_id: str,
                                    original_coords: tuple,
                                    corrected_coords: tuple,
                                    confidence: float = 1.0):
        """
        学习坐标自适应

        Args:
            template_id: 模板ID
            original_coords: 原始坐标
            corrected_coords: 修正后的坐标
            confidence: 置信度
        """
        # 创建学习记录
        learning = CoordinateLearning(
            template_id=template_id,
            original_coords=original_coords,
            corrected_coords=corrected_coords,
            confidence=confidence,
            timestamp=time.time()
        )

        # 添加到学习数据
        self.coordinate_learning.append(learning)

        # 限制学习数据大小
        if len(self.coordinate_learning) > 100:
            self.coordinate_learning.pop(0)

        # 计算自适应偏移
        offset_x = corrected_coords[0] - original_coords[0]
        offset_y = corrected_coords[1] - original_coords[1]

        # 更新模板的自适应偏移
        if template_id in self.templates:
            template = self.templates[template_id]

            # 加权平均偏移
            old_offset_x, old_offset_y = template.adaptive_offset

            new_offset_x = old_offset_x * 0.7 + offset_x * 0.3 * confidence
            new_offset_y = old_offset_y * 0.7 + offset_y * 0.3 * confidence

            template.adaptive_offset = (new_offset_x, new_offset_y)

        logger.debug(f"Coordinate adaptation learned: {template_id} offset={template.adaptive_offset}")

    def apply_coordinate_adaptation(self,
                                    template_id: str,
                                    coords: tuple) -> tuple:
        """
        应用坐标自适应

        Args:
            template_id: 模板ID
            coords: 原始坐标

        Returns:
            适应后的坐标
        """
        if template_id not in self.templates:
            return coords

        template = self.templates[template_id]
        offset_x, offset_y = template.adaptive_offset

        adapted_x = coords[0] + offset_x
        adapted_y = coords[1] + offset_y

        return (adapted_x, adapted_y)

    def get_high_confidence_templates(self,
                                     min_confidence: float = 0.8) -> List[GameTemplate]:
        """
        获取高置信度模板

        Args:
            min_confidence: 最小置信度

        Returns:
            模板列表
        """
        return [
            template for template in self.templates.values()
            if template.confidence >= min_confidence
        ]

    def _load_builtin_templates(self):
        """加载所有内置模板"""
        if not self.template_dir.exists():
            logger.info("No template directory found, skipping built-in templates")
            return

        # 查找所有模板文件
        template_files = list(self.template_dir.glob("*.json"))

        loaded_count = 0
        for template_file in template_files:
            try:
                if self.load_template(str(template_file)):
                    loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to load built-in template {template_file}: {e}")

        logger.info(f"Loaded {loaded_count}/{len(template_files)} built-in templates")

    def _save_template_to_file(self, template: GameTemplate):
        """
        保存模板到文件

        Args:
            template: 模板对象
        """
        try:
            # 准备数据
            template_data = template.template_data.copy()
            template_data['template_id'] = template.template_id
            template_data['game_name'] = template.game_name
            template_data['type'] = template.template_type
            template_data['confidence'] = template.confidence
            template_data['timestamp'] = int(time.time())
            template_data['adaptive_offset'] = template.adaptive_offset

            # 保存文件
            template_file = self.template_dir / f"{template.template_id}.json"

            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Template saved to file: {template_file}")

        except Exception as e:
            logger.error(f"Failed to save template {template.template_id}: {e}")

    def get_template_stats(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        获取模板统计信息

        Args:
            template_id: 模板ID

        Returns:
            统计信息字典
        """
        return self.template_stats.get(template_id)

    def get_system_stats(self) -> Dict[str, Any]:
        """
        获取系统统计信息

        Returns:
            系统统计数据
        """
        total_templates = len(self.templates)

        # 按类型统计
        by_type = {}
        for template in self.templates.values():
            by_type[template.template_type] = by_type.get(template.template_type, 0) + 1

        # 按游戏统计
        by_game = {}
        for template in self.templates.values():
            by_game[template.game_name] = by_game.get(template.game_name, 0) + 1

        # 计算平均置信度
        confidences = [t.confidence for t in self.templates.values()]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # 坐标学习统计
        coordinate_learning_count = len(self.coordinate_learning)

        return {
            'total_templates': total_templates,
            'max_templates': self.max_templates,
            'by_type': by_type,
            'by_game': by_game,
            'avg_confidence': avg_confidence,
            'coordinate_learning_records': coordinate_learning_count,
            'template_directory': str(self.template_dir)
        }

    def cleanup_low_confidence_templates(self, min_confidence: float = 0.3) -> int:
        """
        清理低置信度模板

        Args:
            min_confidence: 最小置信度阈值

        Returns:
            清理的模板数量
        """
        to_remove = [
            template_id
            for template_id, template in self.templates.items()
            if template.confidence < min_confidence
        ]

        for template_id in to_remove:
            self.unload_template(template_id)

        logger.info(f"Cleaned up {len(to_remove)} low confidence templates")

        return len(to_remove)

    def export_templates(self, output_path: str):
        """
        导出所有模板到文件

        Args:
            output_path: 输出文件路径
        """
        try:
            export_data = {
                'templates': [],
                'timestamp': int(time.time())
            }

            for template in self.templates.values():
                template_entry = {
                    'template_id': template.template_id,
                    'game_name': template.game_name,
                    'type': template.template_type,
                    'data': template.template_data,
                    'confidence': template.confidence,
                    'adaptive_offset': template.adaptive_offset
                }
                export_data['templates'].append(template_entry)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(export_data['templates'])} templates to {output_path}")

        except Exception as e:
            logger.error(f"Failed to export templates: {e}")

    def import_templates(self, input_path: str) -> int:
        """
        从文件导入模板

        Args:
            input_path: 输入文件路径

        Returns:
            导入的模板数量
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            imported_count = 0
            for template_entry in import_data.get('templates', []):
                template_id = template_entry['template_id']

                template = GameTemplate(
                    template_id=template_id,
                    game_name=template_entry['game_name'],
                    template_type=template_entry['type'],
                    template_data=template_entry['data'],
                    confidence=template_entry.get('confidence', 1.0),
                    adaptive_offset=tuple(template_entry.get('adaptive_offset', (0, 0)))
                )

                self.templates[template_id] = template
                self.template_stats[template_id] = {
                    'success_rate': 1.0,
                    'total_uses': 0,
                    'successful_uses': 0,
                    'avg_accuracy': 0.0
                }

                imported_count += 1

            logger.info(f"Imported {imported_count} templates from {input_path}")

            return imported_count

        except Exception as e:
            logger.error(f"Failed to import templates: {e}")
            return 0


# 添加time导入
import time
