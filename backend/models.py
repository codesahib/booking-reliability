from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = str


class Event(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    event_id: Identifier = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    reservation_id: Identifier = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    type: Literal['authorized', 'payment_succeeded', 'refund_succeeded', 'refund_failed']
    amount_cents: int = Field(strict=True, gt=0, le=10000000)


class Booking(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    campsite_id: str = Field(min_length=1, max_length=80)
    guest_label: str = Field(min_length=1, max_length=60)
    arrival: date
    departure: date
    idempotency_key: str = Field(min_length=8, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')

    @model_validator(mode='after')
    def check_stay(self):
        nights = (self.departure - self.arrival).days
        if not 1 <= nights <= 30:
            raise ValueError('Stay must be between 1 and 30 nights; departure is exclusive')
        return self
