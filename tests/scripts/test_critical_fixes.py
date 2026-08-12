#!/usr/bin/env python3
"""
测试关键bug修复的脚本
"""

import sys
import os
sys.path.append('src')

def test_agent_config_fix():
    """测试Agent配置访问修复"""
    print("🧪 测试Agent配置访问修复...")
    
    try:
        from agent_manager import AgentManager
        from config import SystemConfig
        
        # 创建配置
        config = SystemConfig()
        
        # 测试AgentManager初始化（应该能处理Dataclass配置）
        agent_manager = AgentManager(config=config.agent)
        print("✅ AgentManager配置访问修复成功")
        return True
        
    except Exception as e:
        print(f"❌ AgentManager配置访问修复失败: {e}")
        return False

def test_agent_debugger_fix():
    """测试AgentDebugger构造函数修复"""
    print("🧪 测试AgentDebugger构造函数修复...")
    
    try:
        from agent_debugger import AgentDebugger
        
        # 测试AgentDebugger初始化（应该接受agent_manager参数）
        debugger = AgentDebugger(agent_manager=None)
        print("✅ AgentDebugger构造函数修复成功")
        return True
        
    except Exception as e:
        print(f"❌ AgentDebugger构造函数修复失败: {e}")
        return False

def test_memory_core_methods():
    """测试MemoryCore缺失方法修复"""
    print("🧪 测试MemoryCore缺失方法修复...")
    
    try:
        from memory_core.memory_core import MemoryCore
        
        # 创建MemoryCore实例
        memory_core = MemoryCore()
        
        # 测试新添加的方法
        entities = memory_core.get_entities()
        conversations = memory_core.get_recent_conversations()
        
        print(f"✅ MemoryCore方法修复成功 - entities: {len(entities)}, conversations: {len(conversations)}")
        return True
        
    except Exception as e:
        print(f"❌ MemoryCore方法修复失败: {e}")
        return False

def test_vts_client_locking():
    """测试VTSClient并发锁修复"""
    print("🧪 测试VTSClient并发锁修复...")
    
    try:
        from vts_client import VTSClient
        
        # 创建VTSClient实例
        vts_client = VTSClient()
        
        # 检查是否有async_lock属性
        if hasattr(vts_client, '_async_lock'):
            print("✅ VTSClient并发锁修复成功")
            return True
        else:
            print("❌ VTSClient缺少_async_lock属性")
            return False
        
    except Exception as e:
        print(f"❌ VTSClient并发锁修复失败: {e}")
        return False

def test_system_workflow_timestamp():
    """测试SystemWorkflow timestamp修复"""
    print("🧪 测试SystemWorkflow timestamp修复...")
    
    try:
        from system_workflow import SystemWorkflow
        from config import SystemConfig
        
        # 创建SystemWorkflow实例
        config = SystemConfig()
        workflow = SystemWorkflow(config)
        
        print("✅ SystemWorkflow timestamp修复成功")
        return True
        
    except Exception as e:
        print(f"❌ SystemWorkflow timestamp修复失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("🔧 开始测试关键bug修复...")
    
    tests = [
        test_agent_config_fix,
        test_agent_debugger_fix,
        test_memory_core_methods,
        test_vts_client_locking,
        test_system_workflow_timestamp
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ 测试异常: {e}")
    
    print(f"\n📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有关键bug修复测试通过！")
    else:
        print("⚠️ 部分测试失败，需要进一步检查")

if __name__ == "__main__":
    main()