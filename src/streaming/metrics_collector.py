"""
Metrics Collector for Streaming Sessions.

Tracks:
- Active session count
- Latency (p50, p95, p99)
- Error rates by type
- Confidence scores
- Cost per minute
- Throughput metrics
"""

import logging
import time
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime
import statistics

logger = logging.getLogger(__name__)


@dataclass
class LatencyMetrics:
    """Latency measurements."""
    measurements: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    def add(self, latency_ms: float):
        """Add latency measurement."""
        self.measurements.append(latency_ms)
    
    def get_percentiles(self) -> Dict[str, float]:
        """Calculate percentiles."""
        if not self.measurements:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        
        sorted_measurements = sorted(self.measurements)
        n = len(sorted_measurements)
        
        return {
            "p50": sorted_measurements[int(n * 0.50)] if n > 0 else 0.0,
            "p95": sorted_measurements[int(n * 0.95)] if n > 0 else 0.0,
            "p99": sorted_measurements[int(n * 0.99)] if n > 0 else 0.0,
            "avg": statistics.mean(sorted_measurements) if n > 0 else 0.0,
            "min": min(sorted_measurements) if n > 0 else 0.0,
            "max": max(sorted_measurements) if n > 0 else 0.0,
        }


@dataclass
class ErrorMetrics:
    """Error tracking."""
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    total_errors: int = 0
    last_error_time: Optional[float] = None
    last_error_message: Optional[str] = None
    
    def add_error(self, error_type: str, error_message: str):
        """Record an error."""
        self.errors_by_type[error_type] += 1
        self.total_errors += 1
        self.last_error_time = time.time()
        self.last_error_message = error_message
    
    def get_error_rate(self, total_requests: int) -> float:
        """Calculate error rate."""
        if total_requests == 0:
            return 0.0
        return self.total_errors / total_requests


@dataclass
class ConfidenceMetrics:
    """Confidence score tracking."""
    scores: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    def add(self, confidence: float):
        """Add confidence score."""
        if 0.0 <= confidence <= 1.0:
            self.scores.append(confidence)
    
    def get_stats(self) -> Dict[str, float]:
        """Get confidence statistics."""
        if not self.scores:
            return {"avg": 0.0, "min": 0.0, "max": 0.0}
        
        return {
            "avg": statistics.mean(self.scores),
            "min": min(self.scores),
            "max": max(self.scores),
            "median": statistics.median(self.scores),
        }


@dataclass
class CostMetrics:
    """Cost tracking."""
    # Google Cloud Speech V2 pricing: $2.16/hour for latest_long
    COST_PER_HOUR = 2.16
    COST_PER_MINUTE = COST_PER_HOUR / 60.0
    COST_PER_SECOND = COST_PER_MINUTE / 60.0
    
    total_audio_seconds: float = 0.0
    total_sessions: int = 0
    
    def add_audio_duration(self, duration_seconds: float):
        """Add audio duration."""
        self.total_audio_seconds += duration_seconds
    
    def add_session(self):
        """Add session count."""
        self.total_sessions += 1
    
    def get_total_cost(self) -> float:
        """Calculate total cost."""
        return self.total_audio_seconds * self.COST_PER_SECOND
    
    def get_cost_per_session(self) -> float:
        """Calculate average cost per session."""
        if self.total_sessions == 0:
            return 0.0
        return self.get_total_cost() / self.total_sessions
    
    def get_stats(self) -> Dict[str, float]:
        """Get cost statistics."""
        return {
            "total_audio_hours": self.total_audio_seconds / 3600.0,
            "total_audio_minutes": self.total_audio_seconds / 60.0,
            "total_cost_usd": self.get_total_cost(),
            "cost_per_session_usd": self.get_cost_per_session(),
            "total_sessions": self.total_sessions,
        }


@dataclass
class ThroughputMetrics:
    """Throughput tracking."""
    total_chunks: int = 0
    total_bytes: int = 0
    total_results: int = 0
    interim_results: int = 0
    final_results: int = 0
    start_time: float = field(default_factory=time.time)
    
    def add_chunk(self, chunk_size: int):
        """Add audio chunk."""
        self.total_chunks += 1
        self.total_bytes += chunk_size
    
    def add_result(self, is_final: bool):
        """Add result."""
        self.total_results += 1
        if is_final:
            self.final_results += 1
        else:
            self.interim_results += 1
    
    def get_rates(self) -> Dict[str, float]:
        """Calculate throughput rates."""
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return {
                "chunks_per_second": 0.0,
                "bytes_per_second": 0.0,
                "results_per_second": 0.0,
            }
        
        return {
            "chunks_per_second": self.total_chunks / elapsed,
            "bytes_per_second": self.total_bytes / elapsed,
            "results_per_second": self.total_results / elapsed,
            "elapsed_seconds": elapsed,
        }


class MetricsCollector:
    """
    Centralized metrics collection for streaming sessions.
    
    Tracks all important metrics for monitoring and alerting.
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        # Session metrics
        self.active_sessions: Dict[str, dict] = {}
        self.completed_sessions: int = 0
        
        # Latency metrics
        self.latency_interim = LatencyMetrics()
        self.latency_final = LatencyMetrics()
        self.latency_e2e = LatencyMetrics()
        
        # Error metrics
        self.errors = ErrorMetrics()
        
        # Confidence metrics
        self.confidence = ConfidenceMetrics()
        
        # Cost metrics
        self.cost = CostMetrics()
        
        # Throughput metrics
        self.throughput = ThroughputMetrics()
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Start time
        self.start_time = time.time()
        
        logger.info("MetricsCollector initialized")
    
    def register_session(self, session_id: str, presentation_id: str):
        """Register a new session."""
        with self.lock:
            self.active_sessions[session_id] = {
                "presentation_id": presentation_id,
                "start_time": time.time(),
                "chunks_sent": 0,
                "bytes_sent": 0,
                "results_received": 0,
            }
            self.cost.add_session()
            
            logger.info(f"Session registered: {session_id}")
    
    def unregister_session(self, session_id: str, duration_seconds: float):
        """Unregister a completed session."""
        with self.lock:
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            self.completed_sessions += 1
            self.cost.add_audio_duration(duration_seconds)
            
            logger.info(
                f"Session unregistered: {session_id} "
                f"(duration: {duration_seconds:.1f}s)"
            )
    
    def record_chunk_sent(self, session_id: str, chunk_size: int):
        """Record audio chunk sent."""
        with self.lock:
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["chunks_sent"] += 1
                self.active_sessions[session_id]["bytes_sent"] += chunk_size
            
            self.throughput.add_chunk(chunk_size)
    
    def record_result_received(
        self,
        session_id: str,
        is_final: bool,
        confidence: float,
        latency_ms: float
    ):
        """Record transcription result received."""
        with self.lock:
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["results_received"] += 1
            
            # Track latency
            if is_final:
                self.latency_final.add(latency_ms)
            else:
                self.latency_interim.add(latency_ms)
            
            # Track confidence
            self.confidence.add(confidence)
            
            # Track throughput
            self.throughput.add_result(is_final)
    
    def record_error(self, error_type: str, error_message: str):
        """Record an error."""
        with self.lock:
            self.errors.add_error(error_type, error_message)
            
            logger.warning(f"Error recorded: {error_type} - {error_message}")
    
    def get_active_session_count(self) -> int:
        """Get number of active sessions."""
        with self.lock:
            return len(self.active_sessions)
    
    def get_session_metrics(self, session_id: str) -> Optional[dict]:
        """Get metrics for specific session."""
        with self.lock:
            return self.active_sessions.get(session_id)
    
    def get_summary(self) -> dict:
        """Get comprehensive metrics summary."""
        with self.lock:
            uptime_seconds = time.time() - self.start_time
            
            return {
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": uptime_seconds,
                "uptime_hours": uptime_seconds / 3600.0,
                
                # Session metrics
                "sessions": {
                    "active": len(self.active_sessions),
                    "completed": self.completed_sessions,
                    "total": len(self.active_sessions) + self.completed_sessions,
                },
                
                # Latency metrics
                "latency": {
                    "interim_results": self.latency_interim.get_percentiles(),
                    "final_results": self.latency_final.get_percentiles(),
                },
                
                # Error metrics
                "errors": {
                    "total": self.errors.total_errors,
                    "by_type": dict(self.errors.errors_by_type),
                    "last_error": {
                        "time": self.errors.last_error_time,
                        "message": self.errors.last_error_message,
                    } if self.errors.last_error_time else None,
                },
                
                # Confidence metrics
                "confidence": self.confidence.get_stats(),
                
                # Cost metrics
                "cost": self.cost.get_stats(),
                
                # Throughput metrics
                "throughput": {
                    "total_chunks": self.throughput.total_chunks,
                    "total_bytes": self.throughput.total_bytes,
                    "total_results": self.throughput.total_results,
                    "interim_results": self.throughput.interim_results,
                    "final_results": self.throughput.final_results,
                    "rates": self.throughput.get_rates(),
                },
            }
    
    def get_dashboard_text(self) -> str:
        """Get text-based dashboard for terminal display."""
        summary = self.get_summary()
        
        lines = [
            "=" * 80,
            "STREAMING METRICS DASHBOARD",
            "=" * 80,
            f"Uptime: {summary['uptime_hours']:.2f} hours",
            f"Timestamp: {summary['timestamp']}",
            "",
            "SESSIONS:",
            f"  Active:    {summary['sessions']['active']}",
            f"  Completed: {summary['sessions']['completed']}",
            f"  Total:     {summary['sessions']['total']}",
            "",
            "LATENCY (ms):",
            f"  Interim Results:",
            f"    p50: {summary['latency']['interim_results']['p50']:.1f}ms",
            f"    p95: {summary['latency']['interim_results']['p95']:.1f}ms",
            f"    p99: {summary['latency']['interim_results']['p99']:.1f}ms",
            f"  Final Results:",
            f"    p50: {summary['latency']['final_results']['p50']:.1f}ms",
            f"    p95: {summary['latency']['final_results']['p95']:.1f}ms",
            f"    p99: {summary['latency']['final_results']['p99']:.1f}ms",
            "",
            "ERRORS:",
            f"  Total: {summary['errors']['total']}",
        ]
        
        if summary['errors']['by_type']:
            lines.append("  By Type:")
            for error_type, count in summary['errors']['by_type'].items():
                lines.append(f"    {error_type}: {count}")
        
        lines.extend([
            "",
            "CONFIDENCE:",
            f"  Average: {summary['confidence']['avg']:.3f}",
            f"  Min:     {summary['confidence']['min']:.3f}",
            f"  Max:     {summary['confidence']['max']:.3f}",
            "",
            "COST:",
            f"  Total Audio: {summary['cost']['total_audio_hours']:.2f} hours",
            f"  Total Cost:  ${summary['cost']['total_cost_usd']:.2f} USD",
            f"  Per Session: ${summary['cost']['cost_per_session_usd']:.4f} USD",
            "",
            "THROUGHPUT:",
            f"  Total Chunks:  {summary['throughput']['total_chunks']}",
            f"  Total Bytes:   {summary['throughput']['total_bytes']:,}",
            f"  Total Results: {summary['throughput']['total_results']}",
            f"    Interim: {summary['throughput']['interim_results']}",
            f"    Final:   {summary['throughput']['final_results']}",
            "",
            "RATES:",
            f"  Chunks/sec:  {summary['throughput']['rates']['chunks_per_second']:.2f}",
            f"  Bytes/sec:   {summary['throughput']['rates']['bytes_per_second']:.0f}",
            f"  Results/sec: {summary['throughput']['rates']['results_per_second']:.2f}",
            "=" * 80,
        ])
        
        return "\n".join(lines)
    
    def reset(self):
        """Reset all metrics."""
        with self.lock:
            self.active_sessions.clear()
            self.completed_sessions = 0
            
            self.latency_interim = LatencyMetrics()
            self.latency_final = LatencyMetrics()
            self.latency_e2e = LatencyMetrics()
            
            self.errors = ErrorMetrics()
            self.confidence = ConfidenceMetrics()
            self.cost = CostMetrics()
            self.throughput = ThroughputMetrics()
            
            self.start_time = time.time()
            
            logger.info("Metrics reset")


# Global metrics instance
_global_metrics: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsCollector()
    return _global_metrics
