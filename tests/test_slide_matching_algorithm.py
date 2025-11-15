"""
Phase 4 End-to-End Integration Tests for Slide Matching

Tests the complete pipeline:
1. PDF extraction (simulated with JSON data)
2. Japanese NLP processing
3. Keyword indexing
4. Embedding generation
5. Multi-pass matching (exact + fuzzy + semantic)
6. Score combination with temporal smoothing

Tests against realistic presentation data with ground truth annotations.
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pdf_processing.japanese_nlp import JapaneseNLP
from pdf_processing.keyword_indexer import KeywordIndexer
from pdf_processing.embedding_generator import EmbeddingGenerator
from matching.exact_matcher import ExactMatcher
from matching.fuzzy_matcher import FuzzyMatcher
from matching.semantic_matcher import SemanticMatcher
from matching.score_combiner import ScoreCombiner, MatchResult


class E2EMatchingTest:
    """End-to-end test for slide matching pipeline"""
    
    def __init__(self, test_data_path: str):
        """Initialize test with presentation data"""
        with open(test_data_path, 'r', encoding='utf-8') as f:
            self.test_data = json.load(f)
        
        # Initialize components
        self.nlp = JapaneseNLP()
        self.keyword_indexer = KeywordIndexer()
        self.embedding_gen = EmbeddingGenerator()
        
        # Process slides
        self.slide_data = self._process_slides()
        
        # Initialize matchers
        self.exact_matcher = ExactMatcher(self.keyword_indexer.inverted_index)
        self.fuzzy_matcher = FuzzyMatcher(self.slide_data['slide_keywords'])
        self.semantic_matcher = SemanticMatcher(self.embedding_gen)
        self.score_combiner = ScoreCombiner()
    
    def _process_slides(self) -> Dict:
        """Process all slides: extract keywords, build index, generate embeddings"""
        print("\n" + "="*70)
        print("PROCESSING SLIDES")
        print("="*70)
        
        slides = self.test_data['slides']
        slide_texts = []
        slide_keywords = {}
        all_keywords_list = []
        
        for slide in slides:
            page = slide['page']
            full_text = f"{slide['title']}\n{slide['content']}"
            slide_texts.append(full_text)
            
            # Extract keywords
            keywords = self.nlp.extract_keywords(full_text)
            slide_keywords[page] = keywords
            all_keywords_list.append((page, kw) for kw in keywords)
            
            print(f"\nSlide {page}: {slide['title']}")
            print(f"  Keywords ({len(keywords)}): {', '.join(keywords[:10])}")
        
        # Build keyword index
        print(f"\n📚 Building keyword index...")
        # Convert to list of keyword lists (not dict)
        slide_ids = [s['page'] for s in slides]
        keywords_list = [slide_keywords[sid] for sid in slide_ids]
        self.keyword_indexer.build_index(keywords_list, slide_ids)
        print(f"   ✅ Index built: {len(self.keyword_indexer.inverted_index)} unique keywords")
        
        # Generate embeddings
        print(f"\n🧠 Generating embeddings...")
        self.embedding_gen.generate_embeddings(slide_texts, slide_ids)
        print(f"   ✅ Embeddings generated: {len(slide_ids)} slides")
        
        # Flatten keywords for fuzzy matcher
        all_keywords = []
        for slide_id, keywords in slide_keywords.items():
            for keyword in keywords:
                all_keywords.append((slide_id, keyword))
        
        return {
            'slides': slides,
            'slide_texts': slide_texts,
            'slide_keywords': slide_keywords,
            'all_keywords': all_keywords
        }
    
    def run_matching_tests(self) -> Tuple[int, int, int]:
        """
        Run matching on all transcript segments and evaluate accuracy.
        
        Returns:
            (correct_matches, total_segments, perfect_matches)
        """
        print("\n" + "="*70)
        print("RUNNING MATCHING TESTS")
        print("="*70)
        
        segments = self.test_data['transcript_segments']
        correct_matches = 0
        perfect_matches = 0
        total_segments = len(segments)
        
        match_results = []
        
        for seg in segments:
            segment_id = seg['segment_id']
            text = seg['text']
            expected_slide = seg['expected_slide']
            start_time = seg['start_time']
            
            # Extract keywords from transcript segment
            keywords = self.nlp.extract_keywords(text)
            readings = [self.nlp.get_reading(text)]
            
            # Run three-pass matching
            exact_results = self.exact_matcher.match(keywords)
            fuzzy_results = self.fuzzy_matcher.match(keywords, readings)
            semantic_results = self.semantic_matcher.match(text, top_k=5)
            
            # Combine scores
            metadata = {'timestamp': start_time}
            match_result = self.score_combiner.combine(
                exact_results,
                fuzzy_results,
                semantic_results,
                metadata
            )
            
            # Check if match is correct
            matched_slide = match_result.slide_id if match_result else None
            is_correct = (matched_slide == expected_slide)
            
            if is_correct:
                correct_matches += 1
                if match_result and match_result.confidence >= 0.8:
                    perfect_matches += 1
            
            match_results.append({
                'segment_id': segment_id,
                'text': text,
                'expected_slide': expected_slide,
                'matched_slide': matched_slide,
                'correct': is_correct,
                'score': match_result.score if match_result else 0.0,
                'confidence': match_result.confidence if match_result else 0.0,
                'keywords': keywords,
                'matched_keywords': match_result.matched_keywords if match_result else []
            })
        
        return correct_matches, total_segments, perfect_matches, match_results
    
    def print_detailed_results(self, match_results: List[Dict]):
        """Print detailed results for analysis"""
        print("\n" + "="*70)
        print("DETAILED RESULTS")
        print("="*70)
        
        # Print first 10 matches
        print("\n📊 First 10 Matches:")
        for result in match_results[:10]:
            status = "✅" if result['correct'] else "❌"
            print(f"\n{status} {result['segment_id']}")
            print(f"   Text: {result['text'][:60]}...")
            print(f"   Expected: Slide {result['expected_slide']}")
            print(f"   Matched:  Slide {result['matched_slide']} (score: {result['score']:.2f}, conf: {result['confidence']:.2f})")
            print(f"   Keywords: {', '.join(result['keywords'][:5])}")
            if result['matched_keywords']:
                print(f"   Matched:  {', '.join(result['matched_keywords'][:5])}")
        
        # Print errors
        errors = [r for r in match_results if not r['correct']]
        if errors:
            print(f"\n\n❌ Errors ({len(errors)} total):")
            for err in errors[:5]:
                print(f"\n   {err['segment_id']}: {err['text'][:50]}...")
                print(f"   Expected: Slide {err['expected_slide']}, Got: Slide {err['matched_slide']}")
                print(f"   Score: {err['score']:.2f}, Confidence: {err['confidence']:.2f}")
    
    def calculate_metrics(self, match_results: List[Dict]) -> Dict:
        """Calculate precision, recall, F1 score"""
        # Per-slide statistics
        slide_stats = {}
        for slide in self.test_data['slides']:
            page = slide['page']
            slide_stats[page] = {
                'true_positives': 0,
                'false_positives': 0,
                'false_negatives': 0
            }
        
        for result in match_results:
            expected = result['expected_slide']
            matched = result['matched_slide']
            
            if matched is not None:
                if matched == expected:
                    slide_stats[expected]['true_positives'] += 1
                else:
                    slide_stats[matched]['false_positives'] += 1
                    slide_stats[expected]['false_negatives'] += 1
            else:
                slide_stats[expected]['false_negatives'] += 1
        
        # Overall metrics
        total_tp = sum(s['true_positives'] for s in slide_stats.values())
        total_fp = sum(s['false_positives'] for s in slide_stats.values())
        total_fn = sum(s['false_negatives'] for s in slide_stats.values())
        
        precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'slide_stats': slide_stats
        }
    
    def run_full_test(self) -> Dict:
        """
        Run complete E2E test and return results.
        
        Returns:
            dict with accuracy, precision, recall, f1_score, total_segments, correct_matches, errors
        """
        correct_matches, total_segments, perfect_matches, match_results = self.run_matching_tests()
        metrics = self.calculate_metrics(match_results)
        
        accuracy = correct_matches / total_segments
        errors = total_segments - correct_matches
        
        return {
            'accuracy': accuracy,
            'precision': metrics['precision'],
            'recall': metrics['recall'],
            'f1_score': metrics['f1_score'],
            'total_segments': total_segments,
            'correct_matches': correct_matches,
            'perfect_matches': perfect_matches,
            'errors': errors,
            'match_results': match_results
        }


def main():
    """Run end-to-end tests"""
    print("\n" + "="*70)
    print("PHASE 4: END-TO-END SLIDE MATCHING TESTS")
    print("="*70)
    
    # Load test data
    test_data_path = Path(__file__).parent / 'fixtures' / 'test_presentations' / 'machine_learning_intro.json'
    
    if not test_data_path.exists():
        print(f"\n❌ Test data not found: {test_data_path}")
        return
    
    print(f"\n📁 Loading test data: {test_data_path.name}")
    
    # Initialize test
    try:
        test = E2EMatchingTest(str(test_data_path))
    except Exception as e:
        print(f"\n❌ Failed to initialize test: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Run matching tests
    try:
        correct, total, perfect, results = test.run_matching_tests()
    except Exception as e:
        print(f"\n❌ Failed during matching: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Print summary
    accuracy = correct / total if total > 0 else 0
    perfect_rate = perfect / total if total > 0 else 0
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"\n📊 Matching Accuracy:")
    print(f"   Correct matches:  {correct}/{total} ({accuracy*100:.1f}%)")
    print(f"   Perfect matches:  {perfect}/{total} ({perfect_rate*100:.1f}%) [conf >= 0.8]")
    print(f"   Errors:           {total - correct}")
    
    # Calculate detailed metrics
    metrics = test.calculate_metrics(results)
    
    print(f"\n📈 Performance Metrics:")
    print(f"   Precision:        {metrics['precision']:.3f}")
    print(f"   Recall:           {metrics['recall']:.3f}")
    print(f"   F1 Score:         {metrics['f1_score']:.3f}")
    
    # Print detailed results
    test.print_detailed_results(results)
    
    # Success criteria
    print("\n" + "="*70)
    print("SUCCESS CRITERIA EVALUATION")
    print("="*70)
    
    success = True
    
    print(f"\n✓ Target Metrics:")
    
    if accuracy >= 0.75:
        print(f"   ✅ Accuracy >= 75%:       {accuracy*100:.1f}% PASS")
    else:
        print(f"   ❌ Accuracy >= 75%:       {accuracy*100:.1f}% FAIL")
        success = False
    
    if metrics['precision'] >= 0.85:
        print(f"   ✅ Precision >= 85%:      {metrics['precision']*100:.1f}% PASS")
    else:
        print(f"   ❌ Precision >= 85%:      {metrics['precision']*100:.1f}% FAIL")
        success = False
    
    if metrics['recall'] >= 0.75:
        print(f"   ✅ Recall >= 75%:         {metrics['recall']*100:.1f}% PASS")
    else:
        print(f"   ❌ Recall >= 75%:         {metrics['recall']*100:.1f}% FAIL")
        success = False
    
    if metrics['f1_score'] >= 0.80:
        print(f"   ✅ F1 Score >= 80%:       {metrics['f1_score']*100:.1f}% PASS")
    else:
        print(f"   ❌ F1 Score >= 80%:       {metrics['f1_score']*100:.1f}% FAIL")
        success = False
    
    if success:
        print("\n" + "="*70)
        print("✅ ALL E2E TESTS PASSED!")
        print("="*70)
    else:
        print("\n" + "="*70)
        print("❌ SOME TESTS FAILED - NEEDS TUNING")
        print("="*70)
        print("\n💡 Suggestions:")
        if metrics['precision'] < 0.85:
            print("   - Increase min_score_threshold to reduce false positives")
            print("   - Reduce fuzzy_match_weight to be more conservative")
        if metrics['recall'] < 0.75:
            print("   - Decrease min_score_threshold to catch more matches")
            print("   - Increase semantic_match_weight for better coverage")
        if accuracy < 0.75:
            print("   - Review failed cases for patterns")
            print("   - Consider adjusting temporal_boost or switch_threshold")


if __name__ == '__main__':
    main()
