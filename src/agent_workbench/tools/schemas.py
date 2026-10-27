from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class CalculateInput(StrictModel):
    operation: Literal["add", "subtract", "multiply", "divide"]
    left: float = Field(allow_inf_nan=False, ge=-1e12, le=1e12)
    right: float = Field(allow_inf_nan=False, ge=-1e12, le=1e12)


class CalculateOutput(StrictModel):
    value: float = Field(allow_inf_nan=False)


class ReadInput(StrictModel):
    path: str = Field(min_length=1, max_length=512)


class ReadOutput(StrictModel):
    text: str = Field(max_length=8192)
