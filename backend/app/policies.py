from pydantic import BaseModel, ConfigDict, Field, StrictBool


class ReturnFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days_since_delivery: float | None = Field(default=None, ge=0, le=36500, strict=True)
    unopened: StrictBool | None = None
    unused: StrictBool | None = None
    original_packaging: StrictBool | None = None


class Decision(BaseModel):
    eligible: bool | None
    reason: str
    missing: list[str] = []


def cancellation(status: str) -> Decision:
    if status == "Processing":
        return Decision(eligible=True, reason="Eligible because the order is Processing. No cancellation has been performed.")
    note = " You may refuse delivery at the doorstep." if status in ("Shipped", "Out for Delivery") else ""
    return Decision(eligible=False, reason=f"Only Processing orders can be cancelled. This order is {status}.{note}")


def returns(facts: ReturnFacts) -> Decision:
    if facts.unopened is False:
        return Decision(eligible=False, reason="Opened products are not covered by the standard return policy. The 7-day window starts at delivery, not purchase.")
    if facts.days_since_delivery is not None and facts.days_since_delivery > 7:
        return Decision(eligible=False, reason="Standard returns must be requested within 7 days of delivery.")
    if facts.unused is False:
        return Decision(eligible=False, reason="Used products are not covered by the standard return policy.")
    if facts.original_packaging is False:
        return Decision(eligible=False, reason="Original packaging is required for a standard return.")
    missing = [key for key, value in facts.model_dump().items() if value is None]
    if missing:
        return Decision(eligible=None, reason="Ask for the missing delivery and product-condition facts before confirming eligibility.", missing=missing)
    return Decision(eligible=True, reason="Within 7 days of delivery, unopened, unused and in original packaging. Eligible under the standard return policy; no refund has been issued.")

