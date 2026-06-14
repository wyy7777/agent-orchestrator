"""审计日志 API。"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.auth import require_admin, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["审计日志"])


@router.get("")
async def list_audit_logs(
    action: str | None = Query(None, description="操作类型筛选"),
    resource_type: str | None = Query(None, description="资源类型筛选"),
    user_id: str | None = Query(None, description="用户ID筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """获取审计日志列表（需管理员权限）。"""
    query = select(AuditLog)

    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)

    # 计数
    count_query = select(func.count(AuditLog.id))
    if action:
        count_query = count_query.where(AuditLog.action == action)
    if resource_type:
        count_query = count_query.where(AuditLog.resource_type == resource_type)
    if user_id:
        count_query = count_query.where(AuditLog.user_id == user_id)
    total = (await db.execute(count_query)).scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(page_size)
    )
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "user_id": log.user_id,
                "username": log.username,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "resource_name": log.resource_name,
                "details": log.details,
                "ip_address": log.ip_address,
            }
            for log in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/report")
async def generate_audit_report(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="截止日期 YYYY-MM-DD"),
    format: str = Query("csv", description="格式: csv | detailed_csv"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager")),
):
    """生成合规审计报告（CSV），含 SHA-256 签名。detailed_csv 包含步骤级详情。"""
    import csv
    import hashlib
    import io
    from datetime import datetime as dt
    from fastapi.responses import StreamingResponse
    from app.models.task import Task
    from app.models.step_execution import StepExecution
    from app.models.approval import Approval
    from sqlalchemy.orm import selectinload

    start_dt = dt.fromisoformat(start_date)
    end_dt = dt.fromisoformat(end_date + "T23:59:59")

    result = await db.execute(
        select(Task)
        .options(selectinload(Task.step_executions))
        .where(Task.created_at >= start_dt, Task.created_at <= end_dt)
        .order_by(Task.created_at)
    )
    tasks = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    if format == "detailed_csv":
        # 步骤级详细报告：每行一个步骤执行
        writer.writerow([
            "task_id", "workflow_name", "task_status", "step_index", "step_name",
            "step_type", "step_status", "ai_model", "tokens_used",
            "quality_correctness", "quality_completeness", "quality_security", "quality_style",
            "error_message", "started_at", "completed_at",
        ])
        for t in tasks:
            wf_name = t.workflow.name if t.workflow else ""
            for s in t.step_executions:
                qs = s.quality_score or {}
                writer.writerow([
                    t.id, wf_name, t.status,
                    s.step_index, s.step_name, s.step_type, s.status,
                    s.ai_model or "", s.token_usage.get("tokens", 0) if s.token_usage else 0,
                    qs.get("correctness", ""), qs.get("completeness", ""),
                    qs.get("security", ""), qs.get("style", ""),
                    (s.error_message or "")[:200],
                    s.started_at.isoformat() if s.started_at else "",
                    s.completed_at.isoformat() if s.completed_at else "",
                ])
    else:
        # 任务级摘要报告
        writer.writerow([
            "task_id", "workflow_name", "status", "trigger_type",
            "started_at", "completed_at", "total_tokens",
            "steps_total", "steps_completed", "steps_failed", "error_message",
        ])
        for t in tasks:
            completed = sum(1 for s in t.step_executions if s.status == "completed")
            failed = sum(1 for s in t.step_executions if s.status == "failed")
            writer.writerow([
                t.id,
                t.workflow.name if t.workflow else "",
                t.status,
                t.trigger_type or "",
                t.started_at.isoformat() if t.started_at else "",
                t.completed_at.isoformat() if t.completed_at else "",
                t.total_tokens_used,
                len(t.step_executions),
                completed,
                failed,
                (t.error_message or "")[:200],
            ])

    content = output.getvalue()
    sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # 存储报告记录
    try:
        from app.models.audit_report import AuditReport
        report = AuditReport(
            start_date=start_dt,
            end_date=end_dt,
            format=format,
            sha256=sha256,
            size_bytes=len(content.encode("utf-8")),
        )
        db.add(report)
        await db.commit()
    except Exception as e:
        logger.warning(f"报告存储失败: {e}")

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=audit_report_{start_date}_{end_date}.{format}.csv",
            "X-Report-SHA256": sha256,
        },
    )


@router.get("/reports")
async def list_reports(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """列出已生成的审计报告。"""
    from app.models.audit_report import AuditReport
    result = await db.execute(
        select(AuditReport).order_by(AuditReport.created_at.desc()).limit(50)
    )
    reports = result.scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "start_date": r.start_date.isoformat() if r.start_date else None,
                "end_date": r.end_date.isoformat() if r.end_date else None,
                "format": r.format,
                "sha256": r.sha256,
                "size_bytes": r.size_bytes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ]
    }
