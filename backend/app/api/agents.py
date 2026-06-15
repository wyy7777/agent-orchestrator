"""Agent 注册中心 API：管理不同能力的 Agent 配置。"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent_config import AgentConfig
from app.models.user import User
from app.auth import require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


# ── Pydantic schemas ──

class AgentCreate(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    capabilities: list[str] = []
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout_seconds: int = 300
    token_budget: int = 0
    enabled: bool = True


class AgentResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: str | None = None
    capabilities: list[str] = []
    provider: str
    model: str
    max_tokens: int
    temperature: float
    timeout_seconds: int
    token_budget: int
    enabled: bool
    created_at: str | None = None


# ── CRUD ──

@router.get("")
async def list_agents(
    db: AsyncSession = Depends(get_db),
) -> list[AgentResponse]:
    result = await db.execute(select(AgentConfig).order_by(AgentConfig.created_at.desc()))
    return [AgentResponse(**a.to_dict()) for a in result.scalars().all()]


@router.post("", status_code=201)
async def create_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager")),
) -> AgentResponse:
    # 检查名称唯一性
    existing = await db.execute(select(AgentConfig).where(AgentConfig.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Agent 名称 '{body.name}' 已存在")

    agent = AgentConfig(
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        capabilities=body.capabilities,
        provider=body.provider,
        model=body.model,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
        timeout_seconds=body.timeout_seconds,
        token_budget=body.token_budget,
        enabled=body.enabled,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return AgentResponse(**agent.to_dict())


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    result = await db.execute(select(AgentConfig).where(AgentConfig.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return AgentResponse(**agent.to_dict())


@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    body: AgentCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager")),
) -> AgentResponse:
    result = await db.execute(select(AgentConfig).where(AgentConfig.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    # 检查名称唯一性（排除自身）
    if body.name != agent.name:
        existing = await db.execute(select(AgentConfig).where(AgentConfig.name == body.name))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Agent 名称 '{body.name}' 已存在")

    agent.name = body.name
    agent.display_name = body.display_name
    agent.description = body.description
    agent.capabilities = body.capabilities
    agent.provider = body.provider
    agent.model = body.model
    agent.max_tokens = body.max_tokens
    agent.temperature = body.temperature
    agent.timeout_seconds = body.timeout_seconds
    agent.token_budget = body.token_budget
    agent.enabled = body.enabled
    await db.commit()
    await db.refresh(agent)
    return AgentResponse(**agent.to_dict())


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin")),
):
    result = await db.execute(select(AgentConfig).where(AgentConfig.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    await db.delete(agent)
    await db.commit()


@router.get("/match/{step_type}")
async def match_agents_for_step(
    step_type: str,
    db: AsyncSession = Depends(get_db),
) -> list[AgentResponse]:
    """查找能处理指定步骤类型的所有 Agent。"""
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.enabled == True)  # noqa: E712
    )
    agents = result.scalars().all()
    matched = [a for a in agents if a.matches_step_type(step_type)]
    return [AgentResponse(**a.to_dict()) for a in matched]
