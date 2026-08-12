"""
System Health Monitor for Full-Duplex Conversational Engine

Provides comprehensive system health monitoring by aggregating health information
from all components and providing system-wide health assessment.
"""

import time
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
import logging

from .logging_config import get_component_logger
from .error_handler import get_error_handler
from .performance_monitor import PerformanceMonitor

logger = get_component_logger("system_health_monitor")

@dataclass
class ComponentHealth:
    """Health information for a single component."""
    name: str
    status: str  # excellent, good, fair, poor, critical
    health_score: int  # 0-100
    errors_recent: int
    performance_metrics: Dict
    recommendations: List[str]
    last_updated: float

@dataclass
class SystemHealth:
    """Overall system health assessment."""
    overall_status: str
    overall_score: int
    component_health: Dict[str, ComponentHealth]
    system_recommendations: List[str]
    critical_issues: List[str]
    timestamp: float

class SystemHealthMonitor:
    """
    Comprehensive system health monitor for the full-duplex engine.
    
    Monitors health across all components and provides system-wide health assessment.
    """
    
    def __init__(self, monitoring_interval: float = 30.0):
        """
        Initialize system health monitor.
        
        Args:
            monitoring_interval: Health check interval in seconds
        """
        self.monitoring_interval = monitoring_interval
        
        # Component references
        self.components = {}
        self.component_health = {}
        
        # Health monitoring state
        self.monitoring_active = False
        self.monitoring_thread = None
        
        # Health history
        self.health_history = []
        self.max_history_size = 100
        
        # Health callbacks
        self.health_callbacks: List[Callable[[SystemHealth], None]] = []
        self.alert_callbacks: List[Callable[[str, str], None]] = []
        
        # Error handler integration
        self.error_handler = get_error_handler()
        
        # Threading
        self.lock = threading.Lock()
        
        logger.info(f"SystemHealthMonitor initialized (interval={monitoring_interval}s)")
    
    def register_component(self, name: str, component: any):
        """
        Register a component for health monitoring.
        
        Args:
            name: Component name
            component: Component instance
        """
        with self.lock:
            self.components[name] = component
            self.component_health[name] = ComponentHealth(
                name=name,
                status="unknown",
                health_score=0,
                errors_recent=0,
                performance_metrics={},
                recommendations=[],
                last_updated=0.0
            )
        
        logger.info(f"Registered component for health monitoring: {name}")
    
    def start_monitoring(self):
        """Start continuous health monitoring."""
        if self.monitoring_active:
            logger.warning("Health monitoring already active")
            return
        
        self.monitoring_active = True
        
        # Start monitoring thread
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            name="system_health_monitor",
            daemon=True
        )
        self.monitoring_thread.start()
        
        logger.info("Started system health monitoring")
    
    def stop_monitoring(self):
        """Stop continuous health monitoring."""
        if not self.monitoring_active:
            return
        
        self.monitoring_active = False
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5.0)
        
        logger.info("Stopped system health monitoring")
    
    def _monitoring_loop(self):
        """Main health monitoring loop."""
        logger.debug("Health monitoring loop started")
        
        while self.monitoring_active:
            try:
                # Perform health check
                system_health = self.check_system_health()
                
                # Store in history
                with self.lock:
                    self.health_history.append(system_health)
                    if len(self.health_history) > self.max_history_size:
                        self.health_history.pop(0)
                
                # Check for alerts
                self._check_for_alerts(system_health)
                
                # Notify callbacks
                for callback in self.health_callbacks:
                    try:
                        callback(system_health)
                    except Exception as e:
                        logger.error(f"Error in health callback: {e}")
                
                # Wait for next check
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                time.sleep(self.monitoring_interval)
        
        logger.debug("Health monitoring loop ended")
    
    def check_system_health(self) -> SystemHealth:
        """
        Perform comprehensive system health check.
        
        Returns:
            SystemHealth with current system status
        """
        current_time = time.time()
        component_health = {}
        
        # Check health of each registered component
        for name, component in self.components.items():
            try:
                health = self._check_component_health(name, component)
                component_health[name] = health
                
                # Update stored component health
                with self.lock:
                    self.component_health[name] = health
                
            except Exception as e:
                logger.error(f"Error checking health of {name}: {e}")
                # Create error health record
                component_health[name] = ComponentHealth(
                    name=name,
                    status="critical",
                    health_score=0,
                    errors_recent=1,
                    performance_metrics={},
                    recommendations=[f"Health check failed: {str(e)}"],
                    last_updated=current_time
                )
        
        # Calculate overall system health
        overall_score, overall_status = self._calculate_overall_health(component_health)
        
        # Generate system-wide recommendations
        system_recommendations = self._generate_system_recommendations(component_health)
        
        # Identify critical issues
        critical_issues = self._identify_critical_issues(component_health)
        
        return SystemHealth(
            overall_status=overall_status,
            overall_score=overall_score,
            component_health=component_health,
            system_recommendations=system_recommendations,
            critical_issues=critical_issues,
            timestamp=current_time
        )
    
    def _check_component_health(self, name: str, component: any) -> ComponentHealth:
        """Check health of a specific component."""
        current_time = time.time()
        
        # Try to get health information from component
        health_info = {}
        if hasattr(component, 'get_system_health'):
            try:
                health_info = component.get_system_health()
            except Exception as e:
                logger.warning(f"Could not get health info from {name}: {e}")
        
        # Extract health metrics
        status = health_info.get('status', 'unknown')
        
        # Map status to score
        status_scores = {
            'excellent': 95,
            'good': 80,
            'fair': 60,
            'poor': 40,
            'warning': 30,
            'critical': 10,
            'unknown': 50
        }
        health_score = status_scores.get(status, 50)
        
        # Get error information
        errors_info = health_info.get('errors', {})
        errors_recent = errors_info.get('total_errors', 0)
        
        # Get performance metrics
        performance_metrics = health_info.get('performance', {})
        
        # Generate component-specific recommendations
        recommendations = []
        
        # Check for specific issues
        if status in ['critical', 'poor']:
            recommendations.append(f"Component {name} is in {status} state - immediate attention required")
        
        if errors_recent > 10:
            recommendations.append(f"High error count in {name}: {errors_recent} errors")
        
        # Check model availability
        models_loaded = health_info.get('models_loaded', {})
        if models_loaded:
            for model_name, loaded in models_loaded.items():
                if not loaded:
                    recommendations.append(f"{model_name.upper()} model not loaded in {name}")
        
        # Check fallback states
        fallbacks_active = health_info.get('fallbacks_active', {})
        if fallbacks_active:
            for fallback_name, active in fallbacks_active.items():
                if active:
                    recommendations.append(f"{fallback_name.upper()} fallback active in {name}")
        
        return ComponentHealth(
            name=name,
            status=status,
            health_score=health_score,
            errors_recent=errors_recent,
            performance_metrics=performance_metrics,
            recommendations=recommendations,
            last_updated=current_time
        )
    
    def _calculate_overall_health(self, component_health: Dict[str, ComponentHealth]) -> tuple:
        """Calculate overall system health score and status."""
        if not component_health:
            return 0, "unknown"
        
        # Calculate weighted average of component health scores
        total_score = 0
        total_weight = 0
        
        # Component weights (more critical components have higher weight)
        component_weights = {
            'streaming_ears': 3.0,  # Most critical for audio processing
            'duplex_manager': 2.5,  # Critical for interruption handling
            'audio_device_manager': 2.0,  # Important for hardware interface
            'text_processor': 1.5,  # Important for text processing
            'configuration_manager': 1.0  # Less critical
        }
        
        for name, health in component_health.items():
            weight = component_weights.get(name, 1.0)
            total_score += health.health_score * weight
            total_weight += weight
        
        overall_score = int(total_score / total_weight) if total_weight > 0 else 0
        
        # Determine overall status
        if overall_score >= 90:
            overall_status = "excellent"
        elif overall_score >= 75:
            overall_status = "good"
        elif overall_score >= 60:
            overall_status = "fair"
        elif overall_score >= 40:
            overall_status = "poor"
        else:
            overall_status = "critical"
        
        # Override status if any component is critical
        for health in component_health.values():
            if health.status == "critical":
                overall_status = "critical"
                overall_score = min(overall_score, 25)
                break
        
        return overall_score, overall_status
    
    def _generate_system_recommendations(self, component_health: Dict[str, ComponentHealth]) -> List[str]:
        """Generate system-wide recommendations."""
        recommendations = []
        
        # Collect all component recommendations
        all_component_recs = []
        for health in component_health.values():
            all_component_recs.extend(health.recommendations)
        
        # Add system-wide recommendations based on patterns
        critical_components = [
            name for name, health in component_health.items()
            if health.status == "critical"
        ]
        
        if critical_components:
            recommendations.append(
                f"Critical components detected: {', '.join(critical_components)}. "
                f"Consider restarting the full-duplex engine."
            )
        
        # Check for widespread errors
        total_errors = sum(health.errors_recent for health in component_health.values())
        if total_errors > 20:
            recommendations.append(
                f"High system-wide error count: {total_errors}. "
                f"Check system resources and configuration."
            )
        
        # Check for multiple fallbacks
        fallback_count = sum(
            1 for health in component_health.values()
            if any("fallback active" in rec for rec in health.recommendations)
        )
        
        if fallback_count > 1:
            recommendations.append(
                f"Multiple components using fallbacks ({fallback_count}). "
                f"Check model availability and system resources."
            )
        
        return recommendations
    
    def _identify_critical_issues(self, component_health: Dict[str, ComponentHealth]) -> List[str]:
        """Identify critical issues requiring immediate attention."""
        critical_issues = []
        
        for name, health in component_health.items():
            if health.status == "critical":
                critical_issues.append(f"{name}: {health.status}")
            
            # Check for specific critical conditions
            if health.errors_recent > 50:
                critical_issues.append(f"{name}: Excessive errors ({health.errors_recent})")
            
            if "model not loaded" in " ".join(health.recommendations).lower():
                critical_issues.append(f"{name}: Critical model unavailable")
        
        return critical_issues
    
    def _check_for_alerts(self, system_health: SystemHealth):
        """Check for conditions that require alerts."""
        # Alert on critical overall status
        if system_health.overall_status == "critical":
            self._send_alert("critical", "System health is critical")
        
        # Alert on critical issues
        for issue in system_health.critical_issues:
            self._send_alert("critical", f"Critical issue: {issue}")
        
        # Alert on poor performance
        if system_health.overall_score < 30:
            self._send_alert("warning", f"System performance poor (score: {system_health.overall_score})")
    
    def _send_alert(self, level: str, message: str):
        """Send alert to registered callbacks."""
        logger.warning(f"ALERT [{level.upper()}]: {message}")
        
        for callback in self.alert_callbacks:
            try:
                callback(level, message)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
    
    def add_health_callback(self, callback: Callable[[SystemHealth], None]):
        """Add callback for health updates."""
        self.health_callbacks.append(callback)
        logger.debug("Added health callback")
    
    def add_alert_callback(self, callback: Callable[[str, str], None]):
        """Add callback for alerts."""
        self.alert_callbacks.append(callback)
        logger.debug("Added alert callback")
    
    def get_health_summary(self) -> Dict:
        """Get comprehensive health summary."""
        current_health = self.check_system_health()
        
        # Get error handler statistics
        error_stats = self.error_handler.get_error_statistics()
        error_health = self.error_handler.get_system_health()
        
        return {
            'current_health': current_health,
            'error_statistics': error_stats,
            'error_health': error_health,
            'monitoring_active': self.monitoring_active,
            'components_monitored': list(self.components.keys()),
            'health_history_size': len(self.health_history)
        }
    
    def log_health_summary(self):
        """Log comprehensive health summary."""
        try:
            summary = self.get_health_summary()
            current_health = summary['current_health']
            
            logger.info("=== System Health Summary ===")
            logger.info(f"Overall Status: {current_health.overall_status.upper()}")
            logger.info(f"Overall Score: {current_health.overall_score}/100")
            logger.info(f"Monitoring Active: {summary['monitoring_active']}")
            
            # Component health
            logger.info("Component Health:")
            for name, health in current_health.component_health.items():
                logger.info(f"  {name}: {health.status} (score: {health.health_score})")
            
            # Critical issues
            if current_health.critical_issues:
                logger.info("Critical Issues:")
                for issue in current_health.critical_issues:
                    logger.info(f"  - {issue}")
            
            # System recommendations
            if current_health.system_recommendations:
                logger.info("System Recommendations:")
                for i, rec in enumerate(current_health.system_recommendations, 1):
                    logger.info(f"  {i}. {rec}")
            
            logger.info("============================")
            
        except Exception as e:
            logger.error(f"Failed to log health summary: {e}")

# Global system health monitor instance
_system_health_monitor: Optional[SystemHealthMonitor] = None

def get_system_health_monitor() -> SystemHealthMonitor:
    """Get global system health monitor instance."""
    global _system_health_monitor
    if _system_health_monitor is None:
        _system_health_monitor = SystemHealthMonitor()
    return _system_health_monitor

def cleanup_system_health_monitor():
    """Clean up global system health monitor."""
    global _system_health_monitor
    if _system_health_monitor is not None:
        _system_health_monitor.stop_monitoring()
        _system_health_monitor = None