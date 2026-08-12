# AIex 遗留 Python 退役清单

## 原则

删除依据是功能覆盖和验证证据，不是文件年龄或命名。用户数据、模型、令牌、参考音频和配置迁移前始终保留。源代码批量删除前还必须恢复有效 Git 元数据，或由用户明确接受无版本快照删除。

当前遗留范围：`src/` 79 个文件、`tests/` 41 个文件、`tools/` 9 个文件、`config_examples/` 4 个文件，另有根入口 `main.py`、`requirements.txt` 和旧 `config.json`。

## 已完成清理

- `logs/`、`.pytest_cache/`、全部 `__pycache__/` 和 `*.pyc` 已删除并验证不存在。
- 旧报告中的产品意图已压缩到 `CORE_TECHNICAL_BASELINE.md`。
- 10 份 `memory_db/backups/*.json.gz` 已只读核验：声明记录数和实际记录数均为 0，空集完整性哈希一致；`chroma.sqlite3` 仍保留，待 SQLite 级最终核验。

## 退役批次

| 批次 | 遗留范围 | Rust 替代 | 当前结论 | 删除门禁 |
| --- | --- | --- | --- | --- |
| A | 9 份根目录历史报告、`.hypothesis/` | 核心基线与本清单 | 可删除，等待明确授权 | 用户确认精确清单 |
| B | `config.py`、`conversation.py`、`domain.py`、`error_handler.py`、`text_cleaner.py`、`stream_processor.py` | config/domain/core/text/migrate | 配置迁移正常/拒绝覆盖路径已验证 | 有效 Git + 用户复核迁移结果 |
| C | `llm_client.py`、`llm/ollama.py`、`llm/koboldcpp.py`、`vts_client.py` | ollama/koboldcpp/vts | 两种 LLM 与 VTS 的 Rust 边界已覆盖 | 外部服务契约测试 |
| D | `tts_pipeline.py`、`tts_player.py`、`full_duplex_engine/` | audio/tts/duplex/asr/capture | 默认逻辑覆盖 | native playback/capture 编译与设备实测 |
| E | `memory_core/` | memory | 基础检索/持久化覆盖 | ChromaDB/多模态数据导入或明确放弃旧数据 |
| F | `gui_controller.py`、`subtitle_window.py`、主题和提示组件 | control/ui-model/desktop | 模型已验证，桌面壳未编译 | eframe 编译、截图和关键交互验收 |
| G | `vision_client.py`、`screen_capturer.py`、`action_engine.py`、`agent_manager.py`、`safety_manager.py` | vision/safety/automation/audit | 安全核心覆盖，平台动作未实现 | Windows 捕获/输入适配器、急停实测、审计验收 |
| H | `*_optimized.py`、`*_monitor.py`、预加载/热重载/自然行为等旁支 | 可观察性与后续明确功能 | 不在 Rust 主链 | 逐项确认无独有产品能力后删除 |
| I | 对应 Python 测试、诊断工具、`requirements.txt`、`main.py` | Rust 测试、服务、桌面端 | 最后处理 | 所有前置批次完成，发布包可启动 |

## 批次 A 精确目标

- `.hypothesis/`
- `BUG_FIX_REPORT.md`
- `COMPLETION_SUMMARY.md`
- `FINAL_REPORT.md`
- `IMPROVEMENT_REPORT.md`
- `INTEGRATION_GUIDE.md`
- `NATURAL_BEHAVIOR_REPORT.md`
- `ULTRA_OPTIMIZATION_REPORT.md`
- `V44_SUPER_OPTIMIZATION_REPORT.md`
- `V44_TEST_REPORT.md`

删除命令尚未执行；安全审查已确认这些文件仍全部存在。

## 完成定义

只有当以下条件同时满足，才可宣布 Python 主链退役：

1. 默认与原生 feature 构建、测试、Clippy 和 Allman 风格门禁通过。
2. Ollama、VTS、TTS、ASR、麦克风、播放设备和视觉服务完成实机健康与关键路径验收。
3. 桌面端完成启动、连接、流式对话、打断、急停、断线恢复和退出验收。
4. 旧记忆与配置完成迁移或形成用户确认的弃用决定。
5. Windows 自动化只能经 permit 和持久审计执行，急停能撤销进行中许可。
6. 所有删除目标在执行前重新列出绝对路径并确认位于工作区内。
