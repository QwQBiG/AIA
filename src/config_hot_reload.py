"""
配置热重载系统

实现配置文件的实时监听和热重载,
支持运行时配置修改,无需重启系统。
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from threading import Thread, Lock, Event
import asyncio


logger = logging.getLogger(__name__)


class ConfigHotReload:
    """
    配置热重载管理器

    功能:
    1. 监听配置文件变化
    2. 自动验证配置有效性
    3. 安全热重载(失败时恢复)
    4. 配置变更通知
    5. 线程安全的配置访问
    """

    def __init__(self,
                 config_path: str = "config.json",
                 check_interval: float = 2.0,
                 enable_validation: bool = True):
        """
        初始化配置热重载管理器

        Args:
            config_path: 配置文件路径
            check_interval: 文件检查间隔(秒)
            enable_validation: 是否启用配置验证
        """
        self.config_path = Path(config_path)
        self.check_interval = check_interval
        self.enable_validation = enable_validation

        # 配置数据
        self.config_data: Dict[str, Any] = {}
        self.config_lock = Lock()

        # 文件监控
        self.last_modified_time: float = 0.0
        self.file_watcher_thread: Optional[Thread] = None
        self.stop_event = Event()

        # 回调函数
        self.config_change_callbacks: List[Callable[[Dict, Dict], None]] = []

        # 备份配置
        self.backup_config: Optional[Dict[str, Any]] = None

        # 配置验证模式(JSON Schema)
        self.config_schema: Optional[Dict[str, Any]] = None

        # 统计信息
        self.stats = {
            'total_reloads': 0,
            'successful_reloads': 0,
            'failed_reloads': 0,
            'validation_failures': 0,
            'last_reload_time': 0.0
        }

        # 加载初始配置
        self._load_initial_config()

        logger.info(f"ConfigHotReload initialized: path={config_path}, interval={check_interval}s")

    def _load_initial_config(self):
        """加载初始配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)

            # 记录最后修改时间
            self.last_modified_time = self.config_path.stat().st_mtime

            # 创建备份
            self.backup_config = self.config_data.copy()

            logger.info(f"Initial configuration loaded: {self.config_path}")

        except Exception as e:
            logger.error(f"Failed to load initial config: {e}")
            raise

    def start_monitoring(self):
        """启动文件监控线程"""
        if self.file_watcher_thread and self.file_watcher_thread.is_alive():
            logger.warning("File watcher already running")
            return

        self.stop_event.clear()
        self.file_watcher_thread = Thread(
            target=self._file_watcher_loop,
            name="ConfigHotReload-Watcher",
            daemon=True
        )
        self.file_watcher_thread.start()

        logger.info("Config file monitoring started")

    def stop_monitoring(self):
        """停止文件监控"""
        self.stop_event.set()

        if self.file_watcher_thread:
            self.file_watcher_thread.join(timeout=2.0)

        logger.info("Config file monitoring stopped")

    def _file_watcher_loop(self):
        """文件监控循环"""
        logger.info("File watcher loop started")

        while not self.stop_event.is_set():
            try:
                # 检查文件修改时间
                try:
                    current_mtime = self.config_path.stat().st_mtime

                    if current_mtime > self.last_modified_time:
                        logger.info(f"Config file changed: {self.config_path}")
                        self._handle_config_change()

                        self.last_modified_time = current_mtime

                except FileNotFoundError:
                    logger.warning(f"Config file not found: {self.config_path}")

                # 等待下一次检查
                self.stop_event.wait(self.check_interval)

            except Exception as e:
                logger.error(f"Error in file watcher loop: {e}")
                self.stop_event.wait(1.0)  # 错误后等待1秒

        logger.info("File watcher loop stopped")

    def _handle_config_change(self):
        """
        处理配置文件变化

        1. 读取新配置
        2. 验证配置
        3. 备份旧配置
        4. 应用新配置
        5. 触发回调
        """
        try:
            logger.info("Processing config change...")

            # 读取新配置
            with open(self.config_path, 'r', encoding='utf-8') as f:
                new_config = json.load(f)

            # 验证配置
            if self.enable_validation:
                if not self._validate_config(new_config):
                    logger.error("Config validation failed, keeping old config")
                    self.stats['validation_failures'] += 1
                    return

            # 获取旧配置
            old_config = self.get_config()

            # 更新配置
            with self.config_lock:
                self.config_data = new_config

            # 更新备份
            self.backup_config = old_config

            # 更新统计
            self.stats['total_reloads'] += 1
            self.stats['successful_reloads'] += 1
            self.stats['last_reload_time'] = time.time()

            logger.info("Config reloaded successfully")

            # 触发回调
            self._trigger_callbacks(old_config, new_config)

        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
            self.stats['failed_reloads'] += 1

            # 尝试恢复备份
            if self.backup_config:
                with self.config_lock:
                    self.config_data = self.backup_config
                logger.warning("Restored backup config")

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证配置有效性

        Args:
            config: 配置字典

        Returns:
            bool: 配置是否有效
        """
        # 如果有schema,使用schema验证
        if self.config_schema:
            try:
                import jsonschema
                from jsonschema import validate

                validate(instance=config, schema=self.config_schema)
                return True

            except ImportError:
                logger.warning("jsonschema not installed, skipping validation")
                return True
            except jsonschema.ValidationError as e:
                logger.error(f"Config validation error: {e}")
                return False

        # 默认验证: 检查必需字段
        required_fields = ['ollama_url', 'ollama_model', 'vts_port']

        for field in required_fields:
            if field not in config:
                logger.error(f"Missing required field: {field}")
                return False

        return True

    def _trigger_callbacks(self, old_config: Dict, new_config: Dict):
        """
        触发配置变更回调

        Args:
            old_config: 旧配置
            new_config: 新配置
        """
        for callback in self.config_change_callbacks:
            try:
                callback(old_config, new_config)
            except Exception as e:
                logger.error(f"Config callback error: {e}")

    def get_config(self) -> Dict[str, Any]:
        """
        获取当前配置(线程安全)

        Returns:
            配置字典
        """
        with self.config_lock:
            return self.config_data.copy()

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项(线程安全)

        Args:
            key: 配置键(支持点分隔,如'ollama.url')
            default: 默认值

        Returns:
            配置值
        """
        with self.config_lock:
            # 支持点分隔键
            keys = key.split('.')

            value = self.config_data
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default

            return value

    def set(self, key: str, value: Any):
        """
        设置配置项(线程安全)

        Args:
            key: 配置键
            value: 配置值
        """
        with self.config_lock:
            # 支持点分隔键
            keys = key.split('.')

            config = self.config_data
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]

            config[keys[-1]] = value

        logger.debug(f"Config item set: {key} = {value}")

    def register_callback(self, callback: Callable[[Dict, Dict], None]):
        """
        注册配置变更回调

        Args:
            callback: 回调函数(old_config, new_config)
        """
        self.config_change_callbacks.append(callback)
        logger.info(f"Config callback registered: {callback.__name__}")

    def unregister_callback(self, callback: Callable[[Dict, Dict], None]):
        """
        取消注册配置变更回调

        Args:
            callback: 回调函数
        """
        if callback in self.config_change_callbacks:
            self.config_change_callbacks.remove(callback)
            logger.info(f"Config callback unregistered: {callback.__name__}")

    def reload(self) -> bool:
        """
        手动触发配置重载

        Returns:
            bool: 重载是否成功
        """
        logger.info("Manual config reload requested")
        self.last_modified_time = 0  # 强制重载
        self._handle_config_change()
        return self.stats['successful_reloads'] > self.stats['total_reloads'] - 1

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计数据
        """
        return self.stats.copy()

    def export_config(self, output_path: str):
        """
        导出当前配置到文件

        Args:
            output_path: 输出文件路径
        """
        try:
            config = self.get_config()

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            logger.info(f"Config exported to {output_path}")

        except Exception as e:
            logger.error(f"Failed to export config: {e}")

    def restore_backup(self) -> bool:
        """
        恢复备份配置

        Returns:
            bool: 是否成功恢复
        """
        if not self.backup_config:
            logger.warning("No backup config available")
            return False

        try:
            with self.config_lock:
                self.config_data = self.backup_config.copy()

            logger.info("Backup config restored")
            return True

        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False

    def shutdown(self):
        """关闭热重载系统"""
        self.stop_monitoring()
        logger.info("ConfigHotReload shutdown complete")


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    # 创建配置热重载管理器
    config_manager = ConfigHotReload(
        config_path="config.json",
        check_interval=2.0
    )

    # 定义配置变更回调
    def on_config_changed(old_config, new_config):
        logger.info(f"Config changed: {old_config.get('ollama_model')} -> {new_config.get('ollama_model')}")

    # 注册回调
    config_manager.register_callback(on_config_changed)

    # 启动监控
    config_manager.start_monitoring()

    try:
        # 主循环
        while True:
            time.sleep(1)

            # 获取配置
            ollama_model = config_manager.get('ollama_model')
            print(f"Current model: {ollama_model}")

    except KeyboardInterrupt:
        print("\nShutting down...")

    finally:
        # 清理
        config_manager.shutdown()
