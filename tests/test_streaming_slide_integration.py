"""
Test Phase 4 streaming integration.

Tests real-time slide matching in streaming pipeline with latency validation.
"""

import unittest
import time
from pathlib import Path
from unittest.mock import Mock

from src.streaming.result_handler import (
    StreamingResultHandler,
    StreamingResult
)


class TestStreamingSlideMatching(unittest.TestCase):
    """Test streaming pipeline with slide matching."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests."""
        cls.test_pdf = Path(__file__).parent / "test_data" / "machine_learning_intro.pdf"
        if not cls.test_pdf.exists():
            raise FileNotFoundError(f"Test PDF not found: {cls.test_pdf}")
    
    def test_handler_initialization_no_slides(self):
        """Test handler initialization without slide matching."""
        handler = StreamingResultHandler()
        
        self.assertFalse(handler.enable_slide_matching)
        self.assertIsNone(handler.slide_processor)
        self.assertFalse(handler.slides_loaded)
    
    def test_handler_initialization_with_slides(self):
        """Test handler initialization with slide matching enabled."""
        handler = StreamingResultHandler(enable_slide_matching=True)
        
        self.assertTrue(handler.enable_slide_matching)
        self.assertIsNone(handler.slide_processor)
        self.assertFalse(handler.slides_loaded)
    
    def test_preload_slides(self):
        """Test slide preloading at session start."""
        handler = StreamingResultHandler(enable_slide_matching=True)
        
        # Preload slides
        start_time = time.time()
        stats = handler.preload_slides(str(self.test_pdf), use_embeddings=False)
        load_time = time.time() - start_time
        
        # Verify loaded
        self.assertTrue(handler.slides_loaded)
        self.assertIsNotNone(handler.slide_processor)
        
        # Verify stats
        self.assertIn('slide_count', stats)
        self.assertIn('keywords_count', stats)
        self.assertIn('has_embeddings', stats)
        self.assertGreater(stats['slide_count'], 0)
        self.assertFalse(stats['has_embeddings'])  # Disabled for speed
        
        # Verify load time (should be <5s without embeddings)
        self.assertLess(load_time, 5.0,
                       f"Slide preload took {load_time:.2f}s (target: <5s)")
        
        print(f"\n✅ Preload: {stats['slide_count']} slides in {load_time:.2f}s")
    
    def test_streaming_without_slides(self):
        """Test streaming transcription without slide matching."""
        results = []
        handler = StreamingResultHandler(
            result_callback=lambda r: results.append(r)
        )
        
        # Simulate streaming results
        handler.handle_interim_result("これは機械学習について", 0.8)
        handler.handle_interim_result("これは機械学習についての", 0.85)
        result = handler.handle_final_result(
            "これは機械学習についての講義です",
            0.9,
            timestamp=0.0
        )
        
        # Verify result
        self.assertTrue(result.is_final)
        self.assertEqual(result.confidence, 0.9)
        self.assertIsNone(result.slide_id)  # No slide matching
        self.assertEqual(result.slide_score, 0.0)
    
    def test_streaming_with_slides(self):
        """Test streaming transcription with slide matching."""
        results = []
        handler = StreamingResultHandler(
            result_callback=lambda r: results.append(r),
            enable_slide_matching=True
        )
        
        # Preload slides
        handler.preload_slides(str(self.test_pdf), use_embeddings=False)
        
        # Simulate streaming results with real transcript
        test_segments = [
            ("機械学習の基本的な概念について説明します", 0.0),
            ("教師あり学習は入力と出力のペアから学習します", 5.0),
            ("ニューラルネットワークは人間の脳を模倣した構造です", 15.0),
        ]
        
        matched_count = 0
        latencies = []
        
        for text, timestamp in test_segments:
            # Simulate interim results
            handler.handle_interim_result(text[:10], 0.7)
            handler.handle_interim_result(text[:20], 0.8)
            
            # Final result with matching
            start_time = time.time()
            result = handler.handle_final_result(text, 0.9, timestamp=timestamp)
            latency = (time.time() - start_time) * 1000
            latencies.append(latency)
            
            # Verify result structure
            self.assertTrue(result.is_final)
            self.assertEqual(result.confidence, 0.9)
            
            # Check if matched
            if result.slide_id is not None:
                matched_count += 1
                self.assertGreater(result.slide_score, 0.0)
                self.assertGreater(result.slide_confidence, 0.0)
                self.assertIsInstance(result.matched_keywords, list)
                
                print(f"\n  Segment {matched_count}: '{text[:30]}...'")
                print(f"    -> Slide {result.slide_id}")
                print(f"    Score: {result.slide_score:.2f}")
                print(f"    Keywords: {result.matched_keywords[:3]}")
                print(f"    Latency: {latency:.1f}ms")
        
        # Verify matching occurred
        self.assertGreater(matched_count, 0,
                          "Expected at least some segments to match slides")
        
        # Verify latency (target: <200ms per segment)
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        self.assertLess(avg_latency, 200,
                       f"Average latency {avg_latency:.1f}ms exceeds 200ms target")
        self.assertLess(max_latency, 300,
                       f"Max latency {max_latency:.1f}ms exceeds 300ms threshold")
        
        print(f"\n✅ Streaming match: {matched_count}/{len(test_segments)} segments")
        print(f"   Latency: avg={avg_latency:.1f}ms, max={max_latency:.1f}ms")
    
    def test_slide_timeline_generation(self):
        """Test timeline generation from streaming results."""
        handler = StreamingResultHandler(enable_slide_matching=True)
        handler.preload_slides(str(self.test_pdf), use_embeddings=False)
        
        # Add some results
        test_segments = [
            ("機械学習の基本的な概念について", 0.0),
            ("教師あり学習について説明します", 5.0),
            ("ニューラルネットワークの構造", 15.0),
            ("モデルの評価方法について", 25.0),
        ]
        
        for text, timestamp in test_segments:
            handler.handle_final_result(text, 0.9, timestamp=timestamp)
        
        # Generate timeline
        timeline = handler.get_slide_timeline()
        
        # Verify timeline structure
        self.assertIsInstance(timeline, list)
        if timeline:  # Only if matches occurred
            for entry in timeline:
                self.assertIn('slide_id', entry)
                self.assertIn('start_time', entry)
                self.assertIn('end_time', entry)
                self.assertGreaterEqual(entry['end_time'], entry['start_time'])
            
            print(f"\n✅ Timeline: {len(timeline)} entries")
            for i, entry in enumerate(timeline[:3], 1):
                print(f"   {i}. Slide {entry['slide_id']}: "
                     f"{entry['start_time']:.1f}s - {entry['end_time']:.1f}s")
    
    def test_matching_stats(self):
        """Test matching statistics collection."""
        handler = StreamingResultHandler(enable_slide_matching=True)
        handler.preload_slides(str(self.test_pdf), use_embeddings=False)
        
        # Add several results
        for i in range(5):
            text = f"機械学習についてのセグメント {i}"
            handler.handle_final_result(text, 0.9, timestamp=float(i * 5))
        
        # Get stats
        stats = handler.get_matching_stats()
        
        # Verify stats structure
        self.assertIn('enabled', stats)
        self.assertIn('total_segments', stats)
        self.assertIn('matched_segments', stats)
        self.assertIn('match_rate', stats)
        self.assertTrue(stats['enabled'])
        self.assertEqual(stats['total_segments'], 5)
        
        # Verify latency stats
        if stats['matched_segments'] > 0:
            self.assertIn('avg_latency_ms', stats)
            self.assertIn('max_latency_ms', stats)
            self.assertIn('min_latency_ms', stats)
            self.assertIn('latency_p95_ms', stats)
            
            # Check latency targets
            self.assertLess(stats['avg_latency_ms'], 200,
                           f"Average latency {stats['avg_latency_ms']:.1f}ms exceeds 200ms")
            
            print(f"\n✅ Matching stats:")
            print(f"   Match rate: {stats['match_rate']*100:.1f}%")
            print(f"   Avg latency: {stats['avg_latency_ms']:.1f}ms")
            print(f"   P95 latency: {stats['latency_p95_ms']:.1f}ms")
    
    def test_export_with_slides(self):
        """Test result export includes slide data."""
        handler = StreamingResultHandler(enable_slide_matching=True)
        handler.preload_slides(str(self.test_pdf), use_embeddings=False)
        
        # Add results
        handler.handle_final_result("機械学習について", 0.9, timestamp=0.0)
        handler.handle_final_result("教師あり学習について", 0.9, timestamp=5.0)
        
        # Export
        exported = handler.export_results()
        
        # Verify structure
        self.assertIn('full_transcript', exported)
        self.assertIn('segments', exported)
        self.assertIn('metrics', exported)
        self.assertIn('exported_at', exported)
        
        # Verify slide-specific data
        self.assertIn('slide_timeline', exported)
        self.assertIn('slide_matching_stats', exported)
        
        # Verify segment slide data
        for segment in exported['segments']:
            if 'slide' in segment:
                self.assertIn('slide_id', segment['slide'])
                self.assertIn('score', segment['slide'])
                self.assertIn('confidence', segment['slide'])
                self.assertIn('matched_keywords', segment['slide'])
        
        print(f"\n✅ Export includes slide data")
    
    def test_reset_clears_slide_data(self):
        """Test that reset clears slide matching state."""
        handler = StreamingResultHandler(enable_slide_matching=True)
        handler.preload_slides(str(self.test_pdf), use_embeddings=False)
        
        # Add results
        handler.handle_final_result("機械学習について", 0.9, timestamp=0.0)
        
        # Verify loaded
        self.assertTrue(handler.slides_loaded)
        self.assertIsNotNone(handler.slide_processor)
        self.assertGreater(len(handler.match_latencies), 0)
        
        # Reset
        handler.reset()
        
        # Verify cleared
        self.assertFalse(handler.slides_loaded)
        self.assertIsNone(handler.slide_processor)
        self.assertEqual(len(handler.match_latencies), 0)
        self.assertEqual(len(handler.final_results), 0)


def run_basic_validation():
    """Run basic validation tests."""
    print("\n" + "="*70)
    print("Phase 4 Streaming Integration - Basic Validation")
    print("="*70)
    
    # Test 1: Handler initialization
    print("\n1. Testing handler initialization...")
    handler = StreamingResultHandler(enable_slide_matching=True)
    print("   ✅ Handler created with slide matching enabled")
    
    # Test 2: Slide preloading
    print("\n2. Testing slide preloading...")
    test_pdf = Path(__file__).parent / "test_data" / "machine_learning_intro.pdf"
    if not test_pdf.exists():
        print(f"   ⚠️  Test PDF not found: {test_pdf}")
        print("   Skipping slide tests")
        return
    
    start_time = time.time()
    stats = handler.preload_slides(str(test_pdf), use_embeddings=False)
    load_time = time.time() - start_time
    
    print(f"   ✅ Loaded {stats['slide_count']} slides in {load_time:.2f}s")
    print(f"      Keywords: {stats['keywords_count']}")
    print(f"      Embeddings: {stats['has_embeddings']}")
    
    # Test 3: Real-time matching
    print("\n3. Testing real-time matching...")
    test_text = "機械学習の基本的な概念について説明します"
    
    start_time = time.time()
    result = handler.handle_final_result(test_text, 0.9, timestamp=0.0)
    latency = (time.time() - start_time) * 1000
    
    if result.slide_id is not None:
        print(f"   ✅ Matched to slide {result.slide_id}")
        print(f"      Score: {result.slide_score:.2f}")
        print(f"      Latency: {latency:.1f}ms")
        print(f"      Keywords: {result.matched_keywords[:3]}")
    else:
        print(f"   ⚠️  No match found")
    
    # Test 4: Latency validation
    print("\n4. Testing latency across multiple segments...")
    latencies = []
    for i in range(10):
        text = f"機械学習についてのテスト {i}"
        start_time = time.time()
        handler.handle_final_result(text, 0.9, timestamp=float(i * 2))
        latencies.append((time.time() - start_time) * 1000)
    
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    
    print(f"   Average: {avg_latency:.1f}ms")
    print(f"   Maximum: {max_latency:.1f}ms")
    
    if avg_latency < 200:
        print(f"   ✅ Latency meets <200ms target")
    else:
        print(f"   ⚠️  Latency exceeds 200ms target")
    
    # Test 5: Stats
    print("\n5. Testing statistics collection...")
    stats = handler.get_matching_stats()
    print(f"   Match rate: {stats['match_rate']*100:.1f}%")
    print(f"   Avg latency: {stats['avg_latency_ms']:.1f}ms")
    print(f"   P95 latency: {stats['latency_p95_ms']:.1f}ms")
    
    print("\n" + "="*70)
    print("✅ Streaming integration validation complete!")
    print("="*70)


if __name__ == "__main__":
    # Run basic validation first
    try:
        run_basic_validation()
    except Exception as e:
        print(f"\n❌ Validation error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n\nRunning full test suite...\n")
    
    # Run full unit tests
    unittest.main()
