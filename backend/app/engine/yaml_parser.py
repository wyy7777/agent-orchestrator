from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class StepDefinition:
    name: str
    type: str  # analyze / execute / review / approval / merge
    config: dict[str, Any] = field(default_factory=dict)
    prompt_template: str | None = None
    timeout: int = 300  # 秒


@dataclass
class WorkflowDefinition:
    name: str
    description: str = ""
    steps: list[StepDefinition] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)


VALID_STEP_TYPES = {"analyze", "execute", "review", "approval", "merge", "script"}


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

        steps.append(
            StepDefinition(
                name=step_name,
                type=step_type,
                config=step_data.get("config", {}),
                prompt_template=step_data.get("prompt_template"),
                timeout=step_data.get("timeout", 300),
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

