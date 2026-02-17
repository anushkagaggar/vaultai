from datetime import datetime, timedelta
from app.confidence.scorer import (
    ConfidenceInput,
    compute_confidence,
)

def test_case_a_new_user():
    """New user: 3 transactions, 2 days, spike"""
    inputs = ConfidenceInput(
        total_transactions=3,
        first_expense_at=datetime.now() - timedelta(days=2),
        last_expense_at=datetime.now(),
        current_month=3000,
        previous_month=100,
        classification="success"
    )
    result = compute_confidence(inputs)
    print(f"Case A (New User): {result.final_confidence}")
    print(f"  coverage={result.coverage_score}, window={result.window_score}, stability={result.stability_score}, explanation={result.explanation_score}")
    assert 0.10 <= result.final_confidence <= 0.35


def test_case_b_normal_user():
    """Normal user: 45 transactions, 60 days, mild variation"""
    inputs = ConfidenceInput(
        total_transactions=45,
        first_expense_at=datetime.now() - timedelta(days=60),
        last_expense_at=datetime.now(),
        current_month=2000,
        previous_month=1800,
        classification="success"
    )
    result = compute_confidence(inputs)
    print(f"Case B (Normal User): {result.final_confidence}")
    print(f"  coverage={result.coverage_score}, window={result.window_score}, stability={result.stability_score}, explanation={result.explanation_score}")
    assert 0.60 <= result.final_confidence <= 0.90


def test_case_c_mature_user():
    """Mature user: 120 transactions, 1 year, stable"""
    inputs = ConfidenceInput(
        total_transactions=120,
        first_expense_at=datetime.now() - timedelta(days=365),
        last_expense_at=datetime.now(),
        current_month=3000,
        previous_month=2900,
        classification="success"
    )
    result = compute_confidence(inputs)
    print(f"Case C (Mature User): {result.final_confidence}")
    print(f"  coverage={result.coverage_score}, window={result.window_score}, stability={result.stability_score}, explanation={result.explanation_score}")
    assert 0.85 <= result.final_confidence <= 1.0


def test_case_d_fallback():
    """
    Fallback: Same as normal user but explanation degraded.
    
    Expected difference from Case B:
    0.15 weight × (1.0 - 0.65) = 0.0525 reduction
    So: ~0.79 - 0.05 = ~0.74
    """
    inputs = ConfidenceInput(
        total_transactions=45,
        first_expense_at=datetime.now() - timedelta(days=60),
        last_expense_at=datetime.now(),
        current_month=2000,
        previous_month=1800,
        classification="fallback"
    )
    result = compute_confidence(inputs)
    print(f"Case D (Fallback): {result.final_confidence}")
    print(f"  coverage={result.coverage_score}, window={result.window_score}, stability={result.stability_score}, explanation={result.explanation_score}")
    # ✅ Corrected range: fallback reduces score by ~0.05 (not 0.20)
    assert 0.65 <= result.final_confidence <= 0.80


def test_case_e_no_data():
    """Edge case: No data at all"""
    inputs = ConfidenceInput(
        total_transactions=0,
        first_expense_at=None,
        last_expense_at=None,
        current_month=0,
        previous_month=0,
        classification="success"
    )
    result = compute_confidence(inputs)
    print(f"Case E (No Data): {result.final_confidence}")
    print(f"  coverage={result.coverage_score}, window={result.window_score}, stability={result.stability_score}, explanation={result.explanation_score}")
    # coverage=0, window=0, stability=1.0 (no change), explanation=1.0
    # = 0.35×0 + 0.25×0 + 0.25×1.0 + 0.15×1.0 = 0.40
    assert 0.35 <= result.final_confidence <= 0.45


def test_success_vs_fallback_difference():
    """
    Verify fallback always scores lower than success
    for identical data.
    """
    base_inputs = dict(
        total_transactions=45,
        first_expense_at=datetime.now() - timedelta(days=60),
        last_expense_at=datetime.now(),
        current_month=2000,
        previous_month=1800,
    )
    
    success_result = compute_confidence(ConfidenceInput(**base_inputs, classification="success"))
    fallback_result = compute_confidence(ConfidenceInput(**base_inputs, classification="fallback"))
    
    difference = round(success_result.final_confidence - fallback_result.final_confidence, 2)
    expected_diff = round(0.15 * (1.0 - 0.65), 2)  # weight × score_difference
    
    print(f"\nSuccess confidence:  {success_result.final_confidence}")
    print(f"Fallback confidence: {fallback_result.final_confidence}")
    print(f"Difference: {difference} (expected ~{expected_diff})")
    
    assert fallback_result.final_confidence < success_result.final_confidence
    assert abs(difference - expected_diff) <= 0.02  # Allow rounding tolerance


if __name__ == "__main__":
    test_case_a_new_user()
    test_case_b_normal_user()
    test_case_c_mature_user()
    test_case_d_fallback()
    test_case_e_no_data()
    test_success_vs_fallback_difference()
    print("\n✅ All confidence tests passed!")