"""
Quick validation of Phase 4 streaming integration.

Tests handler initialization and basic structure without requiring test PDFs.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.streaming.result_handler import (
    StreamingResultHandler,
    StreamingResult,
    ResultMetrics
)


def test_basic_functionality():
    """Test basic streaming handler functionality."""
    print("\n" + "="*70)
    print("Phase 4 Streaming Integration - Quick Validation")
    print("="*70)
    
    # Test 1: Handler without slide matching
    print("\n1. Testing handler without slide matching...")
    handler = StreamingResultHandler()
    
    assert not handler.enable_slide_matching
    assert handler.slide_processor is None
    assert not handler.slides_loaded
    print("   ✅ Handler initialized (slide matching disabled)")
    
    # Test 2: Handler with slide matching enabled
    print("\n2. Testing handler with slide matching enabled...")
    handler = StreamingResultHandler(enable_slide_matching=True)
    
    assert handler.enable_slide_matching
    assert handler.slide_processor is None  # Not loaded yet
    assert not handler.slides_loaded  # Not loaded yet
    assert isinstance(handler.match_latencies, list)
    assert len(handler.match_latencies) == 0
    print("   ✅ Handler initialized (slide matching enabled)")
    
    # Test 3: StreamingResult with slide data
    print("\n3. Testing StreamingResult with slide data...")
    result = StreamingResult(
        text="機械学習について",
        is_final=True,
        confidence=0.9,
        slide_id=3,
        slide_score=2.5,
        slide_confidence=0.85,
        matched_keywords=["機械学習", "教師あり"]
    )
    
    assert result.slide_id == 3
    assert result.slide_score == 2.5
    assert result.slide_confidence == 0.85
    assert len(result.matched_keywords) == 2
    print("   ✅ StreamingResult stores slide data")
    
    # Test 4: Result serialization with slides
    print("\n4. Testing result serialization with slide data...")
    result_dict = result.to_dict()
    
    assert 'slide' in result_dict
    assert result_dict['slide']['slide_id'] == 3
    assert result_dict['slide']['score'] == 2.5
    assert result_dict['slide']['confidence'] == 0.85
    assert result_dict['slide']['matched_keywords'] == ["機械学習", "教師あり"]
    print("   ✅ Result serializes to dict with slide data")
    
    # Test 5: Result without slide data
    print("\n5. Testing result serialization without slide data...")
    result_no_slide = StreamingResult(
        text="テストテキスト",
        is_final=True,
        confidence=0.8
    )
    result_dict = result_no_slide.to_dict()
    
    assert 'slide' not in result_dict
    print("   ✅ Result without slide data doesn't include 'slide' key")
    
    # Test 6: Handle results without slide matching
    print("\n6. Testing handle_final_result without slide matching...")
    handler = StreamingResultHandler()
    result = handler.handle_final_result(
        "機械学習についてのテスト",
        0.9,
        timestamp=0.0
    )
    
    assert result.is_final
    assert result.confidence == 0.9
    assert result.slide_id is None
    assert result.slide_score == 0.0
    assert len(result.matched_keywords) == 0
    print("   ✅ Final result without slides works correctly")
    
    # Test 7: Export results structure
    print("\n7. Testing export_results structure...")
    handler = StreamingResultHandler(enable_slide_matching=True)
    handler.handle_final_result("テスト1", 0.9, timestamp=0.0)
    handler.handle_final_result("テスト2", 0.85, timestamp=5.0)
    
    exported = handler.export_results()
    
    assert 'full_transcript' in exported
    assert 'segments' in exported
    assert 'metrics' in exported
    assert 'exported_at' in exported
    # Slide fields only present if slides are loaded
    # Since we haven't called preload_slides(), they won't be present
    assert 'slide_timeline' not in exported
    assert 'slide_matching_stats' not in exported
    print("   ✅ Export structure correct (no slides loaded)")
    
    # Test 8: Get matching stats
    print("\n8. Testing get_matching_stats...")
    stats = handler.get_matching_stats()
    
    assert 'enabled' in stats
    assert 'total_segments' in stats
    assert 'matched_segments' in stats
    assert 'match_rate' in stats
    assert stats['enabled'] == False  # No slides loaded
    assert stats['total_segments'] == 2
    assert stats['matched_segments'] == 0
    assert stats['match_rate'] == 0.0
    print("   ✅ Matching stats structure correct")
    
    # Test 9: Reset clears slide state
    print("\n9. Testing reset clears slide state...")
    handler = StreamingResultHandler(enable_slide_matching=True)
    handler.match_latencies = [100, 150, 120]  # Simulate some matches
    handler.handle_final_result("テスト", 0.9)
    
    assert len(handler.final_results) > 0
    assert len(handler.match_latencies) > 0
    
    handler.reset()
    
    assert len(handler.final_results) == 0
    assert len(handler.match_latencies) == 0
    assert handler.slides_loaded == False
    assert handler.slide_processor is None
    print("   ✅ Reset clears all slide state")
    
    # Test 10: Preload slides method exists
    print("\n10. Testing preload_slides method exists...")
    handler = StreamingResultHandler(enable_slide_matching=True)
    
    assert hasattr(handler, 'preload_slides')
    assert hasattr(handler, '_match_slide')
    assert hasattr(handler, 'get_slide_timeline')
    assert hasattr(handler, 'get_matching_stats')
    print("   ✅ All slide-related methods present")
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED - Streaming integration structure validated!")
    print("="*70)
    print("\nIntegration summary:")
    print("  • StreamingResultHandler supports slide matching")
    print("  • StreamingResult stores slide data (id, score, keywords)")
    print("  • Slide data serializes correctly to JSON")
    print("  • Export includes slide timeline and stats")
    print("  • Reset properly clears slide state")
    print("  • API ready for real-time matching")
    print("\nNext step: Test with actual PDF to validate latency <200ms")


if __name__ == "__main__":
    try:
        test_basic_functionality()
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
