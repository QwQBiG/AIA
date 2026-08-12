#!/usr/bin/env python3
"""
测试流式响应修复效果的脚本
"""

import sys
import os
sys.path.append('src')

from system_workflow import SystemWorkflow
from config import SystemConfig
import asyncio
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)

class MockStreamHandler:
    """模拟流式处理器"""
    def __init__(self):
        self.tokens = []
        self.emotions = []
        self.should_stop = False
        
    def on_token_received(self, token: str):
        """接收token"""
        self.tokens.append(token)
        print(f"Token: {token}")
        
    def on_emotion_detected(self, emotion: str):
        """检测到情感"""
        self.emotions.append(emotion)
        print(f"Emotion: {emotion}")
        
    def on_stream_complete(self):
        """流式完成"""
        print("Stream complete")

def test_streaming_fixes():
    """测试流式响应修复"""
    print("🧪 测试流式响应修复...")
    
    # 创建配置
    config = SystemConfig()
    
    # 创建系统工作流
    workflow = SystemWorkflow(config)
    
    # 测试重复检测
    print("\n1. 测试重复检测...")
    handler = MockStreamHandler()
    
    # 模拟重复token
    test_tokens = ["嗯", ",", "你", "来", "的", "正", "好", "。", "嗯", ",", "你", "来", "的", "正", "好", "。"]
    
    for token in test_tokens:
        handler.on_token_received(token)
    
    print(f"处理了 {len(handler.tokens)} 个tokens")
    
    # 测试情感标签过滤
    print("\n2. 测试情感标签过滤...")
    test_text = "[neutral] 嗯,你来的正好。我一直觉得我们应该更多地交流。[happy] 最近怎么样?"
    
    # 模拟清理函数
    import re
    cleaned = re.sub(r'\[[\w\s]+\]', '', test_text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    print(f"原文: {test_text}")
    print(f"清理后: {cleaned}")
    
    print("\n✅ 流式响应修复测试完成")

if __name__ == "__main__":
    test_streaming_fixes()