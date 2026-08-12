#!/usr/bin/env python3
"""Check VTube Studio available parameters for mouth animation"""

import asyncio
import json
import sys
sys.path.insert(0, '.')

from src.vts_client import VTSClient

async def get_parameters():
    client = VTSClient(port=8001)
    
    connected = await client.connect()
    if not connected:
        print('Failed to connect to VTube Studio')
        return
    
    authenticated = await client.authenticate()
    if not authenticated:
        print('Failed to authenticate with VTube Studio')
        return
    
    # Get available parameters
    request = {
        'apiName': 'VTubeStudioPublicAPI',
        'apiVersion': '1.0',
        'requestID': 'get_params',
        'messageType': 'InputParameterListRequest',
        'data': {}
    }
    
    await client.websocket.send(json.dumps(request))
    response = await client.websocket.recv()
    data = json.loads(response)
    
    if data.get('messageType') == 'InputParameterListResponse':
        params = data.get('data', {}).get('defaultParameters', [])
        print(f'Found {len(params)} parameters')
        
        # Find mouth-related parameters
        mouth_params = [p for p in params if 'mouth' in p.get('name', '').lower() or 'lip' in p.get('name', '').lower()]
        print(f'\nMouth-related parameters ({len(mouth_params)}):')
        for p in mouth_params:
            print(f"  - {p.get('name')}: min={p.get('min')}, max={p.get('max')}, default={p.get('defaultValue')}")
        
        # Also check for voice-related parameters
        voice_params = [p for p in params if 'voice' in p.get('name', '').lower()]
        print(f'\nVoice-related parameters ({len(voice_params)}):')
        for p in voice_params:
            print(f"  - {p.get('name')}: min={p.get('min')}, max={p.get('max')}, default={p.get('defaultValue')}")
    
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(get_parameters())
