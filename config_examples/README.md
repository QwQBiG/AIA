# AI VTuber System Configuration Examples

This directory contains configuration examples and templates for different use cases of the AI VTuber Emotional Intelligence System.

## Configuration Files

### Basic Configurations
- `basic_config.json` - Minimal configuration for basic functionality
- `emotional_intelligence_config.json` - Full emotional intelligence features enabled
- `voice_cloning_only_config.json` - Voice cloning without expression control
- `expression_only_config.json` - Expression control without voice cloning

### Advanced Configurations
- `live2d_model_configs/` - Model-specific configurations for different Live2D models
- `performance_optimized_config.json` - Configuration optimized for performance
- `development_config.json` - Configuration for development and testing

## Quick Start

1. Copy one of the example configurations to your project root as `config.json`
2. Modify the settings according to your setup
3. Use the validation tool to check your configuration: `python tools/validate_config.py`

## Configuration Reference

### Core Settings

| Setting | Description | Default | Required |
|---------|-------------|---------|----------|
| `ollama_url` | Ollama service URL | `http://localhost:11434` | Yes |
| `ollama_model` | Model name to use | `llama3` | Yes |
| `tts_voice` | Edge-TTS voice name | `zh-CN-XiaoxiaoNeural` | Yes |
| `vts_port` | VTube Studio WebSocket port | `8001` | Yes |
| `log_level` | Logging level | `INFO` | Yes |

### Emotional Intelligence Settings

| Setting | Description | Default | Required |
|---------|-------------|---------|----------|
| `enable_emotional_intelligence` | Enable structured emotional responses | `false` | No |
| `enable_voice_cloning` | Enable GPT-SoVITS voice cloning | `false` | No |
| `enable_expression_control` | Enable Live2D expression control | `false` | No |

### GPT-SoVITS Settings

| Setting | Description | Default | Required |
|---------|-------------|---------|----------|
| `sovits_url` | GPT-SoVITS service URL | `http://127.0.0.1:9880` | No |
| `sovits_timeout` | Request timeout in seconds | `10.0` | No |
| `sovits_language` | Language code for synthesis | `zh` | No |
| `fallback_to_edge_tts` | Fallback to Edge-TTS on failure | `true` | No |

### Expression Control Settings

| Setting | Description | Default | Required |
|---------|-------------|---------|----------|
| `emotion_hotkey_map` | Emotion to hotkey mapping | See examples | No |
| `default_emotion` | Default emotion when parsing fails | `neutral` | No |
| `expression_timeout` | Expression trigger timeout | `0.5` | No |

## Emotion-Hotkey Mapping

The `emotion_hotkey_map` maps emotion tags to VTube Studio hotkeys:

```json
{
  "emotion_hotkey_map": {
    "neutral": "",
    "happy": "F1",
    "angry": "F2", 
    "sad": "F3",
    "surprised": "F4"
  }
}
```

### Supported Emotions
- `neutral` - Default/calm expression
- `happy` - Joy, excitement, positive emotions
- `angry` - Anger, frustration, annoyance
- `sad` - Sadness, disappointment, melancholy
- `surprised` - Surprise, shock, amazement

### Hotkey Format
- Use VTube Studio hotkey names (e.g., "F1", "F2", "Ctrl+A")
- Empty string `""` means no hotkey assigned
- Use `tools/list_vts_hotkeys.py` to discover available hotkeys

## Troubleshooting

If you encounter issues:

1. Validate your configuration: `python tools/validate_config.py config.json`
2. Check the setup guide: `docs/setup_guide.md`
3. Review the troubleshooting section in the setup guide