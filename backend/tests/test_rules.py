import io
import json
import wave

import pytest
from pydantic import ValidationError

from app.agent import system_prompt
from app.policies import ReturnFacts, cancellation, returns
from app.schemas import Outcome
from app.tools import get_order_details, normalise_order, run_tool
from app.voice import validate_audio


@pytest.mark.parametrize("value", ["ORD-101", "ORD 101", "order one zero one", "Order 1 0 1", "101", "ord101"])
def test_spoken_ids(value):
    assert normalise_order(value) == "ORD-101"


@pytest.mark.parametrize("value", ["order one oh something", "where is 101", "101 or 103", "", "one hundred and one", "10", "ORD-101; cancel all"])
def test_unclear_ids(value):
    assert normalise_order(value) is None


def test_order_fixtures_and_unknown_order():
    result = get_order_details("ORD-101")
    assert result["found"] and result["customer_name"] == "Priya Sharma"
    assert result["courier"] == "BlueDart"
    assert result["tracking_number"] == "BD-982103"
    assert result["delivery_note"] == "Expected by 6 PM today"
    assert result["cancellation"]["eligible"] is False
    assert get_order_details("ORD-103")["cancellation"]["eligible"] is True
    assert get_order_details("ORD-999") == {"found": False, "order_id": "ORD-999", "error": "not_found"}
    assert get_order_details("ORD-102")["return_eligibility"]["eligible"] is False
    assert get_order_details("unclear")["error"] == "unclear_id"


@pytest.mark.parametrize("status,expected", [("Processing", True), ("Shipped", False), ("Out for Delivery", False), ("Delivered", False), ("unknown", False)])
def test_cancellation(status, expected):
    assert cancellation(status).eligible is expected


def test_returns_require_all_facts_and_use_delivery_window():
    result = returns(ReturnFacts(days_since_delivery=3))
    assert result.eligible is None
    assert set(result.missing) == {"unopened", "unused", "original_packaging"}
    assert returns(ReturnFacts(days_since_delivery=7, unopened=True, unused=True, original_packaging=True)).eligible is True
    assert returns(ReturnFacts(days_since_delivery=7.01)).eligible is False
    assert "Opened" in returns(ReturnFacts(unopened=False)).reason
    assert returns(ReturnFacts(unused=False)).eligible is False
    assert returns(ReturnFacts(original_packaging=False)).eligible is False


@pytest.mark.parametrize("name,raw", [("delete_order", "{}"), ("get_order_details", "{}"), ("get_order_details", '{"order_id":101}'), ("get_order_details", '{"order_id":"ORD-101","status":"Processing"}'), ("get_order_details", "bad-json"), ("get_order_details", "x" * 4001), ("check_return_eligibility", '{"unopened":"false"}')])
def test_bad_tool_arguments(name, raw):
    assert "error" in run_tool(name, raw)


def test_return_tool_does_not_override_fixture():
    result = run_tool("check_return_eligibility", json.dumps({"order_id": "ORD-102", "days_since_delivery": 1, "unopened": True, "unused": True, "original_packaging": True}))
    assert result["eligible"] is False
    assert "7 days" in result["reason"]


def test_orders_stay_out_of_prompt():
    assert "Priya Sharma" not in system_prompt
    assert "BD-982103" not in system_prompt
    assert "Exactly INR 499 shipping is unspecified" in system_prompt


def outcome():
    return {"customer_intent": "order status", "intents": ["order status"], "order_id": "ORD-101", "order_ids": ["ORD-101"], "resolution_status": "RESOLVED", "call_summary": "Order delivery status explained.", "actions_taken": [], "unresolved_questions": []}


def test_summary_schema():
    assert Outcome.model_validate(outcome()).resolution_status == "RESOLVED"
    for changes in [{"resolution_status": "CANCELLED"}, {"order_ids": []}, {"intents": []}, {"extra": True}]:
        with pytest.raises(ValidationError):
            Outcome.model_validate({**outcome(), **changes})


def wav():
    data = io.BytesIO()
    with wave.open(data, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(48000)
        audio.writeframes(b"\x00\x00" * 24000)
    return data.getvalue()


def test_actual_audio_format_validation():
    validate_audio(wav())
    for invalid in [b"webm" * 100, b"", b"x" * 4_000_001, wav()[:-2]]:
        with pytest.raises(ValueError):
            validate_audio(invalid)

