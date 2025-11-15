"""
Multi-Presentation E2E Test Runner

Tests the slide matching algorithm across multiple diverse presentations:
1. Machine Learning Intro (academic/technical)
2. Business Strategy (business/corporate)
3. Python Tutorial (programming/code-heavy)

Calculates aggregate metrics and validates consistency across scenarios.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Import E2EMatchingTest directly
test_file = Path(__file__).parent / 'test_phase4_e2e_matching.py'
import importlib.util
spec = importlib.util.spec_from_file_location("test_phase4_e2e_matching", test_file)
test_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_module)
E2EMatchingTest = test_module.E2EMatchingTest


def run_single_test(test_name: str, test_file: str) -> dict:
    """Run E2E test on a single presentation"""
    print("\n" + "="*70)
    print(f"TESTING: {test_name}")
    print("="*70)
    
    test_path = Path(__file__).parent / 'fixtures' / 'test_presentations' / test_file
    
    if not test_path.exists():
        print(f"❌ Test file not found: {test_path}")
        return None
    
    test = E2EMatchingTest(str(test_path))
    results = test.run_full_test()
    
    return {
        'name': test_name,
        'file': test_file,
        'accuracy': results['accuracy'],
        'precision': results['precision'],
        'recall': results['recall'],
        'f1_score': results['f1_score'],
        'total_segments': results['total_segments'],
        'correct_matches': results['correct_matches'],
        'errors': results['errors']
    }


def print_summary(all_results: list):
    """Print aggregate summary across all tests"""
    print("\n" + "="*70)
    print("AGGREGATE RESULTS ACROSS ALL PRESENTATIONS")
    print("="*70)
    
    # Calculate aggregate metrics
    total_segments = sum(r['total_segments'] for r in all_results)
    total_correct = sum(r['correct_matches'] for r in all_results)
    total_errors = sum(r['errors'] for r in all_results)
    
    avg_accuracy = sum(r['accuracy'] for r in all_results) / len(all_results)
    avg_precision = sum(r['precision'] for r in all_results) / len(all_results)
    avg_recall = sum(r['recall'] for r in all_results) / len(all_results)
    avg_f1 = sum(r['f1_score'] for r in all_results) / len(all_results)
    
    print(f"\nTotal Test Segments:  {total_segments}")
    print(f"Total Correct:        {total_correct} ({total_correct/total_segments*100:.1f}%)")
    print(f"Total Errors:         {total_errors} ({total_errors/total_segments*100:.1f}%)")
    
    print("\n📊 AVERAGE METRICS:")
    print(f"   Average Accuracy:  {avg_accuracy*100:.1f}%")
    print(f"   Average Precision: {avg_precision*100:.1f}%")
    print(f"   Average Recall:    {avg_recall*100:.1f}%")
    print(f"   Average F1 Score:  {avg_f1*100:.1f}%")
    
    print("\n📋 PER-PRESENTATION BREAKDOWN:")
    print("-" * 70)
    print(f"{'Presentation':<30} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print("-" * 70)
    for r in all_results:
        print(f"{r['name']:<30} {r['accuracy']*100:>9.1f}% {r['precision']*100:>9.1f}% "
              f"{r['recall']*100:>9.1f}% {r['f1_score']*100:>9.1f}%")
    print("-" * 70)
    
    # Evaluate against targets
    print("\n" + "="*70)
    print("SUCCESS CRITERIA EVALUATION (Target: ≥75% average)")
    print("="*70)
    
    success = True
    
    if avg_accuracy >= 0.75:
        print(f"   ✅ Average Accuracy >= 75%:    {avg_accuracy*100:.1f}% PASS")
    else:
        print(f"   ❌ Average Accuracy >= 75%:    {avg_accuracy*100:.1f}% FAIL")
        success = False
    
    if avg_precision >= 0.85:
        print(f"   ✅ Average Precision >= 85%:   {avg_precision*100:.1f}% PASS")
    else:
        print(f"   ⚠️  Average Precision >= 85%:   {avg_precision*100:.1f}% WARNING")
    
    if avg_recall >= 0.75:
        print(f"   ✅ Average Recall >= 75%:      {avg_recall*100:.1f}% PASS")
    else:
        print(f"   ❌ Average Recall >= 75%:      {avg_recall*100:.1f}% FAIL")
        success = False
    
    if avg_f1 >= 0.80:
        print(f"   ✅ Average F1 Score >= 80%:    {avg_f1*100:.1f}% PASS")
    else:
        print(f"   ❌ Average F1 Score >= 80%:    {avg_f1*100:.1f}% FAIL")
        success = False
    
    # Check consistency across presentations
    accuracies = [r['accuracy'] for r in all_results]
    accuracy_variance = max(accuracies) - min(accuracies)
    
    print(f"\n📈 CONSISTENCY CHECK:")
    print(f"   Accuracy Range: {min(accuracies)*100:.1f}% - {max(accuracies)*100:.1f}%")
    print(f"   Variance: {accuracy_variance*100:.1f}%")
    
    if accuracy_variance <= 0.15:
        print(f"   ✅ Good consistency across presentations (variance ≤15%)")
    else:
        print(f"   ⚠️  High variance - algorithm may be scenario-dependent")
    
    # Final verdict
    print("\n" + "="*70)
    if success and all(r['accuracy'] >= 0.70 for r in all_results):
        print("✅ ALGORITHM READY FOR INTEGRATION")
        print("="*70)
        print("\n✨ All presentations meet minimum accuracy threshold!")
        print("   Next step: Integrate into file and streaming pipelines")
    else:
        print("⚠️  ADDITIONAL TUNING RECOMMENDED")
        print("="*70)
        print("\n💡 Suggestions:")
        
        # Identify weak presentations
        weak = [r for r in all_results if r['accuracy'] < 0.75]
        if weak:
            print(f"\n   Presentations below 75% target:")
            for r in weak:
                print(f"   - {r['name']}: {r['accuracy']*100:.1f}%")
        
        if avg_precision < 0.85:
            print("\n   📝 To improve precision:")
            print("      - Increase min_score_threshold")
            print("      - Reduce fuzzy_weight")
            print("      - Add more discriminative keywords")
        
        if avg_recall < 0.75:
            print("\n   📝 To improve recall:")
            print("      - Decrease min_score_threshold")
            print("      - Increase semantic_weight")
            print("      - Improve keyword extraction")
        
        if accuracy_variance > 0.15:
            print("\n   📝 To improve consistency:")
            print("      - Analyze scenario-specific patterns")
            print("      - Consider adaptive parameter selection")
            print("      - Review failed cases per presentation type")


def main():
    """Run all E2E tests"""
    print("\n" + "="*70)
    print("PHASE 4 MULTI-PRESENTATION E2E TEST SUITE")
    print("="*70)
    print("\nTesting slide matching algorithm across diverse scenarios:")
    print("  1. Machine Learning Intro - Academic/Technical content")
    print("  2. Business Strategy - Corporate/Business content")
    print("  3. Python Tutorial - Programming/Code-heavy content")
    
    tests = [
        ("Machine Learning Intro", "machine_learning_intro.json"),
        ("Business Strategy 2025", "business_strategy.json"),
        ("Python Tutorial", "python_tutorial.json")
    ]
    
    all_results = []
    
    for test_name, test_file in tests:
        result = run_single_test(test_name, test_file)
        if result:
            all_results.append(result)
    
    if len(all_results) == len(tests):
        print_summary(all_results)
    else:
        print("\n❌ Some tests failed to run. Check file paths and data.")


if __name__ == '__main__':
    main()
