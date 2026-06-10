from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

from app.config import settings


@dataclass
class StepDefinition:
    name: str
    type: str  # analyze / execute / review / approval / merge / subtask / loop
    config: dict[str, Any] = field(default_factory=dict)
    prompt_template: str | None = None
    timeout: int = field(default_factory=lambda: settings.DEFAULT_STEP_TIMEOUT)
    parallel: bool = False
    steps: list["StepDefinition"] = field(default_factory=list)  # loop 子步骤
    condition: str | None = None  # 条件表达式，如 "{result.score} > 80"
    else_steps: list["StepDefinition"] = field(default_factory=list)  # else 分支步骤
    loop_items: str | None = None  # 循环数据源 key
    max_iterations: int = field(default_factory=lambda: settings.DEFAULT_MAX_ITERATIONS)
    subtask_workflow: str | None = None  # 子工作流 ID


@dataclass
class WorkflowDefinition:
    name: str
    description: str = ""
    steps: list[StepDefinition] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)


VALID_STEP_TYPES = {"analyze", "execute", "review", "approval", "merge", "script", "subtask", "loop", "condition"}


def parse_workflow_yaml(yaml_str: str) -> WorkflowDefinition:
    """解析 YAML 工作流定义，返回结构化的 WorkflowDefinition。"""
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        raise ValueError(f"YAML 解析错误: {e}")

    if not isinstance(data, dict):
        raise ValueError("工作流 YAML 必须是一个字典")

    name = data.get("name")
    if not name:
        raise ValueError("工作流必须定义 name 字段")

    steps_data = data.get("steps")
    if not steps_data or not isinstance(steps_data, list):
        raise ValueError("工作流必须定义 steps 列表，且至少有一个步骤")

    steps: list[StepDefinition] = []
    for i, step_data in enumerate(steps_data):
        if not isinstance(step_data, dict):
            raise ValueError(f"步骤 {i} 必须是字典")

        step_name = step_data.get("name", f"step_{i}")
        step_type = step_data.get("type")
        if not step_type:
            raise ValueError(f"步骤 '{step_name}' 必须定义 type 字段")
        if step_type not in VALID_STEP_TYPES:
            raise ValueError(
                f"步骤 '{step_name}' 的 type '{step_type}' 无效，"
                f"支持的类型: {', '.join(sorted(VALID_STEP_TYPES))}"
            )

        # 解析 loop 类型的子步骤
        sub_steps: list[StepDefinition] = []
        if step_type == "loop" and "steps" in step_data:
            for j, sub_data in enumerate(step_data["steps"]):
                if not isinstance(sub_data, dict):
                    raise ValueError(f"步骤 '{step_name}' 的子步骤 {j} 必须是字典")
                sub_name = sub_data.get("name", f"{step_name}_sub_{j}")
                sub_type = sub_data.get("type")
                if not sub_type:
                    raise ValueError(f"子步骤 '{sub_name}' 必须定义 type 字段")
                sub_steps.append(
                    StepDefinition(
                        name=sub_name,
                        type=sub_type,
                        config=sub_data.get("config", {}),
                        prompt_template=sub_data.get("prompt_template"),
                        timeout=sub_data.get("timeout", settings.DEFAULT_STEP_TIMEOUT),
                        condition=sub_data.get("condition"),
                        loop_items=sub_data.get("loop_items"),
                        max_iterations=sub_data.get("max_iterations", settings.DEFAULT_MAX_ITERATIONS),
                        subtask_workflow=sub_data.get("subtask_workflow"),
                    )
                )

        # 解析 else 分支步骤
        else_steps: list[StepDefinition] = []
        if "else" in step_data:
            else_data = step_data["else"]
            if isinstance(else_data, list):
                for j, sub_data in enumerate(else_data):
                    if not isinstance(sub_data, dict):
                        raise ValueError(f"步骤 '{step_name}' 的 else 分支步骤 {j} 必须是字典")
                    sub_name = sub_data.get("name", f"{step_name}_else_{j}")
                    sub_type = sub_data.get("type")
                    if not sub_type:
                        raise ValueError(f"else 分支步骤 '{sub_name}' 必须定义 type 字段")
                    else_steps.append(
                        StepDefinition(
                            name=sub_name,
                            type=sub_type,
                            config=sub_data.get("config", {}),
                            prompt_template=sub_data.get("prompt_template"),
                            timeout=sub_data.get("timeout", settings.DEFAULT_STEP_TIMEOUT),
                            condition=sub_data.get("condition"),
                        )
                    )

        steps.append(
            StepDefinition(
                name=step_name,
                type=step_type,
                config=step_data.get("config", {}),
                prompt_template=step_data.get("prompt_template"),
                timeout=step_data.get("timeout", settings.DEFAULT_STEP_TIMEOUT),
                parallel=step_data.get("parallel", False),
                steps=sub_steps,
                condition=step_data.get("condition"),
                else_steps=else_steps,
                loop_items=step_data.get("loop_items"),
                max_iterations=step_data.get("max_iterations", settings.DEFAULT_MAX_ITERATIONS),
                subtask_workflow=step_data.get("subtask_workflow"),
            )
        )

    return WorkflowDefinition(
        name=name,
        description=data.get("description", ""),
        steps=steps,
        settings=data.get("settings", {}),
    )


def validate_workflow_yaml(yaml_str: str) -> tuple[bool, str | None]:
    """验证 YAML 工作流定义是否合法，返回 (是否合法, 错误信息)。"""
    try:
        parse_workflow_yaml(yaml_str)
        return True, None
    except ValueError as e:
        return False, str(e)


EXAMPLE_YAML = """\
# Agent Orchestrator 示例工作流
# 代码审查助手 - 自动分析代码问题并生成修复建议

name: 代码审查助手
description: 分析代码中的安全漏洞和性能问题，生成修复建议

settings:
  max_tokens: 4000
  timeout: 600

steps:
  - name: 代码分析
    type: analyze
    timeout: 120
    config:
      provider: deepseek
      model: deepseek-chat
    prompt_template: |
      请分析以下代码，找出安全漏洞、性能问题和代码质量问题。
      返回 JSON 格式: {"issues": [...], "severity": "high/medium/low"}

  - name: 审查报告
    type: review
    timeout: 120
    config:
      provider: deepseek
      model: deepseek-chat
    prompt_template: |
      基于分析结果，生成详细的代码审查报告。
      包含：问题描述、影响范围、修复建议、优先级。
"""

