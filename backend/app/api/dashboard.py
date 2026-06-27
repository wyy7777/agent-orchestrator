import csv
import io
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.database import get_db
from app.models.approval import Approval
from app.models.task import Task
from app.models.user import User
from app.models.workflow import Workflow
from app.schemas.dashboard import (
    DailyTrend,
    DashboardStats,
    ErrorSummary,
    TopWorkflow,
    TrendsResponse,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db), _user: User = Depends(require_role("admin", "manager", "operator", "viewer"))):
    total = (await db.execute(select(func.count(Task.id)))).scalar() or 0
    completed = (
        await db.execute(select(func.count(Task.id)).where(Task.status == "completed"))
    ).scalar() or 0
    failed = (
        await db.execute(select(func.count(Task.id)).where(Task.status == "failed"))
    ).scalar() or 0
    running = (
        await db.execute(select(func.count(Task.id)).where(Task.status == "running"))
    ).scalar() or 0
    pending_approvals = (
        await db.execute(
            select(func.count(Approval.id)).where(Approval.status == "pending")
        )
    ).scalar() or 0
    total_tokens = (
        await db.execute(select(func.coalesce(func.sum(Task.total_tokens_used), 0)))
    ).scalar() or 0

    success_rate = (completed / total * 100) if total > 0 else 0.0

    # 审批通过率
    total_decided = (
        await db.execute(
            select(func.count(Approval.id)).where(
                Approval.status.in_(["approved", "rejected"])
            )
        )
    ).scalar() or 0
    approved_count = (
        await db.execute(
            select(func.count(Approval.id)).where(Approval.status == "approved")
        )
    ).scalar() or 0
    approval_rate = (approved_count / total_decided * 100) if total_decided > 0 else 0.0

    return DashboardStats(
        total_tasks=total,
        completed_tasks=completed,
        failed_tasks=failed,
        running_tasks=running,
        pending_approvals=pending_approvals,
        success_rate=round(success_rate, 1),
        total_tokens_used=total_tokens,
        avg_approval_pass_rate=round(approval_rate, 1),
    )


@router.get("/trends", response_model=TrendsResponse)
async def get_dashboard_trends(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """趋势数据：每日任务数、成功率、Token 消耗、平均执行时间"""
    now = datetime.now(UTC)
    start_date = now - timedelta(days=days - 1)
    start_str = start_date.strftime("%Y-%m-%d")

    # SQLite 的 date() 函数按天分组
    day_expr = func.date(Task.created_at)

    rows = (
        await db.execute(
            select(
                day_expr.label("day"),
                func.count(Task.id).label("task_count"),
                func.sum(case((Task.status == "completed", 1), else_=0)).label(
                    "completed_count"
                ),
                func.coalesce(func.sum(Task.total_tokens_used), 0).label("token_usage"),
                func.avg(
                    case(
                        (
                            Task.completed_at.isnot(None) & Task.started_at.isnot(None),
                            func.strftime("%s", Task.completed_at)
                            - func.strftime("%s", Task.started_at),
                        ),
                        else_=None,
                    )
                ).label("avg_exec_time"),
            )
            .where(day_expr >= start_str)
            .group_by(day_expr)
            .order_by(day_expr)
        )
    ).all()

    # 构建完整日期序列（缺失日期补零）
    date_map: dict[str, DailyTrend] = {}
    for row in rows:
        d = str(row.day)
        count = row.task_count or 0
        completed = row.completed_count or 0
        rate = (completed / count * 100) if count > 0 else 0.0
        date_map[d] = DailyTrend(
            date=d,
            task_count=count,
            success_rate=round(rate, 1),
            token_usage=row.token_usage or 0,
            avg_execution_time=round(row.avg_exec_time or 0, 2),
        )

    result: list[DailyTrend] = []
    for i in range(days):
        d = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        result.append(
            date_map.get(d, DailyTrend(date=d))
        )

    return TrendsResponse(days=days, data=result)


@router.get("/top-workflows", response_model=list[TopWorkflow])
async def get_top_workflows(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager", "operator", "viewer")),
):
    """热门工作流，按执行次数排序"""
    rows = (
        await db.execute(
            select(
                Task.workflow_id,
                Workflow.name.label("workflow_name"),
                func.count(Task.id).label("execution_count"),
                func.sum(case((Task.status == "completed", 1), else_=0)).label(
                    "success_count"
                ),
            )
            .join(Workflow, Task.workflow_id == Workflow.id)
            .group_by(Task.workflow_id, Workflow.name)
            .order_by(func.count(Task.id).desc())
            .limit(limit)
        )
    ).all()

    return [
        TopWorkflow(
            workflow_id=row.workflow_id,
            workflow_name=row.workflow_name,
            execution_count=row.execution_count,
            success_count=row.success_count or 0,
            success_rate=round(
                (row.success_count or 0) / row.execution_count * 100, 1
            ),
        )
        for row in rows
    ]


@router.get("/errors", response_model=list[ErrorSummary])
async def get_dashboard_errors(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager", "operator", "viewer")),
):
    """最近错误汇总，按错误类型分组"""
    # 从 task 和 step_execution 两个表收集错误
    # 简单起见从 task 表的 error_message 做粗略分类
    rows = (
        await db.execute(
            select(
                Task.error_message,
                func.count(Task.id).label("count"),
            )
            .where(Task.status == "failed", Task.error_message.isnot(None))
            .group_by(Task.error_message)
            .order_by(func.count(Task.id).desc())
            .limit(limit)
        )
    ).all()

    results: list[ErrorSummary] = []
    for row in rows:
        msg = row.error_message or ""
        # 粗略分类：取第一行前 50 字符作为类型标识
        first_line = msg.split("\n")[0][:50]
        results.append(
            ErrorSummary(
                error_type=first_line,
                count=row.count,
                latest_message=msg[:500],
            )
        )
    return results


@router.get("/export")
async def export_dashboard_data(
    type: str = Query("tasks", pattern="^(tasks|executions)$"),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager", "operator")),
):
    """导出数据为 CSV（支持 tasks / executions）"""
    now = datetime.now(UTC)
    start_date = now - timedelta(days=days)

    if type == "tasks":
        rows = (
            await db.execute(
                select(Task)
                .where(Task.created_at >= start_date)
                .order_by(Task.created_at.desc())
            )
        ).scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "workflow_id",
                "status",
                "trigger_type",
                "total_tokens_used",
                "error_message",
                "created_at",
                "started_at",
                "completed_at",
            ]
        )
        for t in rows:
            writer.writerow(
                [
                    t.id,
                    t.workflow_id,
                    t.status,
                    t.trigger_type or "",
                    t.total_tokens_used,
                    t.error_message or "",
                    t.created_at.isoformat() if t.created_at else "",
                    t.started_at.isoformat() if t.started_at else "",
                    t.completed_at.isoformat() if t.completed_at else "",
                ]
            )
        filename = f"tasks_export_{now.strftime('%Y%m%d_%H%M%S')}.csv"

    else:
        from app.models.step_execution import StepExecution

        rows = (
            await db.execute(
                select(StepExecution)
                .where(StepExecution.started_at >= start_date)
                .order_by(StepExecution.started_at.desc())
            )
        ).scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "task_id",
                "step_index",
                "step_name",
                "step_type",
                "status",
                "ai_model",
                "error_message",
                "started_at",
                "completed_at",
            ]
        )
        for s in rows:
            writer.writerow(
                [
                    s.id,
                    s.task_id,
                    s.step_index,
                    s.step_name,
                    s.step_type,
                    s.status,
                    s.ai_model or "",
                    s.error_message or "",
                    s.started_at.isoformat() if s.started_at else "",
                    s.completed_at.isoformat() if s.completed_at else "",
                ]
            )
        filename = f"executions_export_{now.strftime('%Y%m%d_%H%M%S')}.csv"

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/quality-trends")
async def quality_trends(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager", "operator", "viewer")),
):
    """返回近 N 天的质量评分趋势（按日聚合）。"""
    from app.models.step_execution import StepExecution

    now = datetime.now(UTC)
    start_date = now - timedelta(days=days)

    result = await db.execute(
        select(StepExecution).where(
            StepExecution.completed_at >= start_date,
            StepExecution.quality_score.isnot(None),
        )
    )
    steps = result.scalars().all()

    # 按日期聚合
    daily: dict[str, list[dict]] = {}
    for s in steps:
        if not s.completed_at:
            continue
        day_key = s.completed_at.strftime("%Y-%m-%d")
        if day_key not in daily:
            daily[day_key] = []
        daily[day_key].append(s.quality_score)

    trends = []
    for day in sorted(daily.keys()):
        scores = daily[day]
        valid = [s for s in scores if s.get("correctness", -1) >= 0]
        if not valid:
            continue
        trends.append({
            "date": day,
            "count": len(valid),
            "avg_correctness": round(sum(s["correctness"] for s in valid) / len(valid), 1),
            "avg_completeness": round(sum(s["completeness"] for s in valid) / len(valid), 1),
            "avg_security": round(sum(s["security"] for s in valid) / len(valid), 1),
            "avg_style": round(sum(s["style"] for s in valid) / len(valid), 1),
        })

    return {"trends": trends}
