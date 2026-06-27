"""模型公共工具。"""
import uuid
from datetime import UTC, datetime


def utcnow():
    return datetime.now(UTC)

def gen_uuid():
    return str(uuid.uuid4())
