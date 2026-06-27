"""Agent 输出的 Pydantic 校验模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FileChange(BaseModel):
    """文件变更描述。"""
    file: str
    action: Literal["modify", "create", "delete"]
    content: str = ""
    explanation: str = ""


class AnalysisOutput(BaseModel):
    """分析步骤输出。"""
    analysis: str = Field(description="问题分析")
    root_cause: str = Field(description="根因判断", default="")
    solution: str = Field(description="修复方案描述", default="")
    files_to_modify: list[FileChange] = Field(default_factory=list)
    risk_assessment: str = Field(default="")
    estimated_effort: Literal["small", "medium", "large"] = "medium"


class ExecuteOutput(BaseModel):
    """执行步骤输出。"""
    changes: list[FileChange] = Field(default_factory=list)
    summary: str = Field(default="")
    written_files: list[str] = Field(default_factory=list)
    pr_body: str = ""


class ReviewIssue(BaseModel):
    """审查问题。"""
    severity: Literal["critical", "warning", "info"] = "warning"
    file: str = ""
    line: str = ""
    description: str = ""
    suggestion: str = ""


class ReviewOutput(BaseModel):
    """审查步骤输出。"""
    verdict: Literal["approve", "request_changes"] = "approve"
    score: int = Field(ge=0, le=100, default=50)
    summary: str = ""
    issues: list[ReviewIssue] = Field(default_factory=list)
    positive: list[str] = Field(default_factory=list)


def validate_agent_output(content: str, schema_class: type[BaseModel]) -> dict | None:
    """
    尝试用 Pydantic 校验 LLM 输出。

    返回:
        校验通过返回 dict，失败返回 None（fallback 到原始解析）
    """
    try:
        import json
        data = json.loads(content)
        validated = schema_class.model_validate(data)
        return validated.model_dump()
    except Exception:
        return None
