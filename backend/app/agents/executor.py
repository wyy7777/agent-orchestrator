from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResponse, get_agent
from app.config import settings
from app.engine.state_machine import StepHandler, register_handler
from app.engine.yaml_parser import StepDefinition

logger = logging.getLogger(__name__)


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


@register_handler("merge")
class MergeHandler(StepHandler):
    """合并步骤：将代码改动提交到 GitHub 并创建 PR。"""

    async def execute(
        self, step: StepDefinition, context: dict[str, Any], db: AsyncSession
    ) -> dict[str, Any]:
        from app.integrations.github import GitHubClient, parse_repo_url

        git_repo = context.get("git_repo", "")
        git_branch = context.get("git_branch", "main")

        if not git_repo:
            raise ValueError("merge 步骤需要设置 git_repo 参数")

        owner, repo = parse_repo_url(git_repo)
        client = GitHubClient()

        # 获取 execute 步骤的改动
        execute_result = context.get("results", {}).get("execute", {})
        changes_data = execute_result.get("changes", {})
        changes = changes_data.get("changes", []) if isinstance(changes_data, dict) else []

        # 生成 PR 分支名
        task_id = context.get("task_id", "unknown")[:8]
        pr_branch = f"agent-orch/{task_id}"

        # 获取 main 分支的 SHA
        main_branch = await client.get_branch(owner, repo, git_branch)
        main_sha = main_branch["commit"]["sha"]

        # 创建新分支
        await client.create_branch(owner, repo, pr_branch, main_sha)

        # 提交每个文件的改动
        committed_files = []
        for change in changes:
            file_path = change.get("file", "")
            content = change.get("content", "")
            action = change.get("action", "modify")

            if not file_path or action == "delete":
                continue

            # 获取文件当前 SHA（如果存在）
            file_sha = None
            try:
                existing = await client.get_file(owner, repo, file_path, ref=pr_branch)
                file_sha = existing.get("sha")
            except RuntimeError:
                pass  # 文件不存在，创建新文件

            await client.create_or_update_file(
                owner=owner,
                repo=repo,
                path=file_path,
                content=content,
                message=f"[Agent Orchestrator] {change.get('explanation', f'Update {file_path}')}",
                branch=pr_branch,
                sha=file_sha,
            )
            committed_files.append(file_path)

        # 创建 PR
        # 汇总分析结果作为 PR body
        analysis = context.get("results", {}).get("analyze", {}).get("analysis", {})
        review = context.get("results", {}).get("review", {}).get("review", {})

        pr_body_parts = ["## 🤖 由 Agent Orchestrator 自动生成\n"]
        if isinstance(analysis, dict):
            pr_body_parts.append(f"### 分析\n{analysis.get('analysis', '')}")
            pr_body_parts.append(f"### 根因\n{analysis.get('root_cause', '')}")
            pr_body_parts.append(f"### 方案\n{analysis.get('solution', '')}")
        if isinstance(review, dict):
            pr_body_parts.append(f"### 审查结果\n{review.get('summary', '')}")
            score = review.get("score", "")
            if score:
                pr_body_parts.append(f"**评分**: {score}/100")

        pr_body = "\n\n".join(pr_body_parts)
        pr_title = f"[Agent] {context.get('task_id', 'Task')[:8]}: 自动修复"

        pr = await client.create_pull_request(
            owner=owner,
            repo=repo,
            title=pr_title,
            head=pr_branch,
            base=git_branch,
            body=pr_body,
        )

        pr_url = pr["html_url"]
        logger.info(f"PR 已创建: {pr_url}")

        return {
            "pr_url": pr_url,
            "pr_number": pr["number"],
            "pr_branch": pr_branch,
            "committed_files": committed_files,
        }
