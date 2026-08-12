"""
System Health Check Module

Provides comprehensive health checking for all agent components:
- Ollama server connectivity
- Vision model availability
- Screen capture functionality
- Action engine status
- Resource usage
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import time


class HealthChecker:
    """Comprehensive system health checker"""
    
    def __init__(self, agent_manager):
        """
        Initialize health checker
        
        Args:
            agent_manager: AgentManager instance to check
        """
        self.agent_manager = agent_manager
        self.logger = logging.getLogger(__name__)
        
        # Health check results cache
        self.last_check_time: Optional[datetime] = None
        self.last_check_results: Dict[str, Any] = {}
        self.check_interval = 60.0  # Check every 60 seconds
    
    async def full_health_check(self, force: bool = False) -> Dict[str, Any]:
        """
        Perform full system health check
        
        Args:
            force: Force check even if recently checked
            
        Returns:
            Dictionary with health status for all components
        """
        # Check if we need to run (avoid too frequent checks)
        if not force and self.last_check_time:
            time_since_check = (datetime.now() - self.last_check_time).total_seconds()
            if time_since_check < self.check_interval:
                self.logger.debug(f"Using cached health check results ({time_since_check:.1f}s ago)")
                return self.last_check_results
        
        self.logger.info("Starting full system health check...")
        start_time = time.time()
        
        health = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'unknown',
            'components': {},
            'warnings': [],
            'errors': [],
            'check_duration': 0.0
        }
        
        # Check each component
        health['components']['ollama_server'] = await self._check_ollama_server()
        health['components']['vision_model'] = await self._check_vision_model()
        health['components']['screen_capture'] = await self._check_screen_capture()
        health['components']['action_engine'] = await self._check_action_engine()
        health['components']['resource_usage'] = await self._check_resource_usage()
        
        # Determine overall status
        all_ok = all(
            comp.get('status') == 'ok' 
            for comp in health['components'].values()
        )
        
        has_warnings = any(
            comp.get('status') == 'warning' 
            for comp in health['components'].values()
        )
        
        has_errors = any(
            comp.get('status') == 'error' 
            for comp in health['components'].values()
        )
        
        if has_errors:
            health['overall_status'] = 'error'
        elif has_warnings:
            health['overall_status'] = 'warning'
        elif all_ok:
            health['overall_status'] = 'ok'
        
        # Collect warnings and errors
        for comp_name, comp_data in health['components'].items():
            if comp_data.get('status') == 'warning' and comp_data.get('message'):
                health['warnings'].append(f"{comp_name}: {comp_data['message']}")
            if comp_data.get('status') == 'error' and comp_data.get('message'):
                health['errors'].append(f"{comp_name}: {comp_data['message']}")
        
        # Record check duration
        health['check_duration'] = time.time() - start_time
        
        # Cache results
        self.last_check_time = datetime.now()
        self.last_check_results = health
        
        self.logger.info(f"Health check completed in {health['check_duration']:.2f}s - Status: {health['overall_status']}")
        
        return health
    
    async def _check_ollama_server(self) -> Dict[str, Any]:
        """Check Ollama server connectivity"""
        try:
            response = await asyncio.to_thread(
                self.agent_manager.vision_client.ollama_client.list
            )
            
            models = response.get('models', [])
            
            return {
                'status': 'ok',
                'message': f'Ollama server running with {len(models)} models',
                'details': {
                    'model_count': len(models),
                    'models': [m['name'] for m in models]
                }
            }
            
        except ConnectionError as e:
            return {
                'status': 'error',
                'message': 'Cannot connect to Ollama server',
                'details': {'error': str(e)},
                'suggestion': 'Start Ollama server with: ollama serve'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Ollama check failed: {str(e)}',
                'details': {'error': str(e)}
            }
    
    async def _check_vision_model(self) -> Dict[str, Any]:
        """Check vision model availability"""
        try:
            # Get model name
            model_name = self.agent_manager.vision_client.model_name
            
            # List available models
            response = await asyncio.to_thread(
                self.agent_manager.vision_client.ollama_client.list
            )
            
            available_models = [m['name'] for m in response.get('models', [])]
            
            # Check if model is available
            if model_name in available_models:
                return {
                    'status': 'ok',
                    'message': f"Model '{model_name}' is available",
                    'details': {
                        'active_model': model_name,
                        'available_models': available_models
                    }
                }
            else:
                return {
                    'status': 'error',
                    'message': f"Model '{model_name}' not found",
                    'details': {
                        'requested_model': model_name,
                        'available_models': available_models
                    },
                    'suggestion': f'Install model with: ollama pull {model_name}'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Vision model check failed: {str(e)}',
                'details': {'error': str(e)}
            }
    
    async def _check_screen_capture(self) -> Dict[str, Any]:
        """Check screen capture functionality"""
        try:
            # Try to capture a screenshot
            start_time = time.time()
            image_b64 = await self.agent_manager.vision_client.capture_screen()
            capture_time = time.time() - start_time
            
            if len(image_b64) > 0:
                return {
                    'status': 'ok',
                    'message': 'Screen capture working',
                    'details': {
                        'capture_time': f'{capture_time:.3f}s',
                        'image_size': f'{len(image_b64)} bytes'
                    }
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Screen capture returned empty image',
                    'details': {}
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Screen capture failed: {str(e)}',
                'details': {'error': str(e)}
            }
    
    async def _check_action_engine(self) -> Dict[str, Any]:
        """Check action engine status"""
        try:
            action_engine = self.agent_manager.action_engine
            
            # Check safety lock status
            safety_active = action_engine.is_safety_active()
            
            # Get action history
            history = action_engine.get_action_history()
            
            if safety_active:
                return {
                    'status': 'warning',
                    'message': 'Safety lock is active - actions disabled',
                    'details': {
                        'safety_active': True,
                        'action_history_size': len(history)
                    },
                    'suggestion': 'Reset safety lock if this is unintended'
                }
            else:
                return {
                    'status': 'ok',
                    'message': 'Action engine ready',
                    'details': {
                        'safety_active': False,
                        'action_history_size': len(history),
                        'use_directinput': action_engine.use_directinput
                    }
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Action engine check failed: {str(e)}',
                'details': {'error': str(e)}
            }
    
    async def _check_resource_usage(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            resource_monitor = self.agent_manager.resource_monitor
            
            # Get current metrics
            metrics = resource_monitor.get_performance_summary()
            
            cpu_percent = metrics.get('current_cpu_percent', 0)
            memory_percent = metrics.get('current_memory_percent', 0)
            
            # Determine status based on thresholds
            if cpu_percent > 80 or memory_percent > 80:
                status = 'warning'
                message = 'High resource usage detected'
            elif cpu_percent > 90 or memory_percent > 90:
                status = 'error'
                message = 'Critical resource usage'
            else:
                status = 'ok'
                message = 'Resource usage normal'
            
            return {
                'status': status,
                'message': message,
                'details': {
                    'cpu_percent': f'{cpu_percent:.1f}%',
                    'memory_percent': f'{memory_percent:.1f}%',
                    'monitoring_active': resource_monitor.monitoring_active
                }
            }
            
        except Exception as e:
            return {
                'status': 'warning',
                'message': f'Resource check failed: {str(e)}',
                'details': {'error': str(e)}
            }
    
    def get_health_summary(self) -> str:
        """
        Get human-readable health summary
        
        Returns:
            Formatted health summary string
        """
        if not self.last_check_results:
            return "No health check performed yet"
        
        health = self.last_check_results
        
        summary = f"System Health: {health['overall_status'].upper()}\n"
        summary += f"Last checked: {health['timestamp']}\n\n"
        
        # Component status
        summary += "Components:\n"
        for comp_name, comp_data in health['components'].items():
            status_icon = {
                'ok': '✓',
                'warning': '⚠',
                'error': '✗',
                'unknown': '?'
            }.get(comp_data.get('status'), '?')
            
            summary += f"  {status_icon} {comp_name}: {comp_data.get('message', 'Unknown')}\n"
        
        # Warnings
        if health['warnings']:
            summary += f"\nWarnings ({len(health['warnings'])}):\n"
            for warning in health['warnings']:
                summary += f"  ⚠ {warning}\n"
        
        # Errors
        if health['errors']:
            summary += f"\nErrors ({len(health['errors'])}):\n"
            for error in health['errors']:
                summary += f"  ✗ {error}\n"
        
        return summary
    
    async def wait_for_healthy(self, timeout: float = 30.0, check_interval: float = 2.0) -> bool:
        """
        Wait for system to become healthy
        
        Args:
            timeout: Maximum time to wait (seconds)
            check_interval: Time between checks (seconds)
            
        Returns:
            True if system became healthy, False if timeout
        """
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            health = await self.full_health_check(force=True)
            
            if health['overall_status'] == 'ok':
                self.logger.info("System is healthy")
                return True
            
            self.logger.info(f"System not healthy yet, waiting... ({health['overall_status']})")
            await asyncio.sleep(check_interval)
        
        self.logger.warning(f"System did not become healthy within {timeout}s")
        return False
