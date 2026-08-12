# Audio Cache Directory

This directory contains pre-recorded audio files for common phrases.
When the TTS pipeline receives text that matches a cached phrase,
it will play the cached audio instantly without calling the TTS API.

## Benefits

- **Instant Response**: Cached phrases play immediately (<100ms)
- **Reduced API Calls**: Saves TTS API resources for common phrases
- **Consistent Quality**: Pre-recorded audio ensures consistent quality

## Default Cached Phrases

The following phrases are configured by default:

| Phrase | File Name | Description |
|--------|-----------|-------------|
| 嗯... | hmm.mp3 | Thinking sound |
| 让我想想 | thinking.mp3 | "Let me think" |
| 你好 | hello.mp3 | "Hello" greeting |
| 好的 | ok.mp3 | "OK" acknowledgment |
| 是的 | yes.mp3 | "Yes" confirmation |
| 嗯嗯 | hmm2.mp3 | Agreement sound |
| 哦 | oh.mp3 | "Oh" exclamation |
| 啊 | ah.mp3 | "Ah" exclamation |

## Adding Custom Cache Entries

1. Record or generate audio files for your phrases
2. Save them as MP3 files in this directory
3. Update the `DEFAULT_PHRASE_CACHE` in `src/tts_pipeline.py`

## File Format Requirements

- Format: MP3 (recommended) or WAV
- Sample Rate: 22050 Hz or higher
- Channels: Mono or Stereo
- Duration: Keep short (< 3 seconds) for natural conversation flow

## Usage Notes

- Exact text matching is used (case-sensitive)
- Missing cache files will fall back to TTS generation
- Cache is loaded at pipeline startup
