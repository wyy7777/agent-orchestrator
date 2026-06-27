"""审计日志服务。"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.database import async_session
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def record_audit(
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    resource_name: str | None = None,
    user_id: str | None = None,
    username: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
):
    """记录一条审计日志。"""
    try:
        async with async_session() as db:
            log = AuditLog(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                user_id=user_id,
                username=username,
                details=json.dumps(details, ensure_ascii=False) if details else None,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.add(log)
            await db.commit()
    except Exception as e:
        logger.error(f"审计日志写入失败: {e}")


# 便捷函数
async def audit_workflow_created(workflow_id: str, name: str, user_id: str = None):
    await record_audit("create", "workflow", workflow_id, name, user_id)

async def audit_task_started(task_id: str, workflow_name: str, user_id: str = None):
    await record_audit("start", "task", task_id, workflow_name, user_id)

async def audit_task_completed(task_id: str, workflow_name: str, user_id: str = None):
    await record_audit("complete", "task", task_id, workflow_name, user_id)

async def audit_task_failed(task_id: str, workflow_name: str, reason: str = None, user_id: str = None):
    await record_audit("fail", "task", task_id, workflow_name, user_id, details={"reason": reason})

async def audit_approval_decided(approval_id: str, decision: str, user_id: str = None, username: str = None):
    await record_audit(decision, "approval", approval_id, user_id=user_id, username=username)

async def audit_task_rollback(task_id: str, step_index: int, user_id: str = None):
    await record_audit("rollback", "task", task_id, user_id=user_id, details={"step_index": step_index})

async def audit_user_login(username: str, ip_address: str = None):
    await record_audit("login", "user", username=username, ip_address=ip_address)

async def audit_settings_changed(setting_name: str, user_id: str = None):
    await record_audit("update", "settings", resource_name=setting_name, user_id=user_id)
