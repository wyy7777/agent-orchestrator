from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResponse, get_agent
from app.config import settings
from app.engine.state_machine import StepHandler, register_handler
from app.engine.yaml_parser import StepDefinition


SYSTEM_PROMPT_ANALYZE = """你是一位资深软件工程师。你的任务是分析一个 Issue 或需求，并输出一个结构化的修复方案。

输出格式（严格 JSON）：
{
    "analysis": "问题分析",
    "root_cause": "根因判断",
    "solution": "修复方案描述",
    "files_to_modify": [
        {"path": "文件路径", "change": "改动说明"}
    ],
    "risk_assessment": "风险评估",
    "estimated_effort": "small/medium/large"
}

重要：只输出 JSON，不要输出其他内容。不要写代码，只输出方案。"""


@register_handler("analyze")
class AnalyzeHandler(StepHandler):
    """分析步骤：读取 issue/代码，输出修复方案。"""

    async def execute(
        self, step: StepDefinition, context: dict[str, Any], db: AsyncSession
    ) -> dict[str, Any]:
        provider = step.config.get("provider", settings.DEFAULT_AI_PROVIDER)
        model = step.config.get("model")
        agent = get_agent(provider, model)

        trigger = context.get("trigger_payload", {})
        issue_body = trigger.get("issue_body", trigger.get("input", ""))
        code_context = trigger.get("code_context", "")

        prompt_template = step.prompt_template or (
            "## Issue / 需求\n{issue}\n\n## 相关代码\n{code}"
        )
        user_prompt = prompt_template.format(issue=issue_body, code=code_context)

        response = await agent.run(SYSTEM_PROMPT_ANALYZE, user_prompt)

        return {
            "analysis": response.parsed or {"raw": response.content},
            "tokens_used": response.tokens_used,
            "model": response.model,
        }


SYSTEM_PROMPT_EXECUTE = """你是一位资深软件工程师。你将根据提供的修复方案，生成具体的代码改动。

输入：修复方案（JSON）和相关代码
输出：具体的代码改动（diff 格式）

规则：
1. 只修改方案中列出的文件
2. 保持改动最小化
3. 每个改动说明原因
4. 不要修改方案之外的文件

输出格式（严格 JSON）：
{
    "changes": [
        {
            "file": "文件路径",
            "action": "modify/create/delete",
            "content": "完整的新文件内容",
            "explanation": "改动说明"
        }
    ],
    "summary": "改动总结"
}

重要：只输出 JSON，不要输出其他内容。"""


@register_handler("execute")
class ExecuteHandler(StepHandler):
    """执行步骤：根据方案修改代码。"""

    async def execute(
        self, step: StepDefinition, context: dict[str, Any], db: AsyncSession
    ) -> dict[str, Any]:
        provider = step.config.get("provider", settings.DEFAULT_AI_PROVIDER)
        model = step.config.get("model")
        agent = get_agent(provider, model)

        analysis = context.get("results", {}).get("analyze", {}).get("analysis", {})
        code_context = context.get("trigger_payload", {}).get("code_context", "")

        prompt_template = step.prompt_template or (
            "## 修复方案\n{plan}\n\n## 当前代码\n{code}"
        )
        user_prompt = prompt_template.format(
            plan=str(analysis), code=code_context
        )

        response = await agent.run(SYSTEM_PROMPT_EXECUTE, user_prompt)

        return {
            "changes": response.parsed or {"raw": response.content},
            "tokens_used": response.tokens_used,
            "model": response.model,
        }


SYSTEM_PROMPT_REVIEW = """你是一位严格的代码审查专家。审查以下代码改动（diff）。

审查维度：
1. 严重 bug — 是否引入了新的问题
2. 安全问题 — 是否有注入、越权等漏洞
3. 代码风格 — 是否符合项目规范
4. 目标达成 — 改动是否解决了原始问题
5. 副作用 — 是否影响了不该影响的功能

输出格式（严格 JSON）：
{
    "verdict": "approve/request_changes",
    "score": 0-100,
    "summary": "审查总结",
    "issues": [
        {
            "severity": "critical/warning/info",
            "file": "文件路径",
            "line": "行号或范围",
            "description": "问题描述",
            "suggestion": "修改建议"
        }
    ],
    "positive": ["做得好的方面"]
}

重要：只输出 JSON，不要输出其他内容。"""


@register_handler("review")
class ReviewHandler(StepHandler):
    """审查步骤：审查 diff，生成 review 报告。"""

    async def execute(
        self, step: StepDefinition, context: dict[str, Any], db: AsyncSession
    ) -> dict[str, Any]:
        provider = step.config.get("provider", settings.DEFAULT_AI_PROVIDER)
        model = step.config.get("model")
        agent = get_agent(provider, model)

        execute_result = context.get("results", {}).get("execute", {})
        changes = execute_result.get("changes", {})

        prompt_template = step.prompt_template or "## 代码改动\n{changes}"
        user_prompt = prompt_template.format(changes=str(changes))

        response = await agent.run(SYSTEM_PROMPT_REVIEW, user_prompt)

        return {
            "review": response.parsed or {"raw": response.content},
            "tokens_used": response.tokens_used,
            "model": response.model,
        }
