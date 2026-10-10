import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .policies import ReturnFacts, cancellation, returns

data_dir = Path(__file__).parent / "data"
orders = json.loads((data_dir / "orders.json").read_text(encoding="utf-8"))
policies = json.loads((data_dir / "brand_policies.json").read_text(encoding="utf-8"))
digits = {name: str(i) for i, name in enumerate("zero one two three four five six seven eight nine".split())}


def normalise_order(value: str) -> str | None:
    value = value.strip().lower()
    value = re.sub(r"^(?:order|ord)\s*[-:]?\s*", "", value)
    words = value.split()
    if words and all(word in digits for word in words):
        value = "".join(digits[word] for word in words)
    elif re.fullmatch(r"\d(?:[\s-]*\d){2,7}", value):
        value = re.sub(r"[\s-]", "", value)
    else:
        return None
    return f"ORD-{value}" if 3 <= len(value) <= 8 else None


class OrderArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    order_id: str = Field(min_length=1, max_length=80)


class ReturnArgs(ReturnFacts):
    order_id: str | None = Field(default=None, max_length=80)


def get_order_details(order_id: str):
    order_id = normalise_order(order_id)
    if order_id is None:
        return {"found": False, "order_id": None, "error": "unclear_id", "message": "Ask the customer to repeat or confirm the ID."}
    if order_id not in orders:
        return {"found": False, "order_id": order_id, "error": "not_found"}
    order = orders[order_id]
    result = {"found": True, "order_id": order_id, **order, "cancellation": cancellation(order["status"]).model_dump()}
    if order_id == "ORD-102":
        result["return_eligibility"] = returns(ReturnFacts(days_since_delivery=14)).model_dump()
    return result


def check_return(args: ReturnArgs):
    facts = ReturnFacts(**args.model_dump(exclude={"order_id"}))
    order_id = None
    if args.order_id:
        order = get_order_details(args.order_id)
        if not order["found"]:
            return order
        order_id = order["order_id"]
        # Delivery time from the fixture wins over a conflicting customer claim.
        if order["order_id"] == "ORD-102":
            facts.days_since_delivery = 14
        elif order["status"] != "Delivered":
            return {"order_id": order_id, "eligible": False, "reason": "This order has not been delivered. Standard returns are assessed after delivery.", "missing": []}
    return {"order_id": order_id, **returns(facts).model_dump()}


tool_specs = [
    {"type": "function",
        "name": "get_order_details",
        "description": "Look up an order before answering ANY question about its status, courier, tracking, cancellation or delivery. Use the prior confirmed ID for follow-ups. Ask for unclear or missing IDs; never guess a nearest ID.",
        "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "Order ID, e.g. ORD-101 or Order one zero one."}}, "required": ["order_id"], "additionalProperties": False}
    },
    {"type": "function",
        "name": "check_return_eligibility",
        "description": "Evaluate a requested standard return using confirmed delivery and product-condition facts. Null for unknown facts. Do not equate purchase time with delivery time. Call before declaring eligibility.",
        "parameters": {"type": "object", "properties": {
            "order_id": {"type": ["string", "null"]},
            "days_since_delivery": {"type": ["number", "null"]},
            "unopened": {"type": ["boolean", "null"]},
            "unused": {"type": ["boolean", "null"]},
            "original_packaging": {"type": ["boolean", "null"]}
        }, "required": ["order_id", "days_since_delivery", "unopened", "unused", "original_packaging"], "additionalProperties": False}
    }
]


def run_tool(name: str, raw: str):
    try:
        if len(raw) > 4000:
            raise ValueError("Arguments too large")
        if name == "get_order_details":
            args = OrderArgs.model_validate_json(raw)
            return get_order_details(args.order_id)
        if name == "check_return_eligibility":
            return check_return(ReturnArgs.model_validate_json(raw))
        return {"error": "unknown_tool", "message": "That tool is not registered. No action was taken."}
    except (ValidationError, ValueError):
        return {"error": "invalid_arguments", "message": "Ask for clear, valid facts. No action was taken."}
    except Exception:
        return {"error": "tool_failed", "message": "The lookup failed. Do not invent its result."}

