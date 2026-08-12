# Game Profiles Directory

This directory contains game-specific profiles and templates for the Hybrid Vision-Reflex System.

## Directory Structure

Each game should have its own subdirectory with the following structure:

```
assets/games/
├── {game-name}/
│   ├── profile.json          # Game configuration and metadata
│   └── templates/            # Visual templates for template matching
│       ├── template1.png
│       ├── template2.png
│       └── ...
```

## Profile Format

Each game profile (`profile.json`) should contain:

```json
{
  "display_name": "Human-readable game name",
  "description": "Brief description of the game",
  "vlm_prompts": [
    "Custom prompt 1 for VLM",
    "Custom prompt 2 for VLM"
  ],
  "default_templates": {
    "template_name": "filename.png"
  },
  "action_cooldowns": {
    "action_name": 2.0
  }
}
```

## Template Requirements

- Format: PNG
- Dimensions: 20x20 to 200x200 pixels
- Grayscale or color (will be converted to grayscale for matching)
- Should be distinctive and easily recognizable

## Creating Templates

Use the Template Creator UI to interactively select and save templates from screenshots.

## Example Games

- `cookie-clicker/` - Incremental clicking game
- Add more games as needed
