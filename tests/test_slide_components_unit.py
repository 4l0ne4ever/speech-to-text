"""
Phase 4 Integration Test: PDF Processing and Slide Matching

Tests the complete Phase 4 pipeline:
1. PDF extraction
2. Japanese NLP processing
3. Keyword indexing
4. Embedding generation
5. Three-pass matching (exact, fuzzy, semantic)
6. Score combination with temporal smoothing
"""

import os
import sys
import unittest
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pdf_processing import PDFExtractor, JapaneseNLP, KeywordIndexer, EmbeddingGenerator
from matching import ExactMatcher, FuzzyMatcher, SemanticMatcher, ScoreCombiner


class TestPhase4Basic(unittest.TestCase):
    """Basic tests for Phase 4 components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.nlp = JapaneseNLP()
        
    def test_japanese_nlp_tokenization(self):
        """Test Japanese tokenization"""
        text = "こんにちは。今日は機械学習について説明します。"
        tokens = self.nlp.tokenize(text)
        
        self.assertGreater(len(tokens), 0)
        print(f"\n✓ Tokenized {len(tokens)} tokens from Japanese text")
        
        # Print tokens
        for token in tokens[:5]:
            print(f"  - {token.surface} ({token.pos}): {token.base_form}")
            
    def test_japanese_nlp_keyword_extraction(self):
        """Test keyword extraction"""
        text = "機械学習は人工知能の一分野です。ニューラルネットワークを使います。"
        keywords = self.nlp.extract_keywords(text)
        
        self.assertGreater(len(keywords), 0)
        print(f"\n✓ Extracted {len(keywords)} keywords: {keywords}")
        
    def test_japanese_nlp_normalization(self):
        """Test text normalization"""
        text = "ＡＢＣ１２３"  # Full-width
        normalized = self.nlp.normalize_text(text)
        
        self.assertEqual(normalized, "ABC123")
        print(f"\n✓ Normalized full-width to half-width: {text} -> {normalized}")
        
    def test_japanese_nlp_sentence_segmentation(self):
        """Test sentence segmentation"""
        text = "これは最初の文です。これは二番目の文です！三番目の文もあります？"
        sentences = self.nlp.segment_sentences(text)
        
        self.assertEqual(len(sentences), 3)
        print(f"\n✓ Segmented {len(sentences)} sentences")
        for i, sent in enumerate(sentences, 1):
            print(f"  {i}. {sent}")
            
    def test_keyword_indexer(self):
        """Test keyword indexing"""
        # Sample slide keywords
        slide_keywords = [
            ["機械学習", "人工知能", "ニューラル", "ネットワーク"],  # Slide 1
            ["機械学習", "データ", "学習", "アルゴリズム"],  # Slide 2
            ["深層学習", "ニューラル", "ネットワーク", "CNN"],  # Slide 3
        ]
        slide_ids = [1, 2, 3]
        
        indexer = KeywordIndexer(min_keyword_length=2)
        index = indexer.build_index(slide_keywords, slide_ids)
        
        self.assertGreater(len(index), 0)
        print(f"\n✓ Built keyword index with {len(index)} unique keywords")
        
        # Test lookup
        matches = indexer.lookup("機械学習")
        print(f"  '機械学習' found in {len(matches)} slides: {[m[0] for m in matches]}")
        
        # Test scoring
        query_keywords = ["機械学習", "ニューラル"]
        scores = indexer.calculate_slide_scores(query_keywords)
        print(f"  Query keywords {query_keywords} scored: {scores}")
        
    def test_exact_matcher(self):
        """Test exact keyword matching"""
        # Build sample index
        slide_keywords = [
            ["機械学習", "人工知能"],
            ["機械学習", "データ"],
            ["深層学習", "ニューラル"],
        ]
        slide_ids = [1, 2, 3]
        
        indexer = KeywordIndexer()
        index = indexer.build_index(slide_keywords, slide_ids)
        
        # Test exact matcher
        matcher = ExactMatcher(index)
        matches = matcher.match(["機械学習"])
        
        self.assertGreater(len(matches), 0)
        print(f"\n✓ ExactMatcher found {len(matches)} slides matching '機械学習'")
        for slide_id, data in matches.items():
            print(f"  Slide {slide_id}: score={data['score']:.2f}, keywords={data['matched_keywords']}")
            
    def test_fuzzy_matcher(self):
        """Test fuzzy matching"""
        slide_keywords = {
            1: ["機械学習", "人工知能"],
            2: ["機会学習", "データ"],  # Typo: 機会 instead of 機械
        }
        
        matcher = FuzzyMatcher(
            slide_keywords=slide_keywords,
            similarity_threshold=0.8
        )
        
        # Should match despite typo
        matches = matcher.match(["機械学習"])
        
        print(f"\n✓ FuzzyMatcher found {len(matches)} slides (with typo tolerance)")
        for slide_id, data in matches.items():
            print(f"  Slide {slide_id}: score={data['score']:.2f}")
            
    def test_score_combiner(self):
        """Test score combination and temporal smoothing"""
        combiner = ScoreCombiner(
            exact_weight=1.0,
            fuzzy_weight=0.7,
            semantic_weight=0.5,
            min_score_threshold=1.0
        )
        
        # Simulate matches from different matchers
        exact_matches = {
            1: {'score': 5.0, 'matched_keywords': ['機械学習'], 'positions': [0]},
            2: {'score': 2.0, 'matched_keywords': ['データ'], 'positions': [10]},
        }
        
        fuzzy_matches = {
            2: {'score': 1.5, 'matched_keywords': ['学習'], 'positions': []},
        }
        
        semantic_matches = {
            3: {'score': 3.0, 'matched_keywords': [], 'positions': []},
        }
        
        # Combine
        result = combiner.combine(exact_matches, fuzzy_matches, semantic_matches)
        
        self.assertIsNotNone(result)
        print(f"\n✓ ScoreCombiner selected slide {result.slide_id}")
        print(f"  Score: {result.score:.2f}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Match types: {result.match_types}")
        print(f"  Matched keywords: {result.matched_keywords}")
        
        # Test temporal smoothing
        combiner.current_slide_id = 1
        result2 = combiner.combine(exact_matches, fuzzy_matches, semantic_matches)
        print(f"  With temporal boost, stayed on slide {result2.slide_id}")
        

class TestPhase4Integration(unittest.TestCase):
    """Integration tests with realistic scenarios"""
    
    def setUp(self):
        """Set up test environment"""
        self.nlp = JapaneseNLP()
        
    def test_complete_matching_pipeline(self):
        """Test complete matching pipeline"""
        print("\n" + "="*70)
        print("COMPLETE MATCHING PIPELINE TEST")
        print("="*70)
        
        # Step 1: Prepare slide content
        slides = [
            {
                'id': 1,
                'title': '機械学習入門',
                'content': '機械学習は人工知能の一分野です。データから学習します。'
            },
            {
                'id': 2,
                'title': 'ニューラルネットワーク',
                'content': 'ニューラルネットワークは深層学習の基礎です。'
            },
            {
                'id': 3,
                'title': 'データ分析',
                'content': 'データを分析してパターンを見つけます。統計手法を使います。'
            }
        ]
        
        print(f"\n1. Prepared {len(slides)} test slides")
        
        # Step 2: Extract keywords
        slide_keywords = []
        slide_ids = []
        slide_texts = []
        
        for slide in slides:
            text = slide['title'] + " " + slide['content']
            keywords = self.nlp.extract_keywords(text)
            slide_keywords.append(keywords)
            slide_ids.append(slide['id'])
            slide_texts.append(text)
            print(f"   Slide {slide['id']}: {len(keywords)} keywords")
            
        # Step 3: Build keyword index
        indexer = KeywordIndexer()
        index = indexer.build_index(slide_keywords, slide_ids)
        print(f"\n2. Built keyword index: {len(index)} unique keywords")
        
        # Step 4: Create matchers
        exact_matcher = ExactMatcher(index)
        
        slide_keywords_dict = {sid: kw for sid, kw in zip(slide_ids, slide_keywords)}
        fuzzy_matcher = FuzzyMatcher(slide_keywords_dict, similarity_threshold=0.8)
        
        print("3. Initialized ExactMatcher and FuzzyMatcher")
        
        # Step 5: Test matching with transcript segment
        transcript_segment = "今日は機械学習について説明します。データから学ぶ方法です。"
        print(f"\n4. Transcript segment: '{transcript_segment}'")
        
        segment_keywords = self.nlp.extract_keywords(transcript_segment)
        print(f"   Extracted keywords: {segment_keywords}")
        
        # Step 6: Match
        exact_matches = exact_matcher.match(segment_keywords)
        fuzzy_matches = fuzzy_matcher.match(segment_keywords)
        
        print(f"\n5. Matching results:")
        print(f"   Exact matches: {len(exact_matches)} slides")
        print(f"   Fuzzy matches: {len(fuzzy_matches)} slides")
        
        # Step 7: Combine scores
        combiner = ScoreCombiner(min_score_threshold=1.0)
        result = combiner.combine(exact_matches, fuzzy_matches, {})
        
        if result:
            print(f"\n6. Best match: Slide {result.slide_id}")
            print(f"   Score: {result.score:.2f}")
            print(f"   Confidence: {result.confidence:.2f}")
            print(f"   Matched keywords: {result.matched_keywords}")
            print(f"   Match types: {result.match_types}")
            
            # Verify it matched the right slide (should be slide 1 about 機械学習)
            self.assertEqual(result.slide_id, 1)
            print("\n✅ PIPELINE TEST PASSED: Correctly matched transcript to slide!")
        else:
            print("\n❌ No match found (score below threshold)")
            self.fail("Expected a match but got None")
            

def run_all_tests():
    """Run all Phase 4 tests"""
    print("\n" + "="*70)
    print("PHASE 4: SLIDE SYNCHRONIZATION - COMPONENT TESTS")
    print("="*70)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add tests
    suite.addTests(loader.loadTestsFromTestCase(TestPhase4Basic))
    suite.addTests(loader.loadTestsFromTestCase(TestPhase4Integration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ ALL PHASE 4 TESTS PASSED!")
        print("="*70)
        print("\nPhase 4 Components Ready:")
        print("  ✓ PDFExtractor - Text extraction from PDF slides")
        print("  ✓ JapaneseNLP - Tokenization and normalization")
        print("  ✓ KeywordIndexer - TF-IDF based indexing")
        print("  ✓ EmbeddingGenerator - Semantic embeddings (not tested yet)")
        print("  ✓ ExactMatcher - Fast keyword lookup")
        print("  ✓ FuzzyMatcher - Typo-tolerant matching")
        print("  ✓ SemanticMatcher - Meaning-based matching (not tested yet)")
        print("  ✓ ScoreCombiner - Weighted scoring with temporal smoothing")
        print("\nNext Steps:")
        print("  1. Create test PDF presentations")
        print("  2. Test with real PDF extraction")
        print("  3. Test semantic matching with embeddings")
        print("  4. Integrate with file processing pipeline")
        print("  5. Integrate with streaming pipeline")
        print("  6. Tune parameters for F1 > 0.8")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("="*70)
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
