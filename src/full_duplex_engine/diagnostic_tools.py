"""
Diagnostic and Troubleshooting Tools for Full-Duplex Conversational Engine

Provides comprehensive diagnostic capabilities, user-friendly error messages,
and automated troubleshooting guidance for audio processing issues.
"""

import os
import sys
import time
import platform
import subprocess
import threading
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import logging
import json

from .logging_config import get_component_logger
from .error_handler import get_error_handler
from .system_health_monitor import get_system_health_monitor

logger = get_component_logger("diagnostic_tools")

@dataclass
class DiagnosticResult:
    """Result of a diagnostic check."""
    name: str
    status: str  # pass, warning, fail, unknown
    message: str
    details: Dict = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    severity: str = "info"  # info, warning, error, critical

@dataclass
class SystemDiagnostics:
    """Complete system diagnostic results."""
    timestamp: float
    overall_status: str
    results: List[DiagnosticResult]
    system_info: Dict
    recommendations: List[str]
    troubleshooting_steps: List[str]

class FullDuplexDiagnosticTools:
    """
    Comprehensive diagnostic and troubleshooting tools.
    
    Provides automated diagnostics, user-friendly error reporting,
    and guided troubleshooting for the full-duplex engine.
    """
    
    def __init__(self):
        """Initialize diagnostic tools."""
        self.error_handler = get_error_handler()
        self.health_monitor = get_system_health_monitor()
        
        # Diagnostic test registry
        self.diagnostic_tests = {}
        self._register_default_tests()
        
        # Troubleshooting knowledge base
        self.troubleshooting_kb = {}
        self._initialize_troubleshooting_kb()
        
        logger.info("FullDuplexDiagnosticTools initialized")
    
    def _register_default_tests(self):
        """Register default diagnostic tests."""
        self.diagnostic_tests = {
            'system_info': self._test_system_info,
            'audio_devices': self._test_audio_devices,
            'python_environment': self._test_python_environment,
            'dependencies': self._test_dependencies,
            'model_availability': self._test_model_availability,
            'audio_permissions': self._test_audio_permissions,
            'hardware_compatibility': self._test_hardware_compatibility,
            'performance_baseline': self._test_performance_baseline,
            'memory_usage': self._test_memory_usage,
            'disk_space': self._test_disk_space,
            'network_connectivity': self._test_network_connectivity
        }
    
    def _initialize_troubleshooting_kb(self):
        """Initialize troubleshooting knowledge base."""
        self.troubleshooting_kb = {
            'audio_device_not_found': {
                'description': 'No suitable audio input device detected',
                'causes': [
                    'Microphone not connected or disabled',
                    'Audio drivers not installed or outdated',
                    'Audio device permissions not granted',
                    'Audio device in use by another application'
                ],
                'solutions': [
                    'Check microphone connection and ensure it is enabled',
                    'Update audio drivers through Device Manager',
                    'Grant microphone permissions to the application',
                    'Close other applications that might be using the microphone',
                    'Try a different audio input device',
                    'Restart the audio service: services.msc -> Windows Audio'
                ]
            },
            'model_loading_failed': {
                'description': 'AI models (VAD/ASR) failed to load',
                'causes': [
                    'Insufficient memory for model loading',
                    'Model files corrupted or missing',
                    'Network connectivity issues during download',
                    'Incompatible model version',
                    'Insufficient disk space'
                ],
                'solutions': [
                    'Restart the application to retry model loading',
                    'Clear model cache: delete assets/models/ folder',
                    'Check available memory and close other applications',
                    'Verify internet connection for model downloads',
                    'Free up disk space (at least 2GB recommended)',
                    'Try running as administrator for file permissions'
                ]
            },
            'high_latency': {
                'description': 'Audio processing latency is too high',
                'causes': [
                    'High system CPU usage',
                    'Insufficient memory',
                    'Audio buffer size too large',
                    'Background applications consuming resources',
                    'Audio driver issues'
                ],
                'solutions': [
                    'Close unnecessary applications to free up CPU',
                    'Reduce audio buffer size in configuration',
                    'Update audio drivers',
                    'Disable audio enhancements in Windows sound settings',
                    'Use a dedicated audio interface if available',
                    'Consider upgrading hardware for better performance'
                ]
            },
            'frequent_interruptions': {
                'description': 'Unexpected interruptions or false speech detection',
                'causes': [
                    'Background noise triggering VAD',
                    'Audio feedback from speakers',
                    'VAD sensitivity too high',
                    'Microphone picking up system audio'
                ],
                'solutions': [
                    'Use headphones instead of speakers to prevent feedback',
                    'Reduce microphone sensitivity or gain',
                    'Move to a quieter environment',
                    'Adjust VAD threshold in configuration',
                    'Use noise cancellation if available',
                    'Check for audio driver echo cancellation settings'
                ]
            },
            'poor_transcription_quality': {
                'description': 'Speech recognition accuracy is poor',
                'causes': [
                    'Poor audio quality or low volume',
                    'Background noise interference',
                    'Microphone too far from speaker',
                    'ASR model not optimized for accent/language',
                    'Audio compression or processing artifacts'
                ],
                'solutions': [
                    'Move microphone closer to mouth (6-12 inches)',
                    'Increase microphone volume in system settings',
                    'Use a higher quality microphone',
                    'Reduce background noise',
                    'Speak clearly and at moderate pace',
                    'Check microphone frequency response (prefer flat response)'
                ]
            }
        }
    
    def run_full_diagnostics(self) -> SystemDiagnostics:
        """
        Run complete system diagnostics.
        
        Returns:
            SystemDiagnostics with comprehensive results
        """
        logger.info("Starting full system diagnostics...")
        start_time = time.time()
        
        results = []
        overall_status = "pass"
        
        # Run all diagnostic tests
        for test_name, test_func in self.diagnostic_tests.items():
            try:
                logger.debug(f"Running diagnostic test: {test_name}")
                result = test_func()
                results.append(result)
                
                # Update overall status
                if result.status == "fail":
                    overall_status = "fail"
                elif result.status == "warning" and overall_status == "pass":
                    overall_status = "warning"
                    
            except Exception as e:
                logger.error(f"Diagnostic test {test_name} failed: {e}")
                results.append(DiagnosticResult(
                    name=test_name,
                    status="fail",
                    message=f"Test execution failed: {str(e)}",
                    severity="error"
                ))
                overall_status = "fail"
        
        # Collect system information
        system_info = self._collect_system_info()
        
        # Generate recommendations and troubleshooting steps
        recommendations = self._generate_recommendations(results)
        troubleshooting_steps = self._generate_troubleshooting_steps(results)
        
        diagnostics = SystemDiagnostics(
            timestamp=time.time(),
            overall_status=overall_status,
            results=results,
            system_info=system_info,
            recommendations=recommendations,
            troubleshooting_steps=troubleshooting_steps
        )
        
        duration = time.time() - start_time
        logger.info(f"Full diagnostics completed in {duration:.1f}s - Status: {overall_status}")
        
        return diagnostics
    
    def _test_system_info(self) -> DiagnosticResult:
        """Test system information and compatibility."""
        try:
            system_info = {
                'platform': platform.system(),
                'platform_version': platform.version(),
                'architecture': platform.architecture()[0],
                'processor': platform.processor(),
                'python_version': sys.version,
                'cpu_count': os.cpu_count()
            }
            
            # Check for known compatibility issues
            warnings = []
            if system_info['platform'] != 'Windows':
                warnings.append(f"Platform {system_info['platform']} may have limited audio support")
            
            if system_info['cpu_count'] < 4:
                warnings.append(f"Low CPU count ({system_info['cpu_count']}) may affect real-time performance")
            
            status = "warning" if warnings else "pass"
            message = "System information collected successfully"
            if warnings:
                message += f" - {len(warnings)} compatibility warnings"
            
            return DiagnosticResult(
                name="system_info",
                status=status,
                message=message,
                details=system_info,
                recommendations=warnings
            )
            
        except Exception as e:
            return DiagnosticResult(
                name="system_info",
                status="fail",
                message=f"Failed to collect system information: {str(e)}",
                severity="error"
            )
    
    def _test_audio_devices(self) -> DiagnosticResult:
        """Test audio device availability and configuration."""
        try:
            import sounddevice as sd
            
            # Get available devices
            devices = sd.query_devices()
            input_devices = [d for d in devices if d['max_input_channels'] > 0]
            output_devices = [d for d in devices if d['max_output_channels'] > 0]
            
            details = {
                'total_devices': len(devices),
                'input_devices': len(input_devices),
                'output_devices': len(output_devices),
                'default_input': sd.query_devices(kind='input'),
                'default_output': sd.query_devices(kind='output')
            }
            
            # Check for issues
            issues = []
            if len(input_devices) == 0:
                issues.append("No audio input devices found")
            if len(output_devices) == 0:
                issues.append("No audio output devices found")
            
            # Test default input device
            try:
                default_input = sd.query_devices(kind='input')
                if default_input['max_input_channels'] == 0:
                    issues.append("Default input device has no input channels")
            except Exception as e:
                issues.append(f"Cannot access default input device: {str(e)}")
            
            status = "fail" if issues else "pass"
            message = f"Found {len(input_devices)} input and {len(output_devices)} output devices"
            if issues:
                message += f" - {len(issues)} issues detected"
            
            return DiagnosticResult(
                name="audio_devices",
                status=status,
                message=message,
                details=details,
                recommendations=issues,
                severity="critical" if "No audio input devices" in str(issues) else "warning"
            )
            
        except ImportError:
            return DiagnosticResult(
                name="audio_devices",
                status="fail",
                message="sounddevice library not available",
                recommendations=["Install sounddevice: pip install sounddevice"],
                severity="critical"
            )
        except Exception as e:
            return DiagnosticResult(
                name="audio_devices",
                status="fail",
                message=f"Audio device test failed: {str(e)}",
                severity="error"
            )
    
    def _test_python_environment(self) -> DiagnosticResult:
        """Test Python environment and version compatibility."""
        try:
            python_version = sys.version_info
            details = {
                'version': f"{python_version.major}.{python_version.minor}.{python_version.micro}",
                'implementation': platform.python_implementation(),
                'executable': sys.executable
            }
            
            issues = []
            recommendations = []
            
            # Check Python version
            if python_version < (3, 8):
                issues.append(f"Python {details['version']} is too old (minimum 3.8 required)")
                recommendations.append("Upgrade to Python 3.8 or newer")
            elif python_version >= (3, 12):
                issues.append(f"Python {details['version']} may have compatibility issues")
                recommendations.append("Consider using Python 3.9-3.11 for best compatibility")
            
            # Check implementation
            if details['implementation'] != 'CPython':
                issues.append(f"Python implementation {details['implementation']} may not be fully supported")
                recommendations.append("Use CPython for best compatibility")
            
            status = "fail" if any("too old" in issue for issue in issues) else ("warning" if issues else "pass")
            message = f"Python {details['version']} ({details['implementation']})"
            if issues:
                message += f" - {len(issues)} compatibility issues"
            
            return DiagnosticResult(
                name="python_environment",
                status=status,
                message=message,
                details=details,
                recommendations=recommendations,
                severity="critical" if status == "fail" else "warning"
            )
            
        except Exception as e:
            return DiagnosticResult(
                name="python_environment",
                status="fail",
                message=f"Python environment test failed: {str(e)}",
                severity="error"
            )
    
    def _test_dependencies(self) -> DiagnosticResult:
        """Test required dependencies availability."""
        required_packages = {
            'torch': 'PyTorch for VAD model',
            'numpy': 'NumPy for audio processing',
            'sounddevice': 'Audio device interface',
            'funasr': 'FunASR for speech recognition',
            'pyaudio': 'Audio capture (alternative)',
        }
        
        optional_packages = {
            'hypothesis': 'Property-based testing',
            'psutil': 'System monitoring'
        }
        
        details = {'installed': {}, 'missing': [], 'versions': {}}
        missing_required = []
        missing_optional = []
        
        # Check required packages
        for package, description in required_packages.items():
            try:
                module = __import__(package)
                details['installed'][package] = True
                # Try to get version
                if hasattr(module, '__version__'):
                    details['versions'][package] = module.__version__
                elif hasattr(module, 'version'):
                    details['versions'][package] = module.version
            except ImportError:
                details['installed'][package] = False
                details['missing'].append(package)
                missing_required.append(f"{package}: {description}")
        
        # Check optional packages
        for package, description in optional_packages.items():
            try:
                module = __import__(package)
                details['installed'][package] = True
                if hasattr(module, '__version__'):
                    details['versions'][package] = module.__version__
            except ImportError:
                details['installed'][package] = False
                missing_optional.append(f"{package}: {description}")
        
        # Determine status
        if missing_required:
            status = "fail"
            message = f"{len(missing_required)} required dependencies missing"
            severity = "critical"
        elif missing_optional:
            status = "warning"
            message = f"All required dependencies available, {len(missing_optional)} optional missing"
            severity = "info"
        else:
            status = "pass"
            message = "All dependencies available"
            severity = "info"
        
        recommendations = []
        if missing_required:
            recommendations.extend([f"Install required: {pkg}" for pkg in missing_required])
        if missing_optional:
            recommendations.extend([f"Consider installing: {pkg}" for pkg in missing_optional])
        
        return DiagnosticResult(
            name="dependencies",
            status=status,
            message=message,
            details=details,
            recommendations=recommendations,
            severity=severity
        )
    
    def _test_model_availability(self) -> DiagnosticResult:
        """Test AI model availability and loading."""
        model_dir = "assets/models"
        details = {
            'model_directory_exists': os.path.exists(model_dir),
            'models_found': [],
            'disk_usage': {}
        }
        
        issues = []
        recommendations = []
        
        # Check model directory
        if not details['model_directory_exists']:
            issues.append("Model directory does not exist")
            recommendations.append("Create assets/models directory")
        else:
            # Check for model files
            try:
                for item in os.listdir(model_dir):
                    item_path = os.path.join(model_dir, item)
                    if os.path.isdir(item_path):
                        details['models_found'].append(item)
                        # Get directory size
                        try:
                            size = sum(
                                os.path.getsize(os.path.join(dirpath, filename))
                                for dirpath, dirnames, filenames in os.walk(item_path)
                                for filename in filenames
                            )
                            details['disk_usage'][item] = f"{size / (1024*1024):.1f} MB"
                        except:
                            details['disk_usage'][item] = "unknown"
            except Exception as e:
                issues.append(f"Cannot access model directory: {str(e)}")
        
        # Check for expected models
        expected_models = ['silero_vad', 'paraformer']
        missing_models = [model for model in expected_models if model not in str(details['models_found'])]
        
        if missing_models:
            issues.extend([f"Missing model: {model}" for model in missing_models])
            recommendations.append("Models will be downloaded on first use")
        
        # Test model loading (basic check)
        try:
            import torch
            # Try to load a simple model to test torch functionality
            torch.jit.script(torch.nn.Linear(1, 1))
            details['torch_jit_available'] = True
        except Exception as e:
            details['torch_jit_available'] = False
            issues.append(f"PyTorch JIT not working: {str(e)}")
            recommendations.append("Reinstall PyTorch")
        
        status = "fail" if not details.get('torch_jit_available', True) else ("warning" if issues else "pass")
        message = f"Found {len(details['models_found'])} cached models"
        if issues:
            message += f" - {len(issues)} issues"
        
        return DiagnosticResult(
            name="model_availability",
            status=status,
            message=message,
            details=details,
            recommendations=recommendations,
            severity="error" if status == "fail" else "info"
        )
    
    def _test_audio_permissions(self) -> DiagnosticResult:
        """Test audio device permissions."""
        try:
            import sounddevice as sd
            
            # Try to query devices (requires basic permissions)
            devices = sd.query_devices()
            details = {'device_query_success': True, 'device_count': len(devices)}
            
            # Try to get default input device info
            try:
                default_input = sd.query_devices(kind='input')
                details['default_input_accessible'] = True
                details['default_input_name'] = default_input['name']
            except Exception as e:
                details['default_input_accessible'] = False
                details['default_input_error'] = str(e)
            
            # Try a very brief recording test (if possible)
            recording_test_success = False
            try:
                # Very short test recording (100ms)
                test_data = sd.rec(int(0.1 * 16000), samplerate=16000, channels=1, dtype='int16')
                sd.wait()  # Wait for recording to complete
                recording_test_success = True
                details['recording_test_success'] = True
            except Exception as e:
                details['recording_test_success'] = False
                details['recording_test_error'] = str(e)
            
            issues = []
            recommendations = []
            
            if not details.get('default_input_accessible', False):
                issues.append("Cannot access default input device")
                recommendations.append("Check audio device permissions in system settings")
            
            if not recording_test_success:
                issues.append("Cannot record audio")
                recommendations.append("Grant microphone permissions to the application")
                recommendations.append("Check if microphone is being used by another application")
            
            status = "fail" if issues else "pass"
            message = "Audio permissions test completed"
            if issues:
                message += f" - {len(issues)} permission issues"
            
            return DiagnosticResult(
                name="audio_permissions",
                status=status,
                message=message,
                details=details,
                recommendations=recommendations,
                severity="critical" if not recording_test_success else "warning"
            )
            
        except ImportError:
            return DiagnosticResult(
                name="audio_permissions",
                status="fail",
                message="Cannot test audio permissions - sounddevice not available",
                severity="error"
            )
        except Exception as e:
            return DiagnosticResult(
                name="audio_permissions",
                status="fail",
                message=f"Audio permissions test failed: {str(e)}",
                severity="error"
            )
    
    def _test_hardware_compatibility(self) -> DiagnosticResult:
        """Test hardware compatibility for full-duplex operation."""
        details = {}
        issues = []
        recommendations = []
        
        try:
            # Test CPU capabilities
            cpu_count = os.cpu_count()
            details['cpu_count'] = cpu_count
            
            if cpu_count < 4:
                issues.append(f"Low CPU count ({cpu_count}) may affect real-time performance")
                recommendations.append("Consider upgrading to a system with 4+ CPU cores")
            
            # Test memory availability
            try:
                import psutil
                memory = psutil.virtual_memory()
                details['total_memory_gb'] = round(memory.total / (1024**3), 1)
                details['available_memory_gb'] = round(memory.available / (1024**3), 1)
                details['memory_usage_percent'] = memory.percent
                
                if memory.available < 2 * (1024**3):  # Less than 2GB available
                    issues.append(f"Low available memory ({details['available_memory_gb']}GB)")
                    recommendations.append("Close other applications to free memory")
                
                if memory.percent > 85:
                    issues.append(f"High memory usage ({memory.percent}%)")
                    recommendations.append("System memory usage is high")
                    
            except ImportError:
                details['memory_info'] = "psutil not available"
            
            # Test audio hardware specific checks
            try:
                import sounddevice as sd
                
                # Check for ASIO drivers (Windows)
                if platform.system() == "Windows":
                    devices = sd.query_devices()
                    asio_devices = [d for d in devices if 'ASIO' in str(d.get('name', ''))]
                    details['asio_devices_available'] = len(asio_devices)
                    
                    if len(asio_devices) > 0:
                        recommendations.append("ASIO audio devices detected - may provide better performance")
                
                # Check sample rate support
                try:
                    default_device = sd.query_devices(kind='input')
                    supported_rates = []
                    test_rates = [16000, 44100, 48000]
                    
                    for rate in test_rates:
                        try:
                            sd.check_input_settings(device=default_device['index'], 
                                                  samplerate=rate, channels=1)
                            supported_rates.append(rate)
                        except:
                            pass
                    
                    details['supported_sample_rates'] = supported_rates
                    
                    if 16000 not in supported_rates:
                        issues.append("16kHz sample rate not supported by default device")
                        recommendations.append("Use a different audio device that supports 16kHz")
                        
                except Exception as e:
                    details['sample_rate_test_error'] = str(e)
                    
            except ImportError:
                pass
            
            status = "fail" if any("not supported" in issue for issue in issues) else ("warning" if issues else "pass")
            message = f"Hardware compatibility check completed"
            if issues:
                message += f" - {len(issues)} compatibility issues"
            
            return DiagnosticResult(
                name="hardware_compatibility",
                status=status,
                message=message,
                details=details,
                recommendations=recommendations,
                severity="error" if status == "fail" else "warning"
            )
            
        except Exception as e:
            return DiagnosticResult(
                name="hardware_compatibility",
                status="fail",
                message=f"Hardware compatibility test failed: {str(e)}",
                severity="error"
            )
    
    def _test_performance_baseline(self) -> DiagnosticResult:
        """Test basic performance baseline."""
        details = {}
        issues = []
        recommendations = []
        
        try:
            # Test CPU performance with a simple benchmark
            import time
            start_time = time.time()
            
            # Simple CPU benchmark
            result = sum(i * i for i in range(100000))
            cpu_time = time.time() - start_time
            details['cpu_benchmark_time'] = f"{cpu_time*1000:.1f}ms"
            
            if cpu_time > 0.1:  # More than 100ms for simple calculation
                issues.append(f"Slow CPU performance ({cpu_time*1000:.1f}ms for benchmark)")
                recommendations.append("System may be under high load")
            
            # Test memory allocation performance
            start_time = time.time()
            test_array = [0] * 1000000  # Allocate 1M integers
            memory_time = time.time() - start_time
            details['memory_allocation_time'] = f"{memory_time*1000:.1f}ms"
            del test_array
            
            if memory_time > 0.05:  # More than 50ms for memory allocation
                issues.append(f"Slow memory allocation ({memory_time*1000:.1f}ms)")
                recommendations.append("System memory may be fragmented or under pressure")
            
            # Test disk I/O if possible
            try:
                test_file = "temp_perf_test.tmp"
                start_time = time.time()
                with open(test_file, 'w') as f:
                    f.write("test" * 10000)
                with open(test_file, 'r') as f:
                    content = f.read()
                os.remove(test_file)
                io_time = time.time() - start_time
                details['disk_io_time'] = f"{io_time*1000:.1f}ms"
                
                if io_time > 0.1:  # More than 100ms for simple I/O
                    issues.append(f"Slow disk I/O ({io_time*1000:.1f}ms)")
                    recommendations.append("Consider using SSD for better performance")
                    
            except Exception as e:
                details['disk_io_error'] = str(e)
            
            status = "warning" if issues else "pass"
            message = f"Performance baseline established"
            if issues:
                message += f" - {len(issues)} performance concerns"
            
            return DiagnosticResult(
                name="performance_baseline",
                status=status,
                message=message,
                details=details,
                recommendations=recommendations,
                severity="warning" if issues else "info"
            )
            
        except Exception as e:
            return DiagnosticResult(
                name="performance_baseline",
                status="fail",
                message=f"Performance baseline test failed: {str(e)}",
                severity="error"
            )
    
    def _test_memory_usage(self) -> DiagnosticResult:
        """Test current memory usage and availability."""
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            process = psutil.Process()
            
            details = {
                'total_system_memory_gb': round(memory.total / (1024**3), 1),
                'available_memory_gb': round(memory.available / (1024**3), 1),
                'system_memory_usage_percent': memory.percent,
                'process_memory_mb': round(process.memory_info().rss / (1024**2), 1),
                'process_memory_percent': round(process.memory_percent(), 1)
            }
            
            issues = []
            recommendations = []
            
            # Check system memory
            if memory.percent > 90:
                issues.append(f"Critical system memory usage ({memory.percent}%)")
                recommendations.append("Close applications to free memory immediately")
            elif memory.percent > 80:
                issues.append(f"High system memory usage ({memory.percent}%)")
                recommendations.append("Consider closing some applications")
            
            # Check available memory for models
            if memory.available < 1 * (1024**3):  # Less than 1GB
                issues.append(f"Low available memory ({details['available_memory_gb']}GB)")
                recommendations.append("AI models may fail to load - need at least 1GB free")
            
            # Check process memory usage
            if process.memory_percent() > 10:
                issues.append(f"High process memory usage ({details['process_memory_percent']}%)")
                recommendations.append("Application is using significant memory")
            
            status = "fail" if memory.percent > 95 else ("warning" if issues else "pass")
            message = f"Memory usage: {memory.percent}% system, {details['process_memory_mb']}MB process"
            
            return DiagnosticResult(
                name="memory_usage",
                status=status,
                message=message,
                details=details,
                recommendations=recommendations,
                severity="critical" if status == "fail" else ("warning" if issues else "info")
            )
            
        except ImportError:
            return DiagnosticResult(
                name="memory_usage",
                status="warning",
                message="Cannot check memory usage - psutil not available",
                recommendations=["Install psutil for memory monitoring: pip install psutil"],
                severity="info"
            )
        except Exception as e:
            return DiagnosticResult(
                name="memory_usage",
                status="fail",
                message=f"Memory usage test failed: {str(e)}",
                severity="error"
            )
    
    def _test_disk_space(self) -> DiagnosticResult:
        """Test available disk space."""
        try:
            import shutil
            
            # Check current directory space
            total, used, free = shutil.disk_usage(".")
            
            details = {
                'total_space_gb': round(total / (1024**3), 1),
                'used_space_gb': round(used / (1024**3), 1),
                'free_space_gb': round(free / (1024**3), 1),
                'usage_percent': round((used / total) * 100, 1)
            }
            
            issues = []
            recommendations = []
            
            # Check free space
            if free < 0.5 * (1024**3):  # Less than 500MB
                issues.append(f"Critical disk space ({details['free_space_gb']}GB free)")
                recommendations.append("Free up disk space immediately")
            elif free < 2 * (1024**3):  # Less than 2GB
                issues.append(f"Low disk space ({details['free_space_gb']}GB free)")
                recommendations.append("Consider freeing up disk space for model downloads")
            
            # Check model directory space if it exists
            model_dir = "assets/models"
            if os.path.exists(model_dir):
                try:
                    model_size = sum(
                        os.path.getsize(os.path.join(dirpath, filename))
                        for dirpath, dirnames, filenames in os.walk(model_dir)
                        for filename in filenames
                    )
                    details['model_cache_size_mb'] = round(model_size / (1024**2), 1)
                except:
                    details['model_cache_size_mb'] = "unknown"
            
            status = "fail" if free < 0.5 * (1024**3) else ("warning" if issues else "pass")
            message = f"Disk space: {details['free_space_gb']}GB free ({details['usage_percent']}% used)"
            
            return DiagnosticResult(
                name="disk_space",
                status=status,
                message=message,
                details=details,
                recommendations=recommendations,
                severity="critical" if status == "fail" else ("warning" if issues else "info")
            )
            
        except Exception as e:
            return DiagnosticResult(
                name="disk_space",
                status="fail",
                message=f"Disk space test failed: {str(e)}",
                severity="error"
            )
    
    def _test_network_connectivity(self) -> DiagnosticResult:
        """Test network connectivity for model downloads."""
        details = {}
        issues = []
        recommendations = []
        
        try:
            import urllib.request
            import socket
            
            # Test basic internet connectivity
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=5)
                details['internet_connectivity'] = True
            except:
                details['internet_connectivity'] = False
                issues.append("No internet connectivity detected")
                recommendations.append("Check internet connection for model downloads")
            
            # Test specific model repositories if internet is available
            if details['internet_connectivity']:
                test_urls = [
                    ("GitHub", "https://github.com"),
                    ("HuggingFace", "https://huggingface.co"),
                    ("ModelScope", "https://modelscope.cn")
                ]
                
                for name, url in test_urls:
                    try:
                        response = urllib.request.urlopen(url, timeout=10)
                        details[f'{name.lower()}_accessible'] = response.getcode() == 200
                    except:
                        details[f'{name.lower()}_accessible'] = False
                        issues.append(f"Cannot access {name}")
                        recommendations.append(f"Check firewall settings for {name} access")
            
            status = "fail" if not details.get('internet_connectivity', False) else ("warning" if issues else "pass")
            message = "Network connectivity test completed"
            if issues:
                message += f" - {len(issues)} connectivity issues"
            
            return DiagnosticResult(
                name="network_connectivity",
                status=status,
                message=message,
                details=details,
                recommendations=recommendations,
                severity="warning" if not details.get('internet_connectivity', False) else "info"
            )
            
        except Exception as e:
            return DiagnosticResult(
                name="network_connectivity",
                status="fail",
                message=f"Network connectivity test failed: {str(e)}",
                severity="error"
            )
    
    def _collect_system_info(self) -> Dict:
        """Collect comprehensive system information."""
        info = {
            'timestamp': time.time(),
            'platform': {
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'architecture': platform.architecture()
            },
            'python': {
                'version': sys.version,
                'executable': sys.executable,
                'implementation': platform.python_implementation()
            },
            'environment': {
                'cwd': os.getcwd(),
                'path': os.environ.get('PATH', ''),
                'pythonpath': os.environ.get('PYTHONPATH', '')
            }
        }
        
        # Add memory info if available
        try:
            import psutil
            memory = psutil.virtual_memory()
            info['memory'] = {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent
            }
            
            # Add CPU info
            info['cpu'] = {
                'count': psutil.cpu_count(),
                'count_logical': psutil.cpu_count(logical=True),
                'freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
            }
        except ImportError:
            pass
        
        return info
    
    def _generate_recommendations(self, results: List[DiagnosticResult]) -> List[str]:
        """Generate system-wide recommendations based on diagnostic results."""
        recommendations = []
        
        # Collect all recommendations from individual tests
        all_recs = []
        for result in results:
            all_recs.extend(result.recommendations)
        
        # Add high-priority recommendations
        critical_failures = [r for r in results if r.status == "fail" and r.severity == "critical"]
        if critical_failures:
            recommendations.append("CRITICAL: Address critical failures before using full-duplex mode")
        
        # Check for common patterns
        audio_issues = [r for r in results if "audio" in r.name and r.status in ["fail", "warning"]]
        if len(audio_issues) > 1:
            recommendations.append("Multiple audio issues detected - check audio system configuration")
        
        model_issues = [r for r in results if "model" in r.name and r.status in ["fail", "warning"]]
        if model_issues:
            recommendations.append("Model loading issues detected - ensure stable internet connection")
        
        performance_issues = [r for r in results if "performance" in r.name or "memory" in r.name]
        if len(performance_issues) > 1:
            recommendations.append("Performance issues detected - consider system optimization")
        
        return recommendations
    
    def _generate_troubleshooting_steps(self, results: List[DiagnosticResult]) -> List[str]:
        """Generate troubleshooting steps based on diagnostic results."""
        steps = []
        
        # Prioritize steps based on severity and type
        critical_results = [r for r in results if r.status == "fail" and r.severity == "critical"]
        
        if critical_results:
            steps.append("1. Address critical issues first:")
            for result in critical_results:
                steps.append(f"   - {result.name}: {result.message}")
                for rec in result.recommendations[:2]:  # Top 2 recommendations
                    steps.append(f"     → {rec}")
        
        # Add general troubleshooting steps
        audio_failures = [r for r in results if "audio" in r.name and r.status == "fail"]
        if audio_failures:
            steps.extend([
                "2. Audio System Troubleshooting:",
                "   - Restart audio services (Windows: services.msc → Windows Audio)",
                "   - Check Device Manager for audio driver issues",
                "   - Test with different audio devices",
                "   - Run Windows audio troubleshooter"
            ])
        
        model_failures = [r for r in results if "model" in r.name and r.status == "fail"]
        if model_failures:
            steps.extend([
                "3. Model Loading Troubleshooting:",
                "   - Clear model cache: delete assets/models/ folder",
                "   - Check internet connection",
                "   - Try running as administrator",
                "   - Verify sufficient disk space (2GB+)"
            ])
        
        return steps
    
    def generate_user_friendly_report(self, diagnostics: SystemDiagnostics) -> str:
        """Generate user-friendly diagnostic report."""
        report = []
        
        # Header
        report.append("=" * 60)
        report.append("Full-Duplex Engine Diagnostic Report")
        report.append("=" * 60)
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(diagnostics.timestamp))}")
        report.append(f"Overall Status: {diagnostics.overall_status.upper()}")
        report.append("")
        
        # Summary
        passed = len([r for r in diagnostics.results if r.status == "pass"])
        warnings = len([r for r in diagnostics.results if r.status == "warning"])
        failed = len([r for r in diagnostics.results if r.status == "fail"])
        
        report.append("SUMMARY:")
        report.append(f"  ✓ Passed: {passed}")
        report.append(f"  ⚠ Warnings: {warnings}")
        report.append(f"  ✗ Failed: {failed}")
        report.append("")
        
        # Critical issues first
        critical_issues = [r for r in diagnostics.results if r.status == "fail" and r.severity == "critical"]
        if critical_issues:
            report.append("CRITICAL ISSUES (Must Fix):")
            for result in critical_issues:
                report.append(f"  ✗ {result.name}: {result.message}")
                for rec in result.recommendations:
                    report.append(f"    → {rec}")
            report.append("")
        
        # Warnings
        warning_issues = [r for r in diagnostics.results if r.status == "warning"]
        if warning_issues:
            report.append("WARNINGS (Recommended to Fix):")
            for result in warning_issues:
                report.append(f"  ⚠ {result.name}: {result.message}")
                for rec in result.recommendations[:2]:  # Top 2 recommendations
                    report.append(f"    → {rec}")
            report.append("")
        
        # System recommendations
        if diagnostics.recommendations:
            report.append("SYSTEM RECOMMENDATIONS:")
            for i, rec in enumerate(diagnostics.recommendations, 1):
                report.append(f"  {i}. {rec}")
            report.append("")
        
        # Troubleshooting steps
        if diagnostics.troubleshooting_steps:
            report.append("TROUBLESHOOTING STEPS:")
            for step in diagnostics.troubleshooting_steps:
                report.append(f"  {step}")
            report.append("")
        
        # System info summary
        sys_info = diagnostics.system_info
        report.append("SYSTEM INFORMATION:")
        report.append(f"  Platform: {sys_info.get('platform', {}).get('system', 'Unknown')}")
        report.append(f"  Python: {sys_info.get('python', {}).get('version', 'Unknown').split()[0]}")
        if 'memory' in sys_info:
            memory_gb = round(sys_info['memory']['total'] / (1024**3), 1)
            memory_pct = sys_info['memory']['percent']
            report.append(f"  Memory: {memory_gb}GB total ({memory_pct}% used)")
        report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def save_diagnostic_report(self, diagnostics: SystemDiagnostics, filename: str = None) -> str:
        """Save diagnostic report to file."""
        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(diagnostics.timestamp))
            filename = f"diagnostic_report_{timestamp}.txt"
        
        report_text = self.generate_user_friendly_report(diagnostics)
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report_text)
                f.write("\n\nDETAILED RESULTS:\n")
                f.write("=" * 40 + "\n")
                
                # Add detailed results
                for result in diagnostics.results:
                    f.write(f"\n{result.name.upper()}:\n")
                    f.write(f"  Status: {result.status}\n")
                    f.write(f"  Message: {result.message}\n")
                    f.write(f"  Severity: {result.severity}\n")
                    
                    if result.details:
                        f.write("  Details:\n")
                        for key, value in result.details.items():
                            f.write(f"    {key}: {value}\n")
                    
                    if result.recommendations:
                        f.write("  Recommendations:\n")
                        for rec in result.recommendations:
                            f.write(f"    - {rec}\n")
            
            logger.info(f"Diagnostic report saved to: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Failed to save diagnostic report: {e}")
            return ""

# Global diagnostic tools instance
_diagnostic_tools: Optional[FullDuplexDiagnosticTools] = None

def get_diagnostic_tools() -> FullDuplexDiagnosticTools:
    """Get global diagnostic tools instance."""
    global _diagnostic_tools
    if _diagnostic_tools is None:
        _diagnostic_tools = FullDuplexDiagnosticTools()
    return _diagnostic_tools