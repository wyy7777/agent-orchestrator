from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.schedule import ScheduleCreate, ScheduleListResponse, ScheduleResponse
from app.services.scheduler import scheduler

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(body: ScheduleCreate, db: AsyncSession = Depends(get_db)):
    """创建一条调度配置。"""
    try:
        schedule = await scheduler.add_schedule(
            workflow_id=body.workflow_id,
            cron_expr=body.cron_expr,
            payload=body.payload,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ScheduleResponse(
        id=schedule.id,
        workflow_id=schedule.workflow_id,
        cron_expr=schedule.cron_expr,
        payload=schedule.payload,
        enabled=schedule.enabled,
        created_at=schedule.created_at,
        last_triggered_at=schedule.last_triggered_at,
    )


@router.get("", response_model=ScheduleListResponse)
async def list_schedules():
    """列出所有调度配置。"""
    items = scheduler.list_schedules()
    return ScheduleListResponse(
        items=[
            ScheduleResponse(
                id=s.id,
                workflow_id=s.workflow_id,
                cron_expr=s.cron_expr,
                payload=s.payload,
                enabled=s.enabled,
                created_at=s.created_at,
                last_triggered_at=s.last_triggered_at,
            )
            for s in items
        ],
        total=len(items),
    )


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def toggle_schedule(schedule_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    """启用/禁用一条调度配置。"""
    enabled = body.get("enabled")
    if enabled is None:
        raise HTTPException(status_code=400, detail="缺少 enabled 字段")
    schedule = await scheduler.toggle_schedule(schedule_id, enabled, db=db)
    if not schedule:
        raise HTTPException(status_code=404, detail="调度不存在")
    return ScheduleResponse(
        id=schedule.id,
        workflow_id=schedule.workflow_id,
        cron_expr=schedule.cron_expr,
        payload=schedule.payload,
        enabled=schedule.enabled,
        created_at=schedule.created_at,
        last_triggered_at=schedule.last_triggered_at,
    )


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: str, db: AsyncSession = Depends(get_db)):
    """删除一条调度配置。"""
    if not await scheduler.remove_schedule(schedule_id, db=db):
        raise HTTPException(status_code=404, detail="调度不存在")
