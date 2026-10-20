"""Unit tests for the Outcome Verification framework."""
import pytest
from backend.models.schemas import VerificationRule
from backend.verification.verifier import OutcomeVerifier

def test_verifier_no_rule():
    res = OutcomeVerifier.verify("The answer is 42", rule=None)
    assert res.verified is False
    assert res.status == "not_applicable"
    assert res.verification_method == "none"
    assert "No verification rule" in res.verification_message

def test_verifier_numerical_success():
    rule = VerificationRule(type="numerical_tolerance", expected_value=130.0, tolerance=0.01)
    res = OutcomeVerifier.verify("The combined total price is $130.00.", rule=rule)
    assert res.verified is True
    assert res.status == "verified"
    assert res.observed_result == 130.0

def test_verifier_numerical_tolerance():
    rule = VerificationRule(type="numerical_tolerance", expected_value=100.0, tolerance=0.5)
    res = OutcomeVerifier.verify("Result is 99.8 units", rule=rule)
    assert res.verified is True
    assert res.status == "verified"

def test_verifier_numerical_mismatch():
    rule = VerificationRule(type="numerical_tolerance", expected_value=50.0, tolerance=0.1)
    res = OutcomeVerifier.verify("The result is 42.", rule=rule)
    assert res.verified is False
    assert res.status == "failed"
    assert "None of observed numbers" in res.verification_message

def test_verifier_numerical_no_numbers():
    rule = VerificationRule(type="numerical_tolerance", expected_value=10.0)
    res = OutcomeVerifier.verify("There are no digits here.", rule=rule)
    assert res.verified is False
    assert res.status == "failed"
    assert "No numerical values found" in res.verification_message

def test_verifier_field_presence_success():
    rule = VerificationRule(
        type="field_presence",
        required_fields=["Product A", "Product B", "$130"]
    )
    answer = "Found Product A ($45) and Product B ($85), total is $130."
    res = OutcomeVerifier.verify(answer, rule=rule)
    assert res.verified is True
    assert res.status == "verified"

def test_verifier_field_presence_missing():
    rule = VerificationRule(
        type="field_presence",
        required_fields=["Product A", "Product Z"]
    )
    answer = "Found Product A only."
    res = OutcomeVerifier.verify(answer, rule=rule)
    assert res.verified is False
    assert res.status == "failed"
    assert "Product Z" in res.verification_message

def test_verifier_evidence_reference_success():
    rule = VerificationRule(
        type="evidence_reference",
        required_snippets=["DOC-REFUND-001", "30 days"]
    )
    answer = "As stated in DOC-REFUND-001, customers have 30 days to return."
    res = OutcomeVerifier.verify(answer, rule=rule)
    assert res.verified is True
    assert res.status == "verified"

def test_verifier_evidence_reference_missing():
    rule = VerificationRule(
        type="evidence_reference",
        required_snippets=["DOC-SHIPPING-002", "express"]
    )
    answer = "Shipping takes 3-5 days."
    res = OutcomeVerifier.verify(answer, rule=rule)
    assert res.verified is False
    assert res.status == "failed"

def test_verifier_exact_match():
    rule = VerificationRule(type="exact_match", expected_value="42")
    res_ok = OutcomeVerifier.verify("42", rule=rule)
    assert res_ok.verified is True
    assert res_ok.status == "verified"

    res_fail = OutcomeVerifier.verify("43", rule=rule)
    assert res_fail.verified is False
    assert res_fail.status == "failed"
