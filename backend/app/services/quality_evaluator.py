"""AI 质量评分服务：对 execute/review 步骤输出做自动质量评估。"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.agents.base import get_agent

logger = logging.getLogger(__name__)

QUALITY_EVAL_PROMPT = """你是一位代码质量评审专家。请对以下步骤输出进行质量评分。

步骤类型: {step_type}
步骤输出:
{output_json}

上下文信息:
{context_json}

请从以下 4 个维度评分（0-10 分），并输出严格 JSON：

{{
    "correctness": <0-10>,
    "completeness": <0-10>,
    "security": <0-10>,
    "style": <0-10>,
    "summary": "<简短评价>"
}}

评分标准：
- correctness: 输出是否正确、逻辑是否合理
- completeness: 是否覆盖了所有必要内容
- security: 是否有安全隐患（注入、泄露等）
- style: 代码风格、可读性、规范性

只输出 JSON，不要输出其他内容。"""


class QualityEvaluator:
    """AI 质量评分器。"""

    async def evaluate(
        self,
        step_type: str,
        output: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        对步骤输出进行质量评分。

        返回:
            {correctness: int, completeness: int, security: int, style: int, summary: str}
            失败时返回 {-1, -1, -1, -1, error: "..."}
        """
        if step_type not in ("execute", "review", "analyze"):
            return {"skipped": True, "reason": f"步骤类型 {step_type} 不需要评分"}

        try:
            agent = get_agent("deepseek")
            prompt = QUALITY_EVAL_PROMPT.format(
                step_type=step_type,
                output_json=json.dumps(output, ensure_ascii=False, indent=2)[:3000],
                context_json=json.dumps(
                    {k: v for k, v in context.items() if k != "results"},
                    ensure_ascii=False,
                    indent=2,
                )[:2000],
            )

            response = await agent.run(
                system_prompt="你是代码质量评审专家。只输出 JSON。",
                user_prompt=prompt,
            )

            result = json.loads(response.content)

            # 验证评分范围
            for key in ("correctness", "completeness", "security", "style"):
                val = result.get(key, -1)
                if not isinstance(val, (int, float)) or val < 0 or val > 10:
                    result[key] = -1

            result["summary"] = result.get("summary", "")[:500]
            return result

        except Exception as e:
            logger.warning(f"质量评分失败: {e}")
            return {
                "correctness": -1,
                "completeness": -1,
                "security": -1,
                "style": -1,
                "error": str(e)[:200],
            }


# 单例
quality_evaluator = QualityEvaluator()
