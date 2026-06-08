"""模型公共工具。"""
import uuid
from datetime import datetime, timezone

def utcnow():
    return datetime.now(timezone.utc)

def gen_uuid():
    return str(uuid.uuid4())
