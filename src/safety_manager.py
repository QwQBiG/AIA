"""
安全管理器 - AI VTuber 紧急停止和安全验证系统

本模块实现紧急停止机制和安全验证系统，
包括 F9 热键监听和全局安全协调。

核心功能：
- F9 紧急停止热键
- 全局安全状态管理
- 紧急回调机制
- TTS 紧急通知

使用示例：
    safety = SafetyManager(config, tts_pipeline)
    safety.setup_emergency_hotkey(action_engine)
    
    # 检查是否允许执行动作
    if safety.is_action_allowed():
        execute_action()
    
    # 手动触发紧急停止
    safety.trigger_emergency_stop()
"""

import logging
import threading
import time
from typing import Optional, Callable
from datetime import datetime

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    logging.warning("pynput 不可用，紧急热键功能将无法使用")


class SafetyManager:
    """
    安全管理器 - 实现紧急停止和安全验证系统
    
    提供全局安全状态管理，支持 F9 热键紧急停止，
    并可通过回调机制通知其他组件。
    
    属性:
        emergency_active: 紧急停止是否激活
        hotkey_enabled: 热键是否启用
        emergency_key: 紧急停止热键（默认 F9）
    """
    
    def __init__(self, config: dict = None, tts_pipeline=None):
        """
        初始化安全管理器
        
        参数:
            config: 配置字典，包含：
                - enable_emergency_hotkey: 是否启用热键（默认 True）
                - emergency_key: 热键名称（默认 "<f9>"）
                - enable_tts_announcement: 是否启用 TTS 通知（默认 True）
            tts_pipeline: TTS 管道实例（用于紧急通知）
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # 紧急状态
        self.emergency_active = False
        self.emergency_timestamp: Optional[datetime] = None
        
        # 热键监听器
        self.hotkey_listener: Optional[keyboard.GlobalHotKeys] = None
        self.listener_thread: Optional[threading.Thread] = None
        self.hotkey_enabled = self.config.get('enable_emergency_hotkey', True)
        self.emergency_key = self.config.get('emergency_key', '<f9>')
        
        # TTS 管道
        self.tts_pipeline = tts_pipeline
        self.enable_tts_announcement = self.config.get('enable_tts_announcement', True)
        
        # 紧急回调列表
        self.emergency_callbacks: list[Callable] = []
        
        # 线程安全锁
        self.state_lock = threading.Lock()
        
        self.logger.info(f"安全管理器初始化完成，紧急热键: {self.emergency_key}")
    
    def setup_emergency_hotkey(self, action_engine=None):
        """
        设置 F9 全局热键监听器
        
        参数:
            action_engine: ActionEngine 实例（用于停止动作）
            
        返回:
            True: 设置成功
            False: 设置失败
        """
        if not PYNPUT_AVAILABLE:
            self.logger.error("无法设置紧急热键 - pynput 不可用")
            return False
        
        if not self.hotkey_enabled:
            self.logger.info("紧急热键已在配置中禁用")
            return False
        
        try:
            # 保存 action_engine 引用
            if action_engine:
                self.add_emergency_callback(action_engine.emergency_stop)
            
            # 创建热键映射
            hotkey_map = {
                self.emergency_key: self._on_emergency_hotkey
            }
            
            # 在守护线程中启动热键监听器
            self.listener_thread = threading.Thread(
                target=self._run_hotkey_listener,
                args=(hotkey_map,),
                daemon=True
            )
            self.listener_thread.start()
            
            self.logger.info(f"紧急热键 {self.emergency_key} 监听器已启动")
            return True
            
        except Exception as e:
            self.logger.error(f"设置紧急热键失败: {e}")
            return False
    
    def _run_hotkey_listener(self, hotkey_map: dict):
        """运行热键监听器（在独立线程中）"""
        try:
            self.logger.info("启动全局热键监听器...")
            
            # 创建全局热键监听器
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)
            
            # 启动监听器
            self.hotkey_listener.start()
            
            # 保持监听器运行
            self.hotkey_listener.join()
                    
        except Exception as e:
            self.logger.error(f"热键监听器错误: {e}")
        finally:
            if self.hotkey_listener:
                try:
                    self.hotkey_listener.stop()
                except:
                    pass
    
    def _on_emergency_hotkey(self):
        """处理紧急热键按下事件"""
        self.logger.warning(f"紧急热键 {self.emergency_key} 被按下！")
        self.trigger_emergency_stop()
    
    def trigger_emergency_stop(self):
        """触发紧急停止，停止所有系统"""
        with self.state_lock:
            if self.emergency_active:
                self.logger.info("紧急停止已激活")
                return
            
            self.emergency_active = True
            self.emergency_timestamp = datetime.now()
            
            self.logger.critical("紧急停止已激活")
            
            # 通过 TTS 通知
            self._announce_emergency_stop()
            
            # 调用所有注册的紧急回调
            for callback in self.emergency_callbacks:
                try:
                    callback()
                except Exception as e:
                    self.logger.error(f"紧急回调执行失败: {e}")
            
            # 记录紧急事件
            self._log_emergency_event("紧急停止已激活")
    
    def reset_emergency_state(self):
        """重置紧急状态（需要手动干预）"""
        with self.state_lock:
            if not self.emergency_active:
                self.logger.info("紧急状态未激活")
                return
            
            self.emergency_active = False
            duration = None
            
            if self.emergency_timestamp:
                duration = datetime.now() - self.emergency_timestamp
            
            self.logger.info(f"紧急状态已重置（持续时间: {duration}）")
            self._log_emergency_event(f"紧急状态已重置，持续 {duration}")
            
            # 注意：不需要重启热键监听器，因为它应该一直运行
    
    def is_emergency_active(self) -> bool:
        """检查紧急停止是否激活"""
        return self.emergency_active
    
    def is_action_allowed(self) -> bool:
        """
        检查是否允许执行动作
        
        动作系统在执行任何操作前应调用此方法。
        
        返回:
            True: 允许执行
            False: 紧急停止激活，禁止执行
        """
        with self.state_lock:
            return not self.emergency_active
    
    def block_until_safe(self, timeout: Optional[float] = None) -> bool:
        """
        阻塞直到紧急状态解除
        
        参数:
            timeout: 最大等待时间（秒），None 表示无限等待
            
        返回:
            True: 紧急状态已解除
            False: 超时
        """
        if not self.emergency_active:
            return True
        
        start_time = time.time()
        
        while self.emergency_active:
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False
            
            time.sleep(0.01)
        
        return True
    
    def get_emergency_duration(self) -> Optional[float]:
        """获取当前紧急状态持续时间（秒）"""
        if not self.emergency_active or not self.emergency_timestamp:
            return None
        
        return (datetime.now() - self.emergency_timestamp).total_seconds()
    
    def add_emergency_callback(self, callback: Callable):
        """
        添加紧急停止回调
        
        参数:
            callback: 紧急停止时调用的函数（不应抛出异常）
        """
        if callback not in self.emergency_callbacks:
            self.emergency_callbacks.append(callback)
            callback_name = getattr(callback, '__name__', str(callback))
            self.logger.debug(f"已添加紧急回调: {callback_name}")
    
    def remove_emergency_callback(self, callback: Callable):
        """移除紧急回调"""
        if callback in self.emergency_callbacks:
            self.emergency_callbacks.remove(callback)
            callback_name = getattr(callback, '__name__', str(callback))
            self.logger.debug(f"已移除紧急回调: {callback_name}")
    
    def validate_system_safety(self) -> dict:
        """
        验证系统整体安全状态
        
        返回:
            包含安全状态信息的字典
        """
        with self.state_lock:
            safety_status = {
                'emergency_active': self.emergency_active,
                'emergency_duration': self.get_emergency_duration(),
                'hotkey_enabled': self.hotkey_enabled,
                'hotkey_available': PYNPUT_AVAILABLE,
                'listener_active': self.listener_thread and self.listener_thread.is_alive(),
                'callback_count': len(self.emergency_callbacks),
                'timestamp': datetime.now(),
                'actions_allowed': not self.emergency_active,
                'state_lock_acquired': True
            }
        
        return safety_status
    
    def force_emergency_reset(self, reason: str = "手动重置"):
        """
        强制重置紧急状态（管理员使用）
        
        参数:
            reason: 重置原因（记录到日志）
        """
        with self.state_lock:
            if not self.emergency_active:
                self.logger.info("强制重置请求，但紧急状态未激活")
                return
            
            old_duration = self.get_emergency_duration()
            self.emergency_active = False
            
            self.logger.warning(f"强制紧急重置: {reason} (持续 {old_duration}秒)")
            self._log_emergency_event(f"强制紧急重置: {reason}")
            
            # 重启热键监听器
            if self.hotkey_enabled and PYNPUT_AVAILABLE:
                self.setup_emergency_hotkey()
    
    def _log_emergency_event(self, event_description: str):
        """记录紧急事件（审计追踪）"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[安全] {timestamp}: {event_description}"
        self.logger.critical(log_entry)
    
    def _announce_emergency_stop(self):
        """通过 TTS 通知紧急停止"""
        if not self.enable_tts_announcement or not self.tts_pipeline:
            return
        
        try:
            import asyncio
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.tts_pipeline.put_text("紧急停止已激活"))
                else:
                    loop.run_until_complete(self.tts_pipeline.put_text("紧急停止已激活"))
            except RuntimeError:
                asyncio.run(self.tts_pipeline.put_text("紧急停止已激活"))
            
            self.logger.info("紧急停止通知已发送到 TTS")
            
        except Exception as e:
            self.logger.error(f"TTS 紧急通知失败: {e}")
    
    def set_tts_pipeline(self, tts_pipeline):
        """设置或更新 TTS 管道引用"""
        self.tts_pipeline = tts_pipeline
        self.logger.debug("TTS 管道引用已更新")
    
    def test_emergency_system(self) -> bool:
        """
        测试紧急系统功能（开发/测试用）
        
        返回:
            True: 测试通过
            False: 测试失败
        """
        try:
            self.trigger_emergency_stop()
            if not self.emergency_active:
                return False
            
            self.reset_emergency_state()
            if self.emergency_active:
                return False
            
            self.logger.info("紧急系统测试通过")
            return True
            
        except Exception as e:
            self.logger.error(f"紧急系统测试失败: {e}")
            return False
    
    def shutdown(self):
        """安全关闭安全管理器"""
        self.logger.info("安全管理器正在关闭...")
        
        # 停止热键监听器
        if self.listener_thread and self.listener_thread.is_alive():
            self.emergency_active = True  # 这会停止监听器循环
            self.listener_thread.join(timeout=2.0)
        
        # 清除回调
        self.emergency_callbacks.clear()
        
        self.logger.info("安全管理器关闭完成")
    
    def __del__(self):
        """析构时清理"""
        try:
            self.shutdown()
        except Exception:
            pass
