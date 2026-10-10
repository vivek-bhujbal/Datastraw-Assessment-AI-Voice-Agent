from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Entry(BaseModel):
    speaker: Literal["Customer", "Aria"]
    text: str
    timestamp: str
    turn_id: str
    playback: Literal["played", "interrupted"] | None = None


class Outcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_intent: str | None = Field(description="Primary intent copied exactly from an entry in intents, or null.")
    intents: list[str]
    order_id: str | None = Field(description="Primary order ID copied exactly from an entry in order_ids, or null.")
    order_ids: list[str]
    resolution_status: Literal["RESOLVED", "UNRESOLVED", "PARTIALLY_RESOLVED", "NO_CONVERSATION"]
    call_summary: str
    actions_taken: list[str]
    unresolved_questions: list[str]

    @model_validator(mode="after")
    def consistent(self):
        if self.order_id and self.order_id not in self.order_ids:
            raise ValueError("Primary order must be in order_ids")
        if self.customer_intent and self.customer_intent not in self.intents:
            raise ValueError("Primary intent must be in intents")
        return self

