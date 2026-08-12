# 记忆核心系统 (memory_core/)

## 🧠 系统概述
记忆核心系统是 AI VTuber 的长期记忆和知识管理模块，基于 ChromaDB 向量数据库实现，提供智能的对话记忆、实体识别和知识检索功能。

## 🏗️ 架构设计
```
memory_core/
├── memory_core.py      # 核心记忆管理器
├── memory_manager.py   # 记忆管理接口
├── data_models.py      # 数据模型定义
├── entity_extractor.py # 实体提取器
├── fallback_embedding.py # 备用嵌入模型
└── __init__.py         # 模块初始化
```

## 🔧 核心组件

### MemoryCore (memory_core.py)
**功能**: 记忆系统的核心控制器
- 🗄️ **向量数据库管理**: 基于 ChromaDB 的高效存储
- 🔍 **语义搜索**: 使用嵌入向量进行相似度检索
- 💾 **对话记忆**: 自动存储和检索历史对话
- 👤 **实体跟踪**: 识别和记住重要实体信息
- 📊 **统计分析**: 提供记忆使用统计和分析

**主要方法**:
```python
# 存储对话记忆
await memory_core.store_conversation(user_input, ai_response)

# 检索相关记忆
memories = await memory_core.retrieve_relevant_memories(query, limit=5)

# 获取实体信息
entities = memory_core.get_entities()

# 获取最近对话
recent = memory_core.get_recent_conversations(limit=10)
```

### MemoryManager (memory_manager.py)
**功能**: 记忆管理的高级接口
- 🔄 **自动备份**: 定期备份记忆数据
- 🧹 **数据清理**: 清理过期和无用数据
- 📈 **性能优化**: 优化查询性能和存储效率
- 🔒 **数据安全**: 确保记忆数据的完整性

### DataModels (data_models.py)
**功能**: 定义记忆系统的数据结构
- 📝 **ConversationMemory**: 对话记忆数据模型
- 👤 **EntityMemory**: 实体记忆数据模型
- 🏷️ **MemoryMetadata**: 记忆元数据模型
- 📊 **MemoryStats**: 记忆统计数据模型

### EntityExtractor (entity_extractor.py)
**功能**: 从对话中提取重要实体
- 🏷️ **命名实体识别**: 识别人名、地名、组织等
- 🔗 **实体关系**: 建立实体间的关联关系
- 📊 **实体统计**: 跟踪实体出现频率和重要性
- 🎯 **上下文理解**: 基于上下文理解实体含义

### FallbackEmbedding (fallback_embedding.py)
**功能**: 提供备用嵌入模型支持
- 🔄 **模型切换**: 在主模型不可用时自动切换
- 📦 **离线支持**: 支持离线嵌入模型
- ⚡ **性能优化**: 优化嵌入计算性能
- 🛡️ **错误恢复**: 处理嵌入计算错误

## 🚀 使用指南

### 1. 初始化记忆系统
```python
from src.memory_core import MemoryCore

# 创建记忆核心
memory_core = MemoryCore(
    db_path="./memory_db",
    collection_name="vtuber_memories"
)

# 初始化（异步）
await memory_core.initialize()
```

### 2. 存储对话记忆
```python
# 存储单次对话
await memory_core.store_conversation(
    user_input="你好，我是小明",
    ai_response="你好小明！很高兴认识你。",
    metadata={"emotion": "happy", "topic": "greeting"}
)

# 批量存储
conversations = [
    ("今天天气怎么样？", "今天天气很好，阳光明媚。"),
    ("推荐一部电影", "我推荐《千与千寻》，这是一部很棒的动画电影。")
]
await memory_core.store_conversations_batch(conversations)
```

### 3. 检索相关记忆
```python
# 基于查询检索
memories = await memory_core.retrieve_relevant_memories(
    query="小明喜欢什么电影",
    limit=5,
    threshold=0.7
)

# 基于时间范围检索
from datetime import datetime, timedelta
recent_memories = await memory_core.retrieve_memories_by_time(
    start_time=datetime.now() - timedelta(days=7),
    end_time=datetime.now()
)
```

### 4. 实体管理
```python
# 获取所有实体
entities = memory_core.get_entities()

# 获取特定实体信息
entity_info = memory_core.get_entity_info("小明")

# 更新实体信息
memory_core.update_entity("小明", {
    "preferences": ["动画电影", "日本文化"],
    "personality": "友好、好奇"
})
```

## 📊 数据模型

### ConversationMemory
```python
@dataclass
class ConversationMemory:
    id: str                    # 唯一标识符
    user_input: str           # 用户输入
    ai_response: str          # AI 响应
    timestamp: datetime       # 时间戳
    embedding: List[float]    # 嵌入向量
    metadata: Dict[str, Any]  # 元数据
    entities: List[str]       # 提取的实体
    emotion: str              # 情感标签
    topic: str                # 话题分类
```

### EntityMemory
```python
@dataclass
class EntityMemory:
    name: str                 # 实体名称
    type: str                # 实体类型
    attributes: Dict[str, Any] # 实体属性
    relationships: List[str]   # 关联实体
    frequency: int            # 出现频率
    last_mentioned: datetime  # 最后提及时间
    importance: float         # 重要性评分
```

## ⚙️ 配置选项

### 基础配置
```json
{
  "memory": {
    "db_path": "./memory_db",
    "collection_name": "vtuber_memories",
    "embedding_model": "all-MiniLM-L6-v2",
    "max_memories": 10000,
    "cleanup_interval": 86400,
    "backup_interval": 3600
  }
}
```

### 高级配置
```json
{
  "memory_advanced": {
    "similarity_threshold": 0.7,
    "entity_extraction_enabled": true,
    "auto_cleanup_enabled": true,
    "compression_enabled": true,
    "encryption_enabled": false
  }
}
```

## 🔍 性能优化

### 1. 嵌入模型优化
- 使用轻量级模型 `all-MiniLM-L6-v2`
- 支持 GPU 加速计算
- 实现嵌入缓存机制

### 2. 数据库优化
- 定期清理过期数据
- 使用索引加速查询
- 实现数据压缩存储

### 3. 内存管理
- 延迟加载嵌入模型
- 实现 LRU 缓存策略
- 定期释放未使用资源

## 🛠️ 维护工具

### 数据备份
```python
# 创建备份
backup_path = memory_core.create_backup()

# 恢复备份
memory_core.restore_backup(backup_path)
```

### 数据清理
```python
# 清理过期数据
cleaned_count = memory_core.cleanup_expired_memories(days=30)

# 压缩数据库
memory_core.compress_database()
```

### 统计分析
```python
# 获取统计信息
stats = memory_core.get_memory_stats()
print(f"总记忆数: {stats.total_memories}")
print(f"实体数: {stats.total_entities}")
print(f"数据库大小: {stats.database_size}")
```

## 🚨 故障排除

### 常见问题
1. **嵌入模型加载失败**
   - 检查网络连接
   - 使用备用模型
   - 查看错误日志

2. **数据库连接错误**
   - 检查数据库路径权限
   - 重新初始化数据库
   - 恢复备份数据

3. **内存使用过高**
   - 清理过期数据
   - 调整缓存大小
   - 重启记忆系统

### 调试模式
```python
# 启用调试日志
import logging
logging.getLogger('memory_core').setLevel(logging.DEBUG)

# 检查系统状态
health_status = memory_core.check_health()
```

## 📚 相关文档
- [系统架构文档](../README.md)
- [配置指南](../../docs/setup_guide.md)
- [API 参考](./api_reference.md)