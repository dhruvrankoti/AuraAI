import pytest
from services.search_planner import SearchPlanner

def test_local_parse_receipts():
    query = "Show me receipts from 2025"
    plan = SearchPlanner._local_parse(query)
    
    assert plan.categories == ["receipt"]
    assert plan.date_start == "2025-01-01T00:00:00"
    assert plan.date_end == "2025-12-31T23:59:59"
    assert plan.semantic_query == query

def test_local_parse_travel_location_person():
    query = "Find travel photos in Goa with Rahul"
    plan = SearchPlanner._local_parse(query)
    
    assert "travel" in plan.categories
    assert plan.location == "Goa"
    assert "Rahul" in plan.person_names

def test_local_parse_ocr_prescription():
    query = "find prescriptions containing \"Paracetamol\""
    plan = SearchPlanner._local_parse(query)
    
    assert plan.categories == ["prescription"]
    assert plan.ocr_query == "Paracetamol"
