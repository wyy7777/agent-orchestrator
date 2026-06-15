"""审批策略 API + 批量审批。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.approval import Approval
from app.models.approval_policy import ApprovalPolicy, get_matching_policies
from app.models.step_execution import StepExecution
from app.models.task import Task
from app.models.user import User
from app.auth import require_role
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approval-policies", tags=["approval-policies"])


# ── Pydantic schemas ──

class PolicyCreate(BaseModel):
    name: str
    description: str | None = None
    workflow_id: str | None = None
    condition: str | None = None
    approvers: list[str] | None = None
    quorum: int = 1
    timeout_minutes: int = 0
    enabled: bool = True


class PolicyResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    workflow_id: str | None = None
    condition: str | None = None
    approvers: list | None = None
    quorum: int = 1
    timeout_minutes: int = 0
    enabled: bool = True
    created_at: str | None = None


class BatchDecision(BaseModel):
    ids: list[str]
    action: str  # "approve" | "reject"
    comment: str | None = None


# ── CRUD ──


@router.get("")
async def list_policies(
    db: AsyncSession = Depends(get_db),
) -> list[PolicyResponse]:
    result = await db.execute(select(ApprovalPolicy).order_by(ApprovalPolicy.created_at.desc()))
    return [PolicyResponse(**p.to_dict()) for p in result.scalars().all()]


@router.post("", status_code=201)
async def create_policy(
    body: PolicyCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager")),
) -> PolicyResponse:
    policy = ApprovalPolicy(
        name=body.name,
        description=body.description,
        workflow_id=body.workflow_id,
        condition=body.condition,
        approvers=body.approvers,
        quorum=body.quorum,
        timeout_minutes=body.timeout_minutes,
        enabled=body.enabled,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return PolicyResponse(**policy.to_dict())


@router.put("/{policy_id}")
async def update_policy(
    policy_id: str,
    body: PolicyCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager")),
) -> PolicyResponse:
    result = await db.execute(select(ApprovalPolicy).where(ApprovalPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")

    policy.name = body.name
    policy.description = body.description
    policy.workflow_id = body.workflow_id
    policy.condition = body.condition
    policy.approvers = body.approvers
    policy.quorum = body.quorum
    policy.timeout_minutes = body.timeout_minutes
    policy.enabled = body.enabled
    await db.commit()
    await db.refresh(policy)
    return PolicyResponse(**policy.to_dict())


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager")),
):
    result = await db.execute(select(ApprovalPolicy).where(ApprovalPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")
    await db.delete(policy)
    await db.commit()


@router.get("/match")
async def match_policies(
    workflow_id: str,
    step_type: str = "",
    risk_level: str = "low",
    db: AsyncSession = Depends(get_db),
) -> list[PolicyResponse]:
    """检查哪些策略匹配当前上下文。"""
    context = {"step_type": step_type, "risk_level": risk_level}
    policies = await get_matching_policies(db, workflow_id, context)
    return [PolicyResponse(**p.to_dict()) for p in policies]
