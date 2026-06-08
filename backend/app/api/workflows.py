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

    # 检查名称是否重复
    existing = await db.execute(select(Workflow).where(Workflow.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"工作流名称 '{body.name}' 已存在")

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
async def validate_yaml(body: dict):
    yaml_content = body.get("yaml_content", "")
    valid, error = validate_workflow_yaml(yaml_content)
    return {"valid": valid, "error": error}


# 预置工作流模板
WORKFLOW_TEMPLATES = [
    {
        "name": "GitHub Issue 自动修复",
        "description": "自动分析 Issue，生成修复方案，执行代码修改，审查后创建 PR",
        "yaml_definition": """name: GitHub Issue 自动修复
description: 自动分析 GitHub Issue 并生成修复 PR

steps:
  - name: analyze
    type: analyze
    timeout: 120
    config:
      provider: deepseek

  - name: review_plan
    type: approval
    timeout: 3600

  - name: execute
    type: execute
    timeout: 300
    config:
      provider: deepseek

  - name: review_code
    type: review
    timeout: 120
    config:
      provider: deepseek

  - name: final_approval
    type: approval
    timeout: 3600

  - name: create_pr
    type: merge
    timeout: 60
""",
    },
    {
        "name": "代码审查助手",
        "description": "对代码变更进行自动审查，生成审查报告",
        "yaml_definition": """name: 代码审查助手
description: 自动审查代码变更并生成报告

steps:
  - name: analyze
    type: analyze
    timeout: 120
    config:
      provider: deepseek
      prompt_template: |
        ## 代码变更
        {code}

        请分析以下内容：
        1. 代码质量
        2. 潜在问题
        3. 改进建议

  - name: review
    type: review
    timeout: 120
    config:
      provider: deepseek

  - name: approval
    type: approval
    timeout: 3600
""",
    },
    {
        "name": "需求分析工作流",
        "description": "分析产品需求，输出技术方案和任务拆解",
        "yaml_definition": """name: 需求分析工作流
description: 分析需求并输出技术方案

steps:
  - name: analyze
    type: analyze
    timeout: 120
    config:
      provider: deepseek
      prompt_template: |
        ## 需求描述
        {issue}

        请输出：
        1. 需求理解
        2. 技术方案
        3. 任务拆解
        4. 风险评估

  - name: approval
    type: approval
    timeout: 3600
""",
    },
]


@router.get("/templates")
async def list_templates():
    return WORKFLOW_TEMPLATES


@router.post("/templates/{index}", response_model=WorkflowResponse, status_code=201)
async def import_template(index: int, db: AsyncSession = Depends(get_db)):
    if index < 0 or index >= len(WORKFLOW_TEMPLATES):
        raise HTTPException(status_code=400, detail="模板不存在")

    template = WORKFLOW_TEMPLATES[index]

    # 检查是否已导入
    existing = await db.execute(select(Workflow).where(Workflow.name == template["name"]))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"模板 '{template['name']}' 已导入")

    workflow = Workflow(
        name=template["name"],
        description=template["description"],
        yaml_definition=template["yaml_definition"],
    )
    db.add(workflow)
    await db.flush()
    await db.refresh(workflow)
    return workflow
