
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    prompt: str = Field(
        min_length=5,
        max_length=5000
    )


class GenerateResponse(BaseModel):
    success: bool
    message: str
    files: dict[str, str]


class EditRequest(BaseModel):
    prompt: str = Field(
        min_length=3,
        max_length=3000,
    )


class RuntimeErrorReport(BaseModel):
    type: str = Field(default="error", max_length=100)
    message: str = Field(min_length=1, max_length=4000)
    stack: str = Field(default="", max_length=8000)
    filename: str = Field(default="", max_length=2000)
    line: int = Field(default=0, ge=0)
    column: int = Field(default=0, ge=0)
    timestamp: int | None = None


class AutoDebugRequest(BaseModel):
    max_attempts: int = Field(default=3, ge=1, le=3)

class TestProjectRequest(BaseModel):
    preview_url: str | None = Field(
        default=None,
        max_length=500,
    )
    run_browser: bool = True

class ProjectPlanRequest(BaseModel):
    prompt: str = Field(
        min_length=3,
        max_length=4000,
    )