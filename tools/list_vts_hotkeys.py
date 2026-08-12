#!/usr/bin/env python3
"""
VTube Studio Hotkey Discovery Tool

This script connects to VTube Studio and retrieves all available hotkeys
for the currently loaded model. This information is essential for setting up
emotion-to-hotkey mappings in the AI VTuber system configuration.

Usage:
    python tools/list_vts_hotkeys.py [--host HOST] [--port PORT] [--format FORMAT]

Requirements:
    - VTube Studio must be running
    - VTube Studio API must be enabled
    - Current model must be loaded in VTube Studio
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vts_client import VTSClient


class HotkeyDiscoveryTool:
    """Tool for discovering and displaying VTube Studio hotkeys"""
    
    def __init__(self, host: str = "localhost", port: int = 8001):
        """
        Initialize the hotkey discovery tool
        
        Args:
            host: VTube Studio WebSocket host
            port: VTube Studio WebSocket port
        """
        self.host = host
        self.port = port
        self.vts_client = VTSClient(host=host, port=port)
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the tool"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        # Create console handler if not already exists
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(levelname)s: %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    async def discover_hotkeys(self) -> Optional[List[Dict]]:
        """
        Connect to VTube Studio and retrieve available hotkeys
        
        Returns:
            List of hotkey dictionaries or None if failed
        """
        try:
            self.logger.info(f"Connecting to VTube Studio at {self.host}:{self.port}...")
            
            # Connect to VTube Studio
            if not await self.vts_client.connect():
                self.logger.error("Failed to connect to VTube Studio")
                self.logger.error("Please ensure:")
                self.logger.error("  1. VTube Studio is running")
                self.logger.error("  2. API access is enabled in VTube Studio settings")
                self.logger.error("  3. The correct host and port are specified")
                return None
            
            self.logger.info("Connected successfully!")
            
            # Authenticate with VTube Studio
            self.logger.info("Authenticating with VTube Studio...")
            if not await self.vts_client.authenticate():
                self.logger.error("Failed to authenticate with VTube Studio")
                self.logger.error("Please accept the authentication request in VTube Studio")
                return None
            
            self.logger.info("Authentication successful!")
            
            # Get available hotkeys
            self.logger.info("Retrieving available hotkeys...")
            hotkeys = await self.vts_client.get_available_hotkeys()
            
            if not hotkeys:
                self.logger.warning("No hotkeys found")
                self.logger.warning("Please ensure:")
                self.logger.warning("  1. A model is currently loaded in VTube Studio")
                self.logger.warning("  2. The model has hotkeys configured")
                return []
            
            self.logger.info(f"Found {len(hotkeys)} available hotkeys")
            return hotkeys
            
        except Exception as e:
            self.logger.error(f"Unexpected error during hotkey discovery: {e}")
            return None
        finally:
            # Clean up connection
            await self.vts_client.disconnect()
    
    def format_hotkeys_table(self, hotkeys: List[Dict]) -> str:
        """
        Format hotkeys as a readable table
        
        Args:
            hotkeys: List of hotkey dictionaries
            
        Returns:
            Formatted table string
        """
        if not hotkeys:
            return "No hotkeys available"
        
        # Calculate column widths
        max_id_width = max(len(hotkey.get("hotkeyID", "")) for hotkey in hotkeys)
        max_name_width = max(len(hotkey.get("name", "")) for hotkey in hotkeys)
        max_type_width = max(len(hotkey.get("type", "")) for hotkey in hotkeys)
        
        # Ensure minimum widths
        id_width = max(max_id_width, len("Hotkey ID"))
        name_width = max(max_name_width, len("Name"))
        type_width = max(max_type_width, len("Type"))
        
        # Create table header
        header = f"{'Hotkey ID':<{id_width}} | {'Name':<{name_width}} | {'Type':<{type_width}}"
        separator = "-" * len(header)
        
        # Create table rows
        rows = []
        for hotkey in hotkeys:
            hotkey_id = hotkey.get("hotkeyID", "")
            name = hotkey.get("name", "")
            hotkey_type = hotkey.get("type", "")
            
            row = f"{hotkey_id:<{id_width}} | {name:<{name_width}} | {hotkey_type:<{type_width}}"
            rows.append(row)
        
        return "\n".join([header, separator] + rows)
    
    def format_hotkeys_json(self, hotkeys: List[Dict]) -> str:
        """
        Format hotkeys as JSON
        
        Args:
            hotkeys: List of hotkey dictionaries
            
        Returns:
            JSON formatted string
        """
        return json.dumps(hotkeys, indent=2, ensure_ascii=False)
    
    def format_hotkeys_config(self, hotkeys: List[Dict]) -> str:
        """
        Format hotkeys as configuration template
        
        Args:
            hotkeys: List of hotkey dictionaries
            
        Returns:
            Configuration template string
        """
        if not hotkeys:
            return "No hotkeys available for configuration"
        
        config_template = {
            "emotion_hotkey_map": {
                "neutral": "",
                "happy": "",
                "angry": "",
                "sad": "",
                "surprised": ""
            }
        }
        
        # Add comments with available hotkeys
        lines = [
            "// Emotion to Hotkey Mapping Configuration Template",
            "// Available hotkeys from your current VTube Studio model:",
            "//"
        ]
        
        for hotkey in hotkeys:
            hotkey_id = hotkey.get("hotkeyID", "")
            name = hotkey.get("name", "")
            lines.append(f"//   {hotkey_id} - {name}")
        
        lines.extend([
            "//",
            "// Copy the desired hotkey IDs into the emotion_hotkey_map below:",
            json.dumps(config_template, indent=2, ensure_ascii=False)
        ])
        
        return "\n".join(lines)
    
    def display_usage_instructions(self) -> None:
        """Display usage instructions for the discovered hotkeys"""
        instructions = """
USAGE INSTRUCTIONS:

1. Copy the desired hotkey IDs from the table above
2. Add them to your AI VTuber system configuration file (config.json)
3. Map emotions to hotkeys in the emotion_hotkey_map section:

   "emotion_hotkey_map": {
     "neutral": "your_neutral_hotkey_id",
     "happy": "your_happy_hotkey_id",
     "angry": "your_angry_hotkey_id",
     "sad": "your_sad_hotkey_id",
     "surprised": "your_surprised_hotkey_id"
   }

4. Enable expression control in your configuration:
   "enable_expression_control": true

5. Restart the AI VTuber system to apply the new configuration

NOTES:
- Leave hotkey IDs empty ("") for emotions you don't want to map
- Hotkey IDs are case-sensitive and must match exactly
- Test your configuration using the validation tool:
  python tools/validate_config.py
"""
        print(instructions)


async def main():
    """Main function for the hotkey discovery tool"""
    parser = argparse.ArgumentParser(
        description="Discover and list VTube Studio hotkeys for AI VTuber configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/list_vts_hotkeys.py
  python tools/list_vts_hotkeys.py --host 192.168.1.100 --port 8001
  python tools/list_vts_hotkeys.py --format json
  python tools/list_vts_hotkeys.py --format config > my_hotkeys.json
        """
    )
    
    parser.add_argument(
        "--host",
        default="localhost",
        help="VTube Studio WebSocket host (default: localhost)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="VTube Studio WebSocket port (default: 8001)"
    )
    
    parser.add_argument(
        "--format",
        choices=["table", "json", "config"],
        default="table",
        help="Output format (default: table)"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress informational messages (only show results)"
    )
    
    args = parser.parse_args()
    
    # Create discovery tool
    tool = HotkeyDiscoveryTool(host=args.host, port=args.port)
    
    # Suppress logging if quiet mode
    if args.quiet:
        tool.logger.setLevel(logging.ERROR)
    
    # Discover hotkeys
    hotkeys = await tool.discover_hotkeys()
    
    if hotkeys is None:
        print("Failed to discover hotkeys. Check the error messages above.", file=sys.stderr)
        sys.exit(1)
    
    # Format and display results
    if args.format == "table":
        print("\nAVAILABLE HOTKEYS:")
        print("=" * 50)
        print(tool.format_hotkeys_table(hotkeys))
        
        if not args.quiet:
            tool.display_usage_instructions()
    
    elif args.format == "json":
        print(tool.format_hotkeys_json(hotkeys))
    
    elif args.format == "config":
        print(tool.format_hotkeys_config(hotkeys))
    
    if not args.quiet and hotkeys:
        print(f"\nDiscovered {len(hotkeys)} hotkeys successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)