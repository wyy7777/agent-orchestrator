from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResponse, get_agent, _get_friendly_error
from app.agents.schemas import AnalysisOutput, ExecuteOutput, ReviewOutput, validate_agent_output
from app.config import settings
from app.engine.state_machine import StepHandler, register_handler
from app.engine.types import StepResult
from app.engine.yaml_parser import StepDefinition
from app.models.agent_config import AgentConfig

logger = logging.getLogger(__name__)


async def _get_agent_from_config(step: StepDefinition, db: AsyncSession) -> tuple[str, str | None]:
    """从步骤配置中获取 Agent 的 provider 和 model。

    优先使用 config.agent（已注册的 Agent 名称），否则使用 config.provider。
    """
    agent_name = step.config.get("agent")
    if agent_name and db:
        from sqlalchemy import select
        result = await db.execute(select(AgentConfig).where(
            AgentConfig.name == agent_name,
            AgentConfig.enabled == True,  # noqa: E712
        ))
        agent_config = result.scalar_one_or_none()
        if agent_config:
            return agent_config.provider, agent_config.model

    # 回退到 config.provider
    return step.config.get("provider", settings.DEFAULT_AI_PROVIDER), step.config.get("model")


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
    ) -> StepResult:
        provider, model = await _get_agent_from_config(step, db)
        agent = get_agent(provider, model)

        trigger = context.get("trigger_payload", {})
        issue_body = trigger.get("issue_body", trigger.get("input", ""))
        code_context = trigger.get("code_context", "")

        prompt_template = step.prompt_template or (
            "## Issue / 需求\n{issue}\n\n## 相关代码\n{code}"
        )
        user_prompt = prompt_template.format(issue=issue_body, code=code_context)

        try:
            response = await agent.run(SYSTEM_PROMPT_ANALYZE, user_prompt)
            validated = validate_agent_output(response.content, AnalysisOutput)
            analysis = validated if validated else (response.parsed or {"raw": response.content})

            return StepResult(
                status="completed",
                output={"analysis": analysis},
                tokens_used=response.tokens_used,
                model=response.model,
            )
        except Exception as e:
            logger.warning(f"AI 分析失败，尝试规则回退: {e}")
            fallback = _analyze_fallback(issue_body, code_context)
            if fallback:
                return StepResult(
                    status="completed",
                    output={"analysis": fallback, "fallback": True},
                    error=str(e),
                )
            return StepResult(status="failed", error=_get_friendly_error(e))



def _analyze_fallback(issue_body: str, code_context: str) -> dict[str, Any] | None:
    """规则引擎回退：当 AI 不可用时，基于关键词扫描。"""
    import re

    findings = []
    files_to_modify = []

    # 扫描代码中的常见问题
    if code_context:
        patterns = [
            (r"\bTODO\b", "info", "存在 TODO 注释"),
            (r"\bFIXME\b", "warning", "存在 FIXME 注释"),
            (r"\bHACK\b", "warning", "存在 HACK 注释"),
            (r"\bXXX\b", "info", "存在 XXX 标记"),
            (r"(?:password|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]", "critical", "疑似硬编码密钥"),
            (r"\beval\s*\(", "critical", "使用了 eval()，存在注入风险"),
            (r"console\.log\s*\(", "info", "遗留 console.log 调试语句"),
            (r"\bprint\s*\(", "info", "遗留 print 调试语句"),
            (r"except\s*:", "warning", "裸 except 捕获所有异常"),
            (r"SELECT\s+\*\s+FROM", "warning", "使用 SELECT * 查询"),
        ]

        for pattern, severity, desc in patterns:
            matches = re.findall(pattern, code_context, re.IGNORECASE)
            if matches:
                findings.append({
                    "severity": severity,
                    "description": f"{desc} (发现 {len(matches)} 处)",
                    "suggestion": f"建议修复: {desc}",
                })

    if issue_body:
        # 简单关键词分析
        keywords = {
            "bug": "修复缺陷",
            "error": "修复错误",
            "crash": "修复崩溃",
            "performance": "性能优化",
            "security": "安全加固",
            "refactor": "代码重构",
            "feature": "新功能实现",
        }
        for kw, action in keywords.items():
            if kw.lower() in issue_body.lower():
                findings.append({
                    "severity": "info",
                    "description": f"需求关键词: {kw}",
                    "suggestion": action,
                })

    if not findings:
        return None

    return {
        "analysis": f"[规则引擎回退] 扫描到 {len(findings)} 个问题",
        "root_cause": "基于关键词的静态分析（AI 不可用）",
        "solution": "请参考下方 findings 手动修复",
        "files_to_modify": files_to_modify,
        "findings": findings,
        "risk_assessment": "低（规则引擎回退，仅做基本检查）",
        "estimated_effort": "small",
        "fallback": True,
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
    ) -> StepResult:
        provider, model = await _get_agent_from_config(step, db)
        agent = get_agent(provider, model)

        # 从 context 中查找分析结果：优先按步骤名 "analyze" 查找，
        # 否则在所有结果中查找含 "analysis" 键的步骤输出（兼容自定义步骤名）
        analysis = context.get("results", {}).get("analyze", {}).get("analysis", {})
        if not analysis:
            for step_name, result in context.get("results", {}).items():
                if isinstance(result, dict) and "analysis" in result:
                    analysis = result.get("analysis", {})
                    break

        code_context = context.get("trigger_payload", {}).get("code_context", "")

        prompt_template = step.prompt_template or (
            "## 修复方案\n{plan}\n\n## 当前代码\n{code}"
        )
        user_prompt = prompt_template.format(
            plan=str(analysis), code=code_context
        )

        try:
            response = await agent.run(SYSTEM_PROMPT_EXECUTE, user_prompt)
        except Exception as e:
            return StepResult(status="failed", error=_get_friendly_error(e))

        validated = validate_agent_output(response.content, ExecuteOutput)
        changes = validated if validated else (response.parsed or {"raw": response.content})

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
                            if ".." in file_path or file_path.startswith("/"):
                                logger.warning(f"跳过不安全路径: {file_path}")
                                continue
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
                return StepResult(
                    status="completed",
                    output={
                        "changes": changes,
                        "written_files": [],
                        "pr_body": str(changes),
                        "error": f"GitHub 写入失败: {e}",
                    },
                    tokens_used=response.tokens_used,
                    model=response.model,
                    error=f"GitHub 写入失败: {e}",
                )

        return StepResult(
            status="completed",
            output={
                "changes": changes,
                "written_files": written_files,
                "pr_body": "\n".join(pr_body_lines) if pr_body_lines else str(changes),
            },
            tokens_used=response.tokens_used,
            model=response.model,
        )


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
    ) -> StepResult:
        provider, model = await _get_agent_from_config(step, db)
        agent = get_agent(provider, model)

        # 从 context 中查找执行结果：优先按步骤名 "execute" 查找，
        # 否则在所有结果中查找含 "changes" 键的步骤输出
        execute_result = context.get("results", {}).get("execute", {})
        if not execute_result:
            for step_name, result in context.get("results", {}).items():
                if isinstance(result, dict) and "changes" in result:
                    execute_result = result
                    break
        changes = execute_result.get("changes", {})

        prompt_template = step.prompt_template or "## 代码改动\n{changes}"
        user_prompt = prompt_template.format(changes=str(changes))

        try:
            response = await agent.run(SYSTEM_PROMPT_REVIEW, user_prompt)
        except Exception as e:
            return StepResult(status="failed", error=_get_friendly_error(e))

        validated = validate_agent_output(response.content, ReviewOutput)
        review = validated if validated else (response.parsed or {"raw": response.content})

        return StepResult(
            status="completed",
            output={"review": review},
            tokens_used=response.tokens_used,
            model=response.model,
        )


# ── merge 处理器：创建 GitHub PR ──


@register_handler("merge")
class MergeHandler(StepHandler):
    """合并步骤：创建 GitHub Pull Request。"""

    async def execute(
        self, step: StepDefinition, context: dict[str, Any], db: AsyncSession
    ) -> StepResult:
        git_repo = context.get("git_repo")
        if not git_repo:
            return StepResult(
                status="skipped",
                output={"pr_url": None},
                error="未配置 git_repo，跳过 PR 创建",
            )

        if not settings.GITHUB_TOKEN:
            return StepResult(
                status="skipped",
                output={"pr_url": None},
                error="未配置 GITHUB_TOKEN，跳过 PR 创建",
            )

        try:
            from app.integrations.github import _parse_repo, create_pr

            owner, repo_name = _parse_repo(git_repo)
            head_branch = context.get("sandbox_branch") or context.get("git_branch")

            analyze_result = context.get("results", {}).get("analyze", {})
            analysis = analyze_result.get("analysis", {})
            if not analysis:
                for _sn, result in context.get("results", {}).items():
                    if isinstance(result, dict) and "analysis" in result:
                        analysis = result.get("analysis", {})
                        break
            issue_title = analysis.get("analysis", "Agent 自动修复")[:80]

            review_result = context.get("results", {}).get("review", {})
            if not review_result:
                for _sn, result in context.get("results", {}).items():
                    if isinstance(result, dict) and "review" in result:
                        review_result = result
                        break
            review = review_result.get("review", {})

            execute_result = context.get("results", {}).get("execute", {})
            if not execute_result:
                for _sn, result in context.get("results", {}).items():
                    if isinstance(result, dict) and ("changes" in result or "written_files" in result):
                        execute_result = result
                        break
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

            return StepResult(
                status="completed",
                output={
                    "pr_url": result["html_url"],
                    "pr_number": result["number"],
                },
            )

        except Exception as e:
            logger.error(f"创建 PR 失败: {e}")
            return StepResult(
                status="failed",
                output={"pr_url": None},
                error=str(e),
            )


@register_handler("condition")
class ConditionHandler(StepHandler):
    """条件步骤：评估条件并返回结果。"""

    async def execute(
        self, step: StepDefinition, context: dict[str, Any], db: AsyncSession
    ) -> StepResult:
        condition = step.condition
        if not condition:
            return StepResult(
                status="completed",
                output={"evaluated": True, "condition": None, "result": True},
            )

        from app.engine.condition_eval import evaluate_condition
        result = evaluate_condition(condition, context)

        return StepResult(
            status="completed",
            output={"evaluated": True, "condition": condition, "result": result},
        )


@register_handler("script")
class ScriptHandler(StepHandler):
    """脚本步骤：执行 shell 命令（带注入防护）。"""

    # 危险命令模式黑名单（正则）
    import re as _re
    _BLOCKED_PATTERNS = [
        _re.compile(r"\brm\s+-rf\s+/\b"),          # rm -rf /
        _re.compile(r"\bmkfs\b"),                    # mkfs (格式化)
        _re.compile(r"\bdd\s+if="),                  # dd if= (磁盘覆写)
        _re.compile(r":\(\)\{"),                     # fork bomb
        _re.compile(r"curl\s.*\|\s*(ba)?sh"),        # curl pipe to shell
        _re.compile(r"wget\s.*\|\s*(ba)?sh"),        # wget pipe to shell
        _re.compile(r"curl\s.*\|\s*python"),         # curl pipe to python
        _re.compile(r">\s*/dev/sd"),                 # write to disk device
        _re.compile(r"\bchmod\s+777\s+/\b"),         # chmod 777 /
        _re.compile(r"\b(nc|netcat)\s.*-e\s"),       # netcat reverse shell
        _re.compile(r"python[23]?\s*-c.*import\s+(os|subprocess|socket)"),  # python reverse shell
    ]

    # 最大超时限制
    MAX_TIMEOUT = 300  # 5 分钟

    @classmethod
    def _check_command_safety(cls, command: str) -> str | None:
        """检查命令安全性。返回 None 表示安全，否则返回危险原因。"""
        lower_cmd = command.lower()
        for pattern in cls._BLOCKED_PATTERNS:
            if pattern.search(lower_cmd):
                return f"命令包含危险模式: {pattern.pattern}"
        return None

    @staticmethod
    def _shell_escape(value: str) -> str:
        """对模板变量值进行 shell 转义，防止注入。"""
        import shlex
        return shlex.quote(value)

    async def execute(
        self, step: StepDefinition, context: dict[str, Any], db: AsyncSession
    ) -> StepResult:
        import asyncio
        import os

        command = step.config.get("command")
        if not command:
            return StepResult(
                status="skipped",
                output={"exit_code": -1},
                error="未配置 command",
            )

        # 安全检查
        safety_issue = self._check_command_safety(command)
        if safety_issue:
            logger.warning(f"ScriptHandler 拒绝执行: {safety_issue}")
            return StepResult(
                status="failed",
                output={"exit_code": -1},
                error=f"命令被安全策略拒绝: {safety_issue}",
            )

        # 替换模板变量（使用 shell 转义防止注入）
        def _collect_strings(obj: Any, prefix: str = "") -> dict[str, str]:
            """递归收集 context 中所有字符串值。"""
            result = {}
            if isinstance(obj, dict):
                for k, v in obj.items():
                    full_key = f"{prefix}.{k}" if prefix else k
                    if isinstance(v, str):
                        result[full_key] = v
                    elif isinstance(v, dict):
                        result.update(_collect_strings(v, full_key))
                    elif isinstance(v, list):
                        for i, item in enumerate(v):
                            result.update(_collect_strings(item, f"{full_key}[{i}]"))
            return result

        all_vars = _collect_strings(context)
        for key, value in all_vars.items():
            safe_value = self._shell_escape(value)
            command = command.replace(f"{{{key}}}", safe_value)

        # 限制超时
        timeout = min(step.timeout or 60, self.MAX_TIMEOUT)
        cwd = step.config.get("cwd")

        # 受限环境变量：清理危险变量，设置安全 HOME
        import tempfile
        safe_env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "LANG": "en_US.UTF-8",
            "HOME": tempfile.gettempdir(),
            "TMPDIR": tempfile.gettempdir(),
        }

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=safe_env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")

            return StepResult(
                status="completed" if proc.returncode == 0 else "failed",
                output={
                    "exit_code": proc.returncode,
                    "output": output[:10000],
                    "error": error[:5000] if error else None,
                },
                error=error[:5000] if proc.returncode != 0 and error else None,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return StepResult(
                status="failed",
                output={"exit_code": -1},
                error=f"命令超时 ({timeout}s)",
            )
        except Exception as e:
            return StepResult(
                status="failed",
                output={"exit_code": -1},
                error=str(e),
            )


@register_handler("subtask")
class SubtaskHandler(StepHandler):
    """子任务步骤：暂存 stub，自动完成。"""

    async def execute(
        self, step: StepDefinition, context: dict[str, Any], db: AsyncSession
    ) -> StepResult:
        logger.warning(f"subtask 步骤尚未实现: {step.name}")
        return StepResult(
            status="completed",
            output={"message": f"subtask 步骤 '{step.name}' 尚未实现，自动跳过"},
        )


@register_handler("loop")
class LoopHandler(StepHandler):
    """循环步骤：暂存 stub，自动完成。"""

    async def execute(
        self, step: StepDefinition, context: dict[str, Any], db: AsyncSession
    ) -> StepResult:
        logger.warning(f"loop 步骤尚未实现: {step.name}")
        return StepResult(
            status="completed",
            output={"message": f"loop 步骤 '{step.name}' 尚未实现，自动跳过"},
        )

