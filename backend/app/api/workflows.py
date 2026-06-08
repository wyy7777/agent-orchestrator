from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.workflow import Workflow
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowUpdate,
)
from app.engine.yaml_parser import validate_workflow_yaml

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)
):
    total_result = await db.execute(select(func.count(Workflow.id)))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(Workflow).order_by(Workflow.updated_at.desc()).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return WorkflowListResponse(items=items, total=total)


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(body: WorkflowCreate, db: AsyncSession = Depends(get_db)):
    valid, error = validate_workflow_yaml(body.yaml_definition)
    if not valid:
        raise HTTPException(status_code=400, detail=f"YAML 格式错误: {error}")

    workflow = Workflow(
        name=body.name,
        description=body.description,
        yaml_definition=body.yaml_definition,
    )
    db.add(workflow)
    await db.flush()
    await db.refresh(workflow)
    return workflow


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return workflow


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str, body: WorkflowUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    if body.yaml_definition is not None:
        valid, error = validate_workflow_yaml(body.yaml_definition)
        if not valid:
            raise HTTPException(status_code=400, detail=f"YAML 格式错误: {error}")
        workflow.yaml_definition = body.yaml_definition
        workflow.version += 1

    if body.name is not None:
        workflow.name = body.name
    if body.description is not None:
        workflow.description = body.description

    await db.flush()
    await db.refresh(workflow)
    return workflow


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    await db.delete(workflow)


@router.post("/validate")
async def validate_yaml(yaml_content: str):
    valid, error = validate_workflow_yaml(yaml_content)
    return {"valid": valid, "error": error}
