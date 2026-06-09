"""示例外部插件：JSON 数据验证。

将此文件放入 plugins/ 目录即可自动加载。
"""
from app.engine.plugin import StepPlugin, register_plugin


@register_plugin("json_validate")
class JsonValidatePlugin(StepPlugin):
    """验证 JSON 数据是否符合指定 schema。"""

    name = "json_validate"
    description = "验证 JSON 数据结构"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["data_path", "schema"],
            "properties": {
                "data_path": {
                    "type": "string",
                    "description": "要验证的数据路径（点分隔，如 results.analyze.output）",
                },
                "schema": {
                    "type": "object",
                    "description": "期望的数据结构描述",
                    "properties": {
                        "required_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "必须存在的字段列表",
                        },
                        "type_checks": {
                            "type": "object",
                            "description": "字段类型检查（字段名→期望类型）",
                        },
                    },
                },
            },
        }

    async def execute(self, config: dict, context: dict) -> dict:
        data_path = config["data_path"]
        schema = config["schema"]

        # 从 context 获取数据
        data = _deep_get(context, data_path)
        if data is None:
            return {
                "valid": False,
                "error": f"数据路径 {data_path} 不存在",
            }

        if not isinstance(data, dict):
            return {
                "valid": False,
                "error": f"数据不是字典类型: {type(data).__name__}",
            }

        errors = []

        # 检查必须字段
        for field in schema.get("required_fields", []):
            if field not in data:
                errors.append(f"缺少必须字段: {field}")

        # 检查字段类型
        type_map = {
            "string": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
        }
        for field, expected_type in schema.get("type_checks", {}).items():
            if field in data:
                expected_cls = type_map.get(expected_type)
                if expected_cls and not isinstance(data[field], expected_cls):
                    errors.append(
                        f"字段 {field} 类型错误: 期望 {expected_type}, 实际 {type(data[field]).__name__}"
                    )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "fields_checked": len(data),
        }


def _deep_get(obj: dict, path: str):
    """按点分隔路径从嵌套字典中取值。"""
    current = obj
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current
