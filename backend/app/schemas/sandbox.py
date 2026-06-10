from pydantic import BaseModel


class SandboxCreate(BaseModel):
    task_id: str
    image: str = "python:3.12-slim"


class SandboxResponse(BaseModel):
    task_id: str
    container_id: str


class SandboxListResponse(BaseModel):
    items: list[SandboxResponse]
    total: int


class SandboxExecuteRequest(BaseModel):
    command: str
    timeout: int = 60


class SandboxExecuteResponse(BaseModel):
    exit_code: int
    output: str
