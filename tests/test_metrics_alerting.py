"""
Test Metrics Collector and Alerting System

Tests metric tracking and alert triggering.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.streaming.metrics_collector import (
    MetricsCollector,
    LatencyMetrics,
    ErrorMetrics,
    ConfidenceMetrics,
    CostMetrics,
)
from src.streaming.alerting import (
    AlertManager,
    AlertConfig,
    AlertSeverity,
)


def test_latency_metrics():
    """Test 1: Latency Metrics"""
    print("\n" + "="*60)
    print("TEST 1: Latency Metrics")
    print("="*60)
    
    latency = LatencyMetrics()
    
    # Add measurements
    measurements = [100, 200, 150, 300, 250, 180, 220, 350, 280, 190]
    for ms in measurements:
        latency.add(ms)
    
    percentiles = latency.get_percentiles()
    
    print(f"   Added {len(measurements)} measurements")
    print(f"   p50: {percentiles['p50']:.1f}ms")
    print(f"   p95: {percentiles['p95']:.1f}ms")
    print(f"   p99: {percentiles['p99']:.1f}ms")
    print(f"   avg: {percentiles['avg']:.1f}ms")
    
    assert percentiles['p50'] > 0
    assert percentiles['p95'] > percentiles['p50']
    assert percentiles['p99'] >= percentiles['p95']
    
    print(f"✅ Latency percentiles calculated correctly")


def test_error_metrics():
    """Test 2: Error Metrics"""
    print("\n" + "="*60)
    print("TEST 2: Error Metrics")
    print("="*60)
    
    errors = ErrorMetrics()
    
    # Add errors
    errors.add_error("timeout", "Connection timeout")
    errors.add_error("timeout", "Another timeout")
    errors.add_error("invalid_audio", "Audio format error")
    
    print(f"   Total errors: {errors.total_errors}")
    print(f"   By type: {dict(errors.errors_by_type)}")
    
    assert errors.total_errors == 3
    assert errors.errors_by_type["timeout"] == 2
    assert errors.errors_by_type["invalid_audio"] == 1
    
    # Calculate error rate
    error_rate = errors.get_error_rate(total_requests=100)
    print(f"   Error rate: {error_rate:.1%}")
    assert error_rate == 0.03
    
    print(f"✅ Error tracking works correctly")


def test_confidence_metrics():
    """Test 3: Confidence Metrics"""
    print("\n" + "="*60)
    print("TEST 3: Confidence Metrics")
    print("="*60)
    
    confidence = ConfidenceMetrics()
    
    # Add scores
    scores = [0.95, 0.88, 0.92, 0.85, 0.90, 0.87, 0.93]
    for score in scores:
        confidence.add(score)
    
    stats = confidence.get_stats()
    
    print(f"   Added {len(scores)} confidence scores")
    print(f"   Avg: {stats['avg']:.3f}")
    print(f"   Min: {stats['min']:.3f}")
    print(f"   Max: {stats['max']:.3f}")
    
    assert 0.85 <= stats['avg'] <= 0.95
    assert stats['min'] == 0.85
    assert stats['max'] == 0.95
    
    print(f"✅ Confidence stats calculated correctly")


def test_cost_metrics():
    """Test 4: Cost Metrics"""
    print("\n" + "="*60)
    print("TEST 4: Cost Metrics")
    print("="*60)
    
    cost = CostMetrics()
    
    # Add sessions
    cost.add_session()
    cost.add_session()
    cost.add_session()
    
    # Add audio duration (10 minutes per session)
    cost.add_audio_duration(600)  # 10 min
    cost.add_audio_duration(600)
    cost.add_audio_duration(600)
    
    stats = cost.get_stats()
    
    print(f"   Total sessions: {stats['total_sessions']}")
    print(f"   Total audio: {stats['total_audio_minutes']:.1f} minutes")
    print(f"   Total cost: ${stats['total_cost_usd']:.4f}")
    print(f"   Cost per session: ${stats['cost_per_session_usd']:.4f}")
    
    assert stats['total_sessions'] == 3
    assert stats['total_audio_minutes'] == 30.0
    assert stats['total_cost_usd'] > 0
    
    # Verify pricing: $2.16/hour = $0.036/minute
    expected_cost = 30.0 * (2.16 / 60.0)
    assert abs(stats['total_cost_usd'] - expected_cost) < 0.01
    
    print(f"✅ Cost calculation correct")


def test_metrics_collector():
    """Test 5: MetricsCollector Integration"""
    print("\n" + "="*60)
    print("TEST 5: MetricsCollector")
    print("="*60)
    
    collector = MetricsCollector()
    
    # Register session
    collector.register_session("session-1", "pres-1")
    assert collector.get_active_session_count() == 1
    print(f"✅ Session registered")
    
    # Record chunks
    collector.record_chunk_sent("session-1", 3200)
    collector.record_chunk_sent("session-1", 4800)
    collector.record_chunk_sent("session-1", 6400)
    print(f"✅ Chunks recorded")
    
    # Record results
    collector.record_result_received("session-1", is_final=False, confidence=0.85, latency_ms=150)
    collector.record_result_received("session-1", is_final=True, confidence=0.92, latency_ms=200)
    print(f"✅ Results recorded")
    
    # Record errors
    collector.record_error("timeout", "Test timeout")
    print(f"✅ Error recorded")
    
    # Get summary
    summary = collector.get_summary()
    
    print(f"\n   Summary:")
    print(f"   - Active sessions: {summary['sessions']['active']}")
    print(f"   - Total chunks: {summary['throughput']['total_chunks']}")
    print(f"   - Total results: {summary['throughput']['total_results']}")
    print(f"   - Total errors: {summary['errors']['total']}")
    
    assert summary['sessions']['active'] == 1
    assert summary['throughput']['total_chunks'] == 3
    assert summary['throughput']['total_results'] == 2
    assert summary['errors']['total'] == 1
    
    # Unregister session
    collector.unregister_session("session-1", duration_seconds=60.0)
    assert collector.get_active_session_count() == 0
    print(f"✅ Session unregistered")
    
    # Print dashboard
    print(f"\n   Dashboard:")
    dashboard = collector.get_dashboard_text()
    print(dashboard)
    
    print("\n✅ MetricsCollector integration works")


def test_alert_manager():
    """Test 6: Alert Manager"""
    print("\n" + "="*60)
    print("TEST 6: Alert Manager")
    print("="*60)
    
    collector = MetricsCollector()
    
    # Track alerts
    triggered_alerts = []
    
    def alert_callback(alert):
        triggered_alerts.append(alert)
        print(f"   🚨 Alert: {alert}")
    
    # Configure alerts with low thresholds for testing
    config = AlertConfig(
        latency_p95_warning=100.0,  # Low threshold
        latency_p95_critical=200.0,
        error_rate_warning=5.0,
        confidence_avg_warning=0.9,  # High threshold
    )
    
    alert_manager = AlertManager(
        metrics_collector=collector,
        config=config,
        alert_callback=alert_callback
    )
    
    # Register session
    collector.register_session("session-1", "pres-1")
    
    # Add high latency
    for i in range(10):
        collector.record_result_received(
            "session-1",
            is_final=True,
            confidence=0.95,
            latency_ms=250.0  # Above critical threshold
        )
    
    # Check latency manually
    alert_manager._check_latency()
    
    # Should trigger critical alert
    assert len(triggered_alerts) > 0
    assert any(a.severity == AlertSeverity.CRITICAL for a in triggered_alerts)
    print(f"✅ High latency alert triggered")
    
    # Add low confidence
    triggered_alerts.clear()
    for i in range(10):
        collector.record_result_received(
            "session-1",
            is_final=True,
            confidence=0.85,  # Below warning threshold
            latency_ms=50.0
        )
    
    alert_manager._check_confidence()
    
    # Should trigger warning
    assert len(triggered_alerts) > 0
    print(f"✅ Low confidence alert triggered")
    
    # Get alert stats
    stats = alert_manager.get_alert_stats()
    print(f"\n   Alert Stats:")
    print(f"   - Total: {stats['total_alerts']}")
    print(f"   - By severity: {stats['by_severity']}")
    
    print("\n✅ Alert manager works correctly")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("METRICS & ALERTING TESTS")
    print("="*60)
    
    try:
        test_latency_metrics()
        test_error_metrics()
        test_confidence_metrics()
        test_cost_metrics()
        test_metrics_collector()
        test_alert_manager()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        print("\nMonitoring system is ready!")
        print("\nKey features:")
        print("  • Latency tracking (p50/p95/p99)")
        print("  • Error rate monitoring")
        print("  • Confidence score tracking")
        print("  • Cost calculation")
        print("  • Automated alerting")
        print("  • Dashboard display")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
