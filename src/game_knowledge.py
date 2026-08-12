"""
游戏知识库 - 游戏模板和配置文件的存储与管理

本模块负责管理游戏特定的模板、配置和元数据。
每个游戏都有独立的配置文件（profile.json）和模板目录。

目录结构：
    assets/games/
    └── {game-name}/
        ├── profile.json      # 游戏配置文件
        └── templates/        # 模板图片目录
            ├── button.png
            └── target.png

配置文件格式 (profile.json):
    {
        "display_name": "游戏显示名称",
        "description": "游戏描述",
        "vlm_prompts": ["VLM 提示词列表"],
        "default_templates": {"模板名": "文件名"},
        "action_cooldowns": {"动作名": 冷却时间}
    }

使用示例：
    knowledge = GameKnowledge()
    
    # 创建新游戏配置
    knowledge.create_profile("cookie-clicker", {
        "display_name": "Cookie Clicker",
        "description": "点击饼干游戏",
        "vlm_prompts": ["点击大饼干"],
        "default_templates": {"cookie": "cookie.png"}
    })
    
    # 加载游戏配置
    profile = knowledge.load_profile("cookie-clicker")
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GameProfile:
    """
    游戏配置数据类
    
    属性:
        game_name: 游戏标识符（kebab-case 格式，如 "cookie-clicker"）
        display_name: 游戏显示名称
        description: 游戏描述
        vlm_prompts: VLM 分析时使用的提示词列表
        default_templates: 默认模板映射 {模板名: 文件名}
        action_cooldowns: 动作冷却时间映射 {动作名: 秒数}
        templates_path: 模板目录的完整路径
    """
    game_name: str
    display_name: str
    description: str
    vlm_prompts: List[str]
    default_templates: Dict[str, str]  # 模板名 -> 文件名
    action_cooldowns: Dict[str, float]
    templates_path: str  # 模板目录完整路径


class GameKnowledge:
    """
    游戏知识库管理器
    
    负责创建、加载和管理游戏配置文件及其关联的模板图片。
    所有游戏数据存储在 base_path 指定的目录下。
    
    属性:
        base_path: 游戏数据根目录（默认 "assets/games"）
    """
    
    def __init__(self, base_path: str = "assets/games"):
        """
        初始化游戏知识库
        
        参数:
            base_path: 游戏配置文件的根目录
        """
        self.base_path = Path(base_path)
        self._profiles: Dict[str, GameProfile] = {}  # 配置缓存
        
        # 创建根目录（如果不存在）
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"游戏知识库初始化完成，根目录={base_path}")
    
    def create_profile(self, game_name: str, profile_data: Dict[str, Any]) -> bool:
        """
        创建新的游戏配置
        
        会自动创建游戏目录和模板子目录，并保存配置文件。
        
        参数:
            game_name: 游戏标识符（kebab-case 格式，如 "cookie-clicker"）
            profile_data: 配置数据字典，必须包含：
                - display_name: str - 显示名称
                - description: str - 游戏描述
                - vlm_prompts: List[str] - VLM 提示词
                - default_templates: Dict[str, str] - 默认模板
                - action_cooldowns: Dict[str, float] - 动作冷却（可选）
                
        返回:
            True: 创建成功
            False: 配置已存在或创建失败
        """
        game_path = self.base_path / game_name
        
        # 检查是否已存在
        if game_path.exists():
            logger.warning(f"游戏配置已存在: {game_name}")
            return False
        
        try:
            # 创建目录结构
            game_path.mkdir(parents=True, exist_ok=True)
            templates_path = game_path / "templates"
            templates_path.mkdir(exist_ok=True)
            
            # 验证必需字段
            required_fields = ["display_name", "description", "vlm_prompts", "default_templates"]
            for field in required_fields:
                if field not in profile_data:
                    logger.error(f"缺少必需字段: {field}")
                    return False
            
            # 添加默认的动作冷却配置
            if "action_cooldowns" not in profile_data:
                profile_data["action_cooldowns"] = {}
            
            # 保存配置文件
            profile_path = game_path / "profile.json"
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"游戏配置创建成功: {game_name}")
            return True
            
        except Exception as e:
            logger.error(f"创建游戏配置失败: {e}", exc_info=True)
            return False
    
    def save_template(self, game_name: str, template_name: str, image: np.ndarray) -> str:
        """
        保存模板图片到游戏的模板目录
        
        参数:
            game_name: 游戏标识符
            template_name: 模板名称（不含扩展名）
            image: 裁剪后的图片（numpy 数组格式）
            
        返回:
            保存的模板文件完整路径
        """
        templates_path = self.base_path / game_name / "templates"
        
        # 创建模板目录（如果不存在）
        templates_path.mkdir(parents=True, exist_ok=True)
        
        # 保存为 PNG 格式
        template_path = templates_path / f"{template_name}.png"
        cv2.imwrite(str(template_path), image)
        
        logger.info(f"模板已保存: {template_path}")
        return str(template_path)
    
    def load_profile(self, game_name: str) -> Optional[GameProfile]:
        """
        从磁盘加载游戏配置
        
        加载成功后会缓存配置，后续调用直接返回缓存。
        
        参数:
            game_name: 游戏标识符
            
        返回:
            GameProfile: 游戏配置对象
            None: 配置不存在或加载失败
        """
        game_path = self.base_path / game_name
        profile_path = game_path / "profile.json"
        
        if not profile_path.exists():
            logger.error(f"游戏配置不存在: {game_name}")
            return None
        
        try:
            # 读取配置文件
            with open(profile_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 验证必需字段
            required_fields = ["display_name", "description", "vlm_prompts", "default_templates"]
            for field in required_fields:
                if field not in data:
                    logger.error(f"配置文件无效: 缺少字段 {field}")
                    return None
            
            # 创建 GameProfile 对象
            templates_path = str(game_path / "templates")
            profile = GameProfile(
                game_name=game_name,
                display_name=data["display_name"],
                description=data["description"],
                vlm_prompts=data["vlm_prompts"],
                default_templates=data["default_templates"],
                action_cooldowns=data.get("action_cooldowns", {}),
                templates_path=templates_path
            )
            
            # 缓存配置
            self._profiles[game_name] = profile
            
            logger.info(f"游戏配置加载成功: {game_name}")
            return profile
            
        except json.JSONDecodeError as e:
            logger.error(f"配置文件 JSON 格式错误: {e}")
            return None
        except Exception as e:
            logger.error(f"加载游戏配置失败: {e}", exc_info=True)
            return None
    
    def list_templates(self, game_name: str) -> List[str]:
        """
        获取游戏的所有模板文件路径列表
        
        参数:
            game_name: 游戏标识符
            
        返回:
            模板文件完整路径列表（PNG 文件）
        """
        templates_path = self.base_path / game_name / "templates"
        
        if not templates_path.exists():
            logger.warning(f"模板目录不存在: {game_name}")
            return []
        
        # 查找所有 PNG 文件
        template_files = list(templates_path.glob("*.png"))
        template_paths = [str(f) for f in template_files]
        
        logger.info(f"找到 {len(template_paths)} 个模板文件 ({game_name})")
        return template_paths
    
    def get_template_path(self, game_name: str, template_name: str) -> Optional[str]:
        """
        获取指定模板的完整路径
        
        参数:
            game_name: 游戏标识符
            template_name: 模板名称（可带或不带 .png 扩展名）
            
        返回:
            模板文件完整路径
            None: 模板不存在
        """
        # 自动添加 .png 扩展名
        if not template_name.endswith('.png'):
            template_name = f"{template_name}.png"
        
        template_path = self.base_path / game_name / "templates" / template_name
        
        if template_path.exists():
            return str(template_path)
        else:
            logger.warning(f"模板不存在: {template_path}")
            return None
