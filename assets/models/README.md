# Model Storage Directory

This directory contains cached models for the Full-Duplex Conversational Engine.

## Directory Structure

```
assets/models/
├── paraformer/          # FunASR Paraformer-streaming models
├── silero_vad/          # Silero VAD models
└── cache/               # Temporary model cache files
```

## Model Management

Models are automatically downloaded and cached when first used. The system will:

1. Check for local model existence before downloading
2. Use specific model versions to ensure stability
3. Implement fallback mechanisms for model unavailability

## Supported Models

### FunASR Paraformer-streaming
- **Model**: `paraformer-zh-streaming`
- **Version**: `v2.0.4` (pinned for stability)
- **Purpose**: Real-time speech recognition with streaming capabilities
- **Language**: Chinese (Mandarin)

### Silero VAD
- **Model**: `silero_vad`
- **Purpose**: Voice Activity Detection
- **Languages**: Multilingual support

## Storage Requirements

- Paraformer model: ~500MB
- Silero VAD model: ~50MB
- Total estimated: ~600MB

## Configuration

Model paths and versions are configured in the ConfigurationManager component.
See `src/full_duplex_engine/configuration_manager.py` for details.