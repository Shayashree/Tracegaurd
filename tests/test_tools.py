"""Unit tests for initial tool set: Calculator, Data Lookup, and Document Search."""
import pytest
from pathlib import Path
from backend.tools.calculator import CalculatorTool
from backend.tools.data_lookup import DataLookupTool
from backend.tools.document_search import DocumentSearchTool

# ---------------------------------------------------------------------------
# Calculator Tests
# ---------------------------------------------------------------------------

def test_calculator_addition():
    tool = CalculatorTool()
    res = tool.execute({"operation": "add", "a": 10, "b": 25})
    assert res.success is True
    assert res.data["result"] == 35
    assert res.error is None
    assert res.duration_ms is not None

def test_calculator_subtraction():
    tool = CalculatorTool()
    res = tool.execute({"operation": "-", "a": 50, "b": 17.5})
    assert res.success is True
    assert res.data["result"] == 32.5

def test_calculator_multiplication():
    tool = CalculatorTool()
    res = tool.execute({"operation": "multiply", "a": 6, "b": 7})
    assert res.success is True
    assert res.data["result"] == 42

def test_calculator_division():
    tool = CalculatorTool()
    res = tool.execute({"operation": "divide", "a": 100, "b": 4})
    assert res.success is True
    assert res.data["result"] == 25

def test_calculator_division_by_zero():
    tool = CalculatorTool()
    res = tool.execute({"operation": "divide", "a": 10, "b": 0})
    assert res.success is False
    assert res.data is None
    assert "Cannot divide by zero" in res.error

def test_calculator_invalid_operation():
    tool = CalculatorTool()
    res = tool.execute({"operation": "modulus", "a": 10, "b": 2})
    assert res.success is False
    assert "Invalid arguments" in res.error

def test_calculator_invalid_operand_type():
    tool = CalculatorTool()
    res = tool.execute({"operation": "add", "a": "ten", "b": 5})
    assert res.success is False
    assert "Invalid arguments" in res.error

# ---------------------------------------------------------------------------
# Data Lookup Tests
# ---------------------------------------------------------------------------

def test_data_lookup_by_query():
    tool = DataLookupTool()
    res = tool.execute({"query": "Product A"})
    assert res.success is True
    assert res.data["count"] >= 1
    names = [m["name"] for m in res.data["matches"]]
    assert "Product A" in names

def test_data_lookup_multi_query():
    tool = DataLookupTool()
    res = tool.execute({"query": "Product A and Product B"})
    assert res.success is True
    assert res.data["count"] >= 2
    names = [m["name"] for m in res.data["matches"]]
    assert "Product A" in names
    assert "Product B" in names

def test_data_lookup_by_exact_id():
    tool = DataLookupTool()
    res = tool.execute({"product_id": "prod_001"})
    assert res.success is True
    assert res.data["count"] == 1
    assert res.data["matches"][0]["id"] == "prod_001"
    assert res.data["matches"][0]["price"] == 45.0

def test_data_lookup_by_category():
    tool = DataLookupTool()
    res = tool.execute({"category": "Accessories"})
    assert res.success is True
    assert res.data["count"] >= 1
    for m in res.data["matches"]:
        assert m["category"].lower() == "accessories"

def test_data_lookup_no_matches():
    tool = DataLookupTool()
    res = tool.execute({"query": "NonExistentGadgetXYZ999"})
    assert res.success is True
    assert res.data["count"] == 0
    assert "No matching records found" in res.data["message"]

def test_data_lookup_missing_file(tmp_path):
    tool = DataLookupTool(data_path=tmp_path / "nonexistent.json")
    res = tool.execute({"query": "Product A"})
    assert res.success is True
    assert res.data["count"] == 0
    assert "file not found" in res.data["message"]

# ---------------------------------------------------------------------------
# Document Search Tests
# ---------------------------------------------------------------------------

def test_document_search_success():
    tool = DocumentSearchTool()
    res = tool.execute({"query": "refund policy 30 days"})
    assert res.success is True
    assert res.data["count"] >= 1
    match = res.data["matches"][0]
    assert "DOC-REFUND-001" in match["document_id"]
    assert "30-Day Window" in match["snippet"] or "refund" in match["snippet"].lower()

def test_document_search_warranty():
    tool = DocumentSearchTool()
    res = tool.execute({"query": "hardware warranty coverage"})
    assert res.success is True
    assert res.data["count"] >= 1
    doc_ids = [m["document_id"] for m in res.data["matches"]]
    assert any("DOC-WARRANTY" in did for did in doc_ids)

def test_document_search_no_match():
    tool = DocumentSearchTool()
    res = tool.execute({"query": "quantum teleporter flux capacitor"})
    assert res.success is True
    assert res.data["count"] == 0
    assert "No relevant evidence found" in res.data["message"]

def test_document_search_empty_query():
    tool = DocumentSearchTool()
    res = tool.execute({"query": ""})
    assert res.success is False
    assert "Invalid arguments" in res.error

def test_document_search_missing_dir(tmp_path):
    tool = DocumentSearchTool(docs_dir=tmp_path / "empty_dir")
    res = tool.execute({"query": "refund"})
    assert res.success is True
    assert res.data["count"] == 0
    assert "does not exist" in res.data["message"]
