from __future__ import annotations

import logging
from datetime import datetime
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
    """执行步骤：AI 生成代码改动 → 写入文件（如配置了 GitHub token）。"""

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
        changes = response.parsed or {"raw": response.content}

        # 如果配置了 GitHub token 和仓库，则实际写入文件
        git_repo = context.get("git_repo")
        git_branch = context.get("sandbox_branch") or context.get("git_branch")
        written_files = []
        pr_body_lines = []

        if git_repo and settings.GITHUB_TOKEN and git_branch:
            try:
                from app.integrations.github import _parse_repo, write_file

                owner, repo = _parse_repo(git_repo)

                change_list = changes.get("changes", [])
                if isinstance(change_list, list):
                    for change in change_list:
                        file_path = change.get("file")
                        content = change.get("content")
                        explanation = change.get("explanation", "")
                        if file_path and content:
                            await write_file(
                                owner, repo, git_branch,
                                file_path=file_path,
                                content=content,
                                commit_message=f"Agent: {explanation}" if explanation else f"Agent fix: {file_path}",
                            )
                            written_files.append(file_path)
                            pr_body_lines.append(f"- **{file_path}**: {explanation}")

                logger.info(
                    f"已写入 {len(written_files)} 个文件到 {git_repo}/{git_branch}"
                )
            except Exception as e:
                logger.warning(f"文件写入失败（GitHub API）: {e}")

        return {
            "changes": changes,
            "written_files": written_files,
            "pr_body": "\n".join(pr_body_lines) if pr_body_lines else str(changes),
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


# ── merge 处理器：创建 GitHub PR ──


@register_handler("merge")
class MergeHandler(StepHandler):
    """合并步骤：创建 GitHub Pull Request。"""

    async def execute(
        self, step: StepDefinition, context: dict[str, Any], db: AsyncSession
    ) -> dict[str, Any]:
        git_repo = context.get("git_repo")
        if not git_repo:
            return {
                "status": "skipped",
                "reason": "未配置 git_repo，跳过 PR 创建",
                "pr_url": None,
            }

        if not settings.GITHUB_TOKEN:
            return {
                "status": "skipped",
                "reason": "未配置 GITHUB_TOKEN，跳过 PR 创建",
                "pr_url": None,
            }

        try:
            from app.integrations.github import _parse_repo, create_pr

            owner, repo_name = _parse_repo(git_repo)
            head_branch = context.get("sandbox_branch") or context.get("git_branch")

            # 收集 PR 标题和正文
            analyze_result = context.get("results", {}).get("analyze", {})
            analysis = analyze_result.get("analysis", {})
            issue_title = analysis.get("analysis", "Agent 自动修复")[:80]

            review_result = context.get("results", {}).get("review_code", {})
            review = review_result.get("review", {})

            execute_result = context.get("results", {}).get("execute", {})
            pr_body = execute_result.get("pr_body", "")
            written_files = execute_result.get("written_files", [])

            body_parts = ["## 🤖 Agent 自动修复\n"]
            if written_files:
                body_parts.append("### 修改的文件")
                for f in written_files:
                    body_parts.append(f"- `{f}`")
                body_parts.append("")

            body_parts.append("### 改动说明")
            body_parts.append(pr_body)

            if review:
                body_parts.append("\n### AI 审查结果")
                body_parts.append(f"- 评分: {review.get('score', 'N/A')}")
                body_parts.append(f"- 结论: {review.get('verdict', 'N/A')}")
                summary = review.get("summary", "")
                if summary:
                    body_parts.append(f"- {summary}")

            result = await create_pr(
                owner=owner,
                repo=repo_name,
                head_branch=head_branch,
                base_branch=context.get("git_branch", "main"),
                title=issue_title,
                body="\n".join(body_parts),
            )

            return {
                "status": "created",
                "pr_url": result["html_url"],
                "pr_number": result["number"],
            }

        except Exception as e:
            logger.error(f"创建 PR 失败: {e}")
            return {
                "status": "failed",
                "reason": str(e),
                "pr_url": None,
            }
