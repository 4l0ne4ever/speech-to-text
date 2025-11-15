"""
Alerting System for Streaming Metrics.

Monitors metrics and triggers alerts for:
- High error rates
- High latency
- Stuck sessions
- Cost overruns
"""

import logging
import time
import threading
from typing import Callable, List, Optional, Dict
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Alert notification."""
    severity: AlertSeverity
    alert_type: str
    message: str
    timestamp: float
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Export alert as dictionary."""
        return {
            "severity": self.severity.value,
            "alert_type": self.alert_type,
            "message": self.message,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "metric_value": self.metric_value,
            "threshold": self.threshold,
        }
    
    def __str__(self) -> str:
        """String representation."""
        return (
            f"[{self.severity.value.upper()}] {self.alert_type}: {self.message} "
            f"(value={self.metric_value}, threshold={self.threshold})"
        )


@dataclass
class AlertConfig:
    """Alert thresholds configuration."""
    # Latency thresholds (ms)
    latency_p95_warning: float = 800.0
    latency_p95_critical: float = 1500.0
    latency_p99_warning: float = 1200.0
    latency_p99_critical: float = 2000.0
    
    # Error rate thresholds (%)
    error_rate_warning: float = 5.0
    error_rate_critical: float = 10.0
    
    # Confidence thresholds
    confidence_avg_warning: float = 0.7
    confidence_avg_critical: float = 0.5
    
    # Session thresholds
    max_active_sessions: int = 100
    stuck_session_duration: float = 600.0  # 10 minutes
    
    # Cost thresholds (USD)
    cost_per_hour_warning: float = 50.0
    cost_per_hour_critical: float = 100.0
    
    # Check interval
    check_interval_seconds: float = 30.0


class AlertManager:
    """
    Manages alerts based on metrics thresholds.
    
    Monitors metrics and triggers alerts when thresholds exceeded.
    """
    
    def __init__(
        self,
        metrics_collector,
        config: Optional[AlertConfig] = None,
        alert_callback: Optional[Callable[[Alert], None]] = None
    ):
        """
        Initialize alert manager.
        
        Args:
            metrics_collector: MetricsCollector instance
            config: Alert configuration
            alert_callback: Optional callback for alerts
        """
        self.metrics_collector = metrics_collector
        self.config = config or AlertConfig()
        self.alert_callback = alert_callback
        
        # Alert history
        self.alerts: List[Alert] = []
        self.alert_counts: Dict[str, int] = {}
        
        # Monitor thread
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_monitor = threading.Event()
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        logger.info(
            f"AlertManager initialized: "
            f"check_interval={self.config.check_interval_seconds}s"
        )
    
    def start_monitoring(self):
        """Start background monitoring thread."""
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("Monitor thread already running")
            return
        
        self.stop_monitor.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info("Alert monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring thread."""
        if not self.monitor_thread:
            return
        
        self.stop_monitor.set()
        self.monitor_thread.join(timeout=5.0)
        
        logger.info("Alert monitoring stopped")
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        logger.info("Alert monitor loop started")
        
        while not self.stop_monitor.is_set():
            try:
                # Check all alert conditions
                self._check_latency()
                self._check_error_rate()
                self._check_confidence()
                self._check_sessions()
                self._check_cost()
                
                # Sleep before next check
                time.sleep(self.config.check_interval_seconds)
            
            except Exception as e:
                logger.error(f"Error in alert monitor loop: {e}", exc_info=True)
                time.sleep(10.0)
        
        logger.info("Alert monitor loop stopped")
    
    def _check_latency(self):
        """Check latency metrics."""
        summary = self.metrics_collector.get_summary()
        
        # Check p95 latency
        p95_final = summary['latency']['final_results']['p95']
        
        if p95_final >= self.config.latency_p95_critical:
            self._trigger_alert(
                severity=AlertSeverity.CRITICAL,
                alert_type="high_latency_p95",
                message=f"Final result latency p95 critically high: {p95_final:.1f}ms",
                metric_value=p95_final,
                threshold=self.config.latency_p95_critical
            )
        elif p95_final >= self.config.latency_p95_warning:
            self._trigger_alert(
                severity=AlertSeverity.WARNING,
                alert_type="high_latency_p95",
                message=f"Final result latency p95 elevated: {p95_final:.1f}ms",
                metric_value=p95_final,
                threshold=self.config.latency_p95_warning
            )
        
        # Check p99 latency
        p99_final = summary['latency']['final_results']['p99']
        
        if p99_final >= self.config.latency_p99_critical:
            self._trigger_alert(
                severity=AlertSeverity.CRITICAL,
                alert_type="high_latency_p99",
                message=f"Final result latency p99 critically high: {p99_final:.1f}ms",
                metric_value=p99_final,
                threshold=self.config.latency_p99_critical
            )
        elif p99_final >= self.config.latency_p99_warning:
            self._trigger_alert(
                severity=AlertSeverity.WARNING,
                alert_type="high_latency_p99",
                message=f"Final result latency p99 elevated: {p99_final:.1f}ms",
                metric_value=p99_final,
                threshold=self.config.latency_p99_warning
            )
    
    def _check_error_rate(self):
        """Check error rate."""
        summary = self.metrics_collector.get_summary()
        
        total_errors = summary['errors']['total']
        total_results = summary['throughput']['total_results']
        
        if total_results == 0:
            return
        
        error_rate = (total_errors / total_results) * 100.0
        
        if error_rate >= self.config.error_rate_critical:
            self._trigger_alert(
                severity=AlertSeverity.CRITICAL,
                alert_type="high_error_rate",
                message=f"Error rate critically high: {error_rate:.1f}%",
                metric_value=error_rate,
                threshold=self.config.error_rate_critical
            )
        elif error_rate >= self.config.error_rate_warning:
            self._trigger_alert(
                severity=AlertSeverity.WARNING,
                alert_type="high_error_rate",
                message=f"Error rate elevated: {error_rate:.1f}%",
                metric_value=error_rate,
                threshold=self.config.error_rate_warning
            )
    
    def _check_confidence(self):
        """Check confidence scores."""
        summary = self.metrics_collector.get_summary()
        
        avg_confidence = summary['confidence']['avg']
        
        if avg_confidence == 0.0:
            return
        
        if avg_confidence <= self.config.confidence_avg_critical:
            self._trigger_alert(
                severity=AlertSeverity.CRITICAL,
                alert_type="low_confidence",
                message=f"Average confidence critically low: {avg_confidence:.3f}",
                metric_value=avg_confidence,
                threshold=self.config.confidence_avg_critical
            )
        elif avg_confidence <= self.config.confidence_avg_warning:
            self._trigger_alert(
                severity=AlertSeverity.WARNING,
                alert_type="low_confidence",
                message=f"Average confidence low: {avg_confidence:.3f}",
                metric_value=avg_confidence,
                threshold=self.config.confidence_avg_warning
            )
    
    def _check_sessions(self):
        """Check session status."""
        summary = self.metrics_collector.get_summary()
        
        active_sessions = summary['sessions']['active']
        
        # Check max active sessions
        if active_sessions >= self.config.max_active_sessions:
            self._trigger_alert(
                severity=AlertSeverity.WARNING,
                alert_type="max_sessions",
                message=f"Maximum active sessions reached: {active_sessions}",
                metric_value=float(active_sessions),
                threshold=float(self.config.max_active_sessions)
            )
        
        # Check for stuck sessions
        current_time = time.time()
        for session_id, session_data in self.metrics_collector.active_sessions.items():
            duration = current_time - session_data['start_time']
            
            if duration >= self.config.stuck_session_duration:
                self._trigger_alert(
                    severity=AlertSeverity.WARNING,
                    alert_type="stuck_session",
                    message=f"Session possibly stuck: {session_id} (duration: {duration:.0f}s)",
                    metric_value=duration,
                    threshold=self.config.stuck_session_duration
                )
    
    def _check_cost(self):
        """Check cost metrics."""
        summary = self.metrics_collector.get_summary()
        
        uptime_hours = summary['uptime_hours']
        if uptime_hours == 0:
            return
        
        total_cost = summary['cost']['total_cost_usd']
        cost_per_hour = total_cost / uptime_hours
        
        if cost_per_hour >= self.config.cost_per_hour_critical:
            self._trigger_alert(
                severity=AlertSeverity.CRITICAL,
                alert_type="high_cost",
                message=f"Cost rate critically high: ${cost_per_hour:.2f}/hour",
                metric_value=cost_per_hour,
                threshold=self.config.cost_per_hour_critical
            )
        elif cost_per_hour >= self.config.cost_per_hour_warning:
            self._trigger_alert(
                severity=AlertSeverity.WARNING,
                alert_type="high_cost",
                message=f"Cost rate elevated: ${cost_per_hour:.2f}/hour",
                metric_value=cost_per_hour,
                threshold=self.config.cost_per_hour_warning
            )
    
    def _trigger_alert(
        self,
        severity: AlertSeverity,
        alert_type: str,
        message: str,
        metric_value: Optional[float] = None,
        threshold: Optional[float] = None
    ):
        """Trigger an alert."""
        with self.lock:
            alert = Alert(
                severity=severity,
                alert_type=alert_type,
                message=message,
                timestamp=time.time(),
                metric_value=metric_value,
                threshold=threshold
            )
            
            # Add to history
            self.alerts.append(alert)
            
            # Track count
            if alert_type not in self.alert_counts:
                self.alert_counts[alert_type] = 0
            self.alert_counts[alert_type] += 1
            
            # Log alert
            if severity == AlertSeverity.CRITICAL:
                logger.critical(str(alert))
            elif severity == AlertSeverity.WARNING:
                logger.warning(str(alert))
            else:
                logger.info(str(alert))
            
            # Invoke callback
            if self.alert_callback:
                try:
                    self.alert_callback(alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}", exc_info=True)
    
    def get_recent_alerts(self, limit: int = 10) -> List[Alert]:
        """Get recent alerts."""
        with self.lock:
            return self.alerts[-limit:]
    
    def get_alert_stats(self) -> dict:
        """Get alert statistics."""
        with self.lock:
            return {
                "total_alerts": len(self.alerts),
                "by_type": dict(self.alert_counts),
                "by_severity": {
                    "info": sum(1 for a in self.alerts if a.severity == AlertSeverity.INFO),
                    "warning": sum(1 for a in self.alerts if a.severity == AlertSeverity.WARNING),
                    "critical": sum(1 for a in self.alerts if a.severity == AlertSeverity.CRITICAL),
                },
            }
    
    def clear_alerts(self):
        """Clear alert history."""
        with self.lock:
            self.alerts.clear()
            self.alert_counts.clear()
            logger.info("Alert history cleared")
