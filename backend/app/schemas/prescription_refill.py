from typing import Literal, Optional

from pydantic import BaseModel, Field


class RefillRequestCreate(BaseModel):
    """Patient-initiated refill/renewal request for one of their prescriptions."""

    note: Optional[str] = Field(default=None, max_length=1000)


class RefillRespondRequest(BaseModel):
    """Doctor response to a refill request — approve clones the prescription."""

    action: Literal["approve", "decline"]
    note: Optional[str] = Field(default=None, max_length=1000)
