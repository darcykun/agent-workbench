from pydantic import BaseModel, ConfigDict, Field


class Budgets(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    max_steps: int = Field(default=8, ge=1, le=100)
    timeout_seconds: float = Field(default=15, gt=0, le=300)
    max_output_tokens: int = Field(default=1024, ge=1, le=32768)
    max_result_bytes: int = Field(default=16384, ge=128, le=1048576)
