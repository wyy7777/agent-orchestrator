"""条件表达式评估器。"""
from __future__ import annotations

import operator
import re
from typing import Any

# 条件表达式运算符映射
_OPERATORS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}


def evaluate_condition(condition: str, context: dict[str, Any]) -> bool:
    """
    评估条件表达式。

    支持的语法:
    - 比较: {result.score} > 80
    - 存在性: {result.pr_url}
    - 布尔: {result.approved} == true
    - 复合: {result.score} > 80 and {result.approved} == true
    """
    if not condition:
        return True

    # 替换上下文变量 {key.path}
    def resolve_var(match: re.Match) -> str:
        var_path = match.group(1).strip()
        value = context
        for key in var_path.split("."):
            if isinstance(value, dict):
                value = value.get(key)
            else:
                value = None
                break
        if value is None:
            return "None"
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return f'"{value}"'
        return str(value)

    expr = re.sub(r"\{([^}]+)\}", resolve_var, condition)

    # 处理复合条件 (and/or)
    if " and " in expr:
        parts = expr.split(" and ")
        return all(_evaluate_single(p.strip()) for p in parts)
    if " or " in expr:
        parts = expr.split(" or ")
        return any(_evaluate_single(p.strip()) for p in parts)

    return _evaluate_single(expr)


def _evaluate_single(expr: str) -> bool:
    """评估单个条件表达式。"""
    expr = expr.strip()

    # 按长度降序遍历，确保 >= 优先于 >、<= 优先于 <
    for op_str, op_func in sorted(_OPERATORS.items(), key=lambda x: -len(x[0])):
        if op_str in expr:
            left, right = expr.split(op_str, 1)
            left = left.strip().strip('"')
            right = right.strip().strip('"')
            try:
                left_val = float(left) if left != "None" else None
                right_val = float(right) if right != "None" else None
                if left_val is not None and right_val is not None:
                    return op_func(left_val, right_val)
            except (ValueError, TypeError):
                pass
            # 字符串比较
            if left == "None":
                return right == "None"
            if right == "None":
                return False
            return op_func(left, right)

    # 存在性检查 (truthy)
    if expr.lower() == "true":
        return True
    if expr.lower() in ("false", "none", "null", "0", "no", ""):
        return False
    if expr.startswith('"') and expr.endswith('"'):
        return bool(expr[1:-1])

    # 默认为真（非空字符串）
    return bool(expr)
