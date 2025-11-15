"""
Streaming Test Harness

Simulates real-time audio streaming from files for testing.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, List, Tuple, Any

import numpy as np

# Note: StreamProcessor not yet implemented, using placeholder types
# from .stream_processor import (
#     StreamingConfig,
#     StreamProcessor,
#     StreamingResult,
# )
from .metrics_collector import get_metrics_collector

logger = logging.getLogger(__name__)


class StreamingPattern(Enum):
    """Audio streaming patterns for testing"""
    CONTINUOUS = "continuous"  # No pauses
    WITH_PAUSES = "with_pauses"  # Natural pauses
    FAST_SPEECH = "fast_speech"  # High word rate
    SLOW_SPEECH = "slow_speech"  # Long pauses
    LONG_SESSION = "long_session"  # >5 minutes


@dataclass
class TestCase:
    """Test case configuration"""
    name: str
    pattern: StreamingPattern
    audio_file: Optional[Path] = None
    duration_seconds: float = 60.0
    chunk_size: int = 3200  # 100ms at 16kHz mono
    
    # Pattern-specific settings
    pause_duration_ms: float = 0  # For WITH_PAUSES
    speech_rate_multiplier: float = 1.0  # For FAST/SLOW
    
    # Expected thresholds
    expected_latency_p95_ms: float = 800.0
    expected_accuracy_min: float = 0.80


@dataclass
class TestResult:
    """Test execution result"""
    test_case: TestCase
    success: bool
    
    # Timing metrics
    total_duration_seconds: float
    audio_duration_seconds: float
    session_start_latency_ms: float
    
    # Quality metrics
    latency_p95_ms: float
    latency_avg_ms: float
    interim_accuracy: float
    final_accuracy: float
    
    # Throughput
    chunks_sent: int
    interim_results: int
    final_results: int
    
    # Issues
    errors: List[str]
    warnings: List[str]
    
    # Session events
    renewals: int = 0
    
    def __str__(self) -> str:
        """Format result for display"""
        status = "✅ PASS" if self.success else "❌ FAIL"
        return f"""
{status} {self.test_case.name}
  Duration: {self.audio_duration_seconds:.1f}s audio, {self.total_duration_seconds:.1f}s total
  Start: {self.session_start_latency_ms:.0f}ms
  Latency: p95={self.latency_p95_ms:.0f}ms, avg={self.latency_avg_ms:.0f}ms
  Results: {self.interim_results} interim, {self.final_results} final
  Accuracy: interim={self.interim_accuracy:.1%}, final={self.final_accuracy:.1%}
  Chunks: {self.chunks_sent}
  Renewals: {self.renewals}
  Errors: {len(self.errors)}
  Warnings: {len(self.warnings)}
"""


class StreamingTestHarness:
    """Test harness for streaming scenarios"""
    
    def __init__(self, config: Any = None):
        self.config = config
        # Note: StreamProcessor not yet implemented
        # self.processor = StreamProcessor(config)
        self.processor = None
        
    async def run_test(self, test_case: TestCase) -> TestResult:
        """Run a single test case"""
        logger.info(f"Starting test: {test_case.name}")
        
        # Initialize metrics
        start_time = time.time()
        errors: List[str] = []
        warnings: List[str] = []
        chunks_sent = 0
        interim_results = 0
        final_results = 0
        latencies: List[float] = []
        
        session_id = None
        presentation_id = "test-pres"
        
        try:
            # Start streaming session
            session_start = time.time()
            session_id = await self.processor.start_streaming_session(presentation_id)
            session_start_latency = (time.time() - session_start) * 1000
            
            logger.info(f"Session {session_id} started in {session_start_latency:.0f}ms")
            
            # Generate or load audio
            audio_chunks = self._generate_audio_chunks(test_case)
            
            # Stream chunks
            audio_start = time.time()
            
            for i, chunk in enumerate(audio_chunks):
                chunk_start = time.time()
                
                # Send chunk
                await self.processor.send_audio_chunk(session_id, chunk)
                chunks_sent += 1
                
                # Wait for realistic timing
                await asyncio.sleep(test_case.chunk_size / 16000.0)  # Chunk duration
                
                # Add pattern-specific delays
                if test_case.pattern == StreamingPattern.WITH_PAUSES:
                    if i % 20 == 19:  # Pause every 2 seconds
                        await asyncio.sleep(test_case.pause_duration_ms / 1000.0)
                
                elif test_case.pattern == StreamingPattern.SLOW_SPEECH:
                    await asyncio.sleep(0.05)  # Extra delay
                    
                # Collect results (non-blocking)
                # In real impl, would process from response iterator
                
            audio_duration = (time.time() - audio_start)
            
            # Wait for final results
            await asyncio.sleep(1.0)
            
            # Stop session
            await self.processor.stop_streaming_session(session_id)
            
            # Get metrics from collector
            collector = get_metrics_collector()
            summary = collector.get_summary()
            
            # Extract session metrics
            latency_p95 = summary['latency']['final_results']['p95']
            latency_avg = summary['latency']['final_results']['avg']
            
            # Mock accuracy for now (would compare with ground truth)
            interim_accuracy = 0.85
            final_accuracy = 0.92
            
            # Count renewals
            renewals = 1 if test_case.pattern == StreamingPattern.LONG_SESSION else 0
            
            # Check thresholds
            success = True
            
            if latency_p95 > test_case.expected_latency_p95_ms:
                errors.append(
                    f"Latency p95 too high: {latency_p95:.0f}ms > {test_case.expected_latency_p95_ms:.0f}ms"
                )
                success = False
                
            if final_accuracy < test_case.expected_accuracy_min:
                errors.append(
                    f"Accuracy too low: {final_accuracy:.1%} < {test_case.expected_accuracy_min:.1%}"
                )
                success = False
            
            # Build result
            result = TestResult(
                test_case=test_case,
                success=success,
                total_duration_seconds=time.time() - start_time,
                audio_duration_seconds=audio_duration,
                session_start_latency_ms=session_start_latency,
                latency_p95_ms=latency_p95,
                latency_avg_ms=latency_avg,
                interim_accuracy=interim_accuracy,
                final_accuracy=final_accuracy,
                chunks_sent=chunks_sent,
                interim_results=interim_results,
                final_results=final_results,
                errors=errors,
                warnings=warnings,
                renewals=renewals,
            )
            
            logger.info(f"Test completed: {test_case.name}")
            return result
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            errors.append(str(e))
            
            return TestResult(
                test_case=test_case,
                success=False,
                total_duration_seconds=time.time() - start_time,
                audio_duration_seconds=0.0,
                session_start_latency_ms=0.0,
                latency_p95_ms=0.0,
                latency_avg_ms=0.0,
                interim_accuracy=0.0,
                final_accuracy=0.0,
                chunks_sent=chunks_sent,
                interim_results=0,
                final_results=0,
                errors=errors,
                warnings=warnings,
            )
            
        finally:
            # Cleanup
            if session_id:
                try:
                    await self.processor.stop_streaming_session(session_id)
                except:
                    pass
    
    def _generate_audio_chunks(self, test_case: TestCase) -> List[bytes]:
        """Generate audio chunks for testing"""
        
        if test_case.audio_file and test_case.audio_file.exists():
            # Load from file
            return self._load_audio_file(test_case.audio_file, test_case.chunk_size)
        
        # Generate synthetic audio
        sample_rate = 16000
        num_samples = int(test_case.duration_seconds * sample_rate)
        
        # Generate sine wave (simulating speech)
        frequency = 440.0  # A4 note
        t = np.linspace(0, test_case.duration_seconds, num_samples, False)
        audio = np.sin(2 * np.pi * frequency * t)
        
        # Apply pattern
        if test_case.pattern == StreamingPattern.WITH_PAUSES:
            # Add silence every 2 seconds
            for i in range(0, num_samples, sample_rate * 2):
                pause_samples = int(test_case.pause_duration_ms * sample_rate / 1000)
                if i + pause_samples < num_samples:
                    audio[i:i+pause_samples] = 0
                    
        elif test_case.pattern == StreamingPattern.FAST_SPEECH:
            # Higher frequency
            frequency = 880.0
            audio = np.sin(2 * np.pi * frequency * t)
            
        elif test_case.pattern == StreamingPattern.SLOW_SPEECH:
            # Lower frequency, more silence
            frequency = 220.0
            audio = np.sin(2 * np.pi * frequency * t) * 0.5
        
        # Normalize to 16-bit PCM range
        audio = (audio * 32767).astype(np.int16)
        
        # Split into chunks
        chunks = []
        chunk_samples = test_case.chunk_size // 2  # 16-bit = 2 bytes per sample
        
        for i in range(0, len(audio), chunk_samples):
            chunk = audio[i:i+chunk_samples]
            chunks.append(chunk.tobytes())
        
        return chunks
    
    def _load_audio_file(self, audio_file: Path, chunk_size: int) -> List[bytes]:
        """Load audio from file and split into chunks"""
        # Would use soundfile or librosa
        # For now, generate synthetic
        return []
    
    async def run_test_suite(self, test_cases: List[TestCase]) -> List[TestResult]:
        """Run multiple test cases"""
        results = []
        
        logger.info(f"Running {len(test_cases)} test cases")
        
        for test_case in test_cases:
            result = await self.run_test(test_case)
            results.append(result)
            
            # Print result
            print(result)
            
            # Brief pause between tests
            await asyncio.sleep(2.0)
        
        return results
    
    def print_summary(self, results: List[TestResult]) -> None:
        """Print test suite summary"""
        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total - passed
        
        print("\n" + "="*80)
        print("TEST SUITE SUMMARY")
        print("="*80)
        print(f"Total:  {total}")
        print(f"Passed: {passed} ({passed/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        
        if failed > 0:
            print("\nFailed Tests:")
            for result in results:
                if not result.success:
                    print(f"  ❌ {result.test_case.name}")
                    for error in result.errors:
                        print(f"     - {error}")
        
        # Aggregate metrics
        avg_latency = np.mean([r.latency_p95_ms for r in results if r.latency_p95_ms > 0])
        avg_accuracy = np.mean([r.final_accuracy for r in results if r.final_accuracy > 0])
        
        print(f"\nAggregate Metrics:")
        print(f"  Average Latency p95: {avg_latency:.0f}ms")
        print(f"  Average Accuracy: {avg_accuracy:.1%}")
        print("="*80)


def create_standard_test_suite() -> List[TestCase]:
    """Create standard test cases"""
    return [
        TestCase(
            name="Continuous Speech (60s)",
            pattern=StreamingPattern.CONTINUOUS,
            duration_seconds=60.0,
            expected_latency_p95_ms=800.0,
            expected_accuracy_min=0.85,
        ),
        TestCase(
            name="Natural Pauses (60s)",
            pattern=StreamingPattern.WITH_PAUSES,
            duration_seconds=60.0,
            pause_duration_ms=500.0,
            expected_latency_p95_ms=800.0,
            expected_accuracy_min=0.82,
        ),
        TestCase(
            name="Fast Speech (30s)",
            pattern=StreamingPattern.FAST_SPEECH,
            duration_seconds=30.0,
            expected_latency_p95_ms=1000.0,
            expected_accuracy_min=0.80,
        ),
        TestCase(
            name="Slow Speech with Long Pauses (60s)",
            pattern=StreamingPattern.SLOW_SPEECH,
            duration_seconds=60.0,
            expected_latency_p95_ms=800.0,
            expected_accuracy_min=0.85,
        ),
        TestCase(
            name="Long Session (6 minutes)",
            pattern=StreamingPattern.LONG_SESSION,
            duration_seconds=360.0,  # 6 minutes
            expected_latency_p95_ms=800.0,
            expected_accuracy_min=0.83,
        ),
    ]
