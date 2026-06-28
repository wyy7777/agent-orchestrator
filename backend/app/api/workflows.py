import base64
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.database import get_db
from app.engine.yaml_parser import validate_workflow_yaml
from app.models.user import User
from app.models.workflow import Workflow
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowUpdate,
)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_db)
):
    total_result = await db.execute(select(func.count(Workflow.id)))
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        select(Workflow).order_by(Workflow.updated_at.desc()).offset(offset).limit(page_size)
    )
    items = result.scalars().all()
    return WorkflowListResponse(items=items, total=total)


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(body: WorkflowCreate, db: AsyncSession = Depends(get_db), _user: User = Depends(require_role("admin", "manager", "operator"))):
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
    workflow_id: str, body: WorkflowUpdate, db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager", "operator")),
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
async def delete_workflow(workflow_id: str, db: AsyncSession = Depends(get_db), _user: User = Depends(require_role("admin", "manager"))):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    await db.delete(workflow)



TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _load_templates() -> list[dict]:
    """加载所有内置模板。"""
    templates = []
    if not TEMPLATES_DIR.exists():
        return templates
    for f in sorted(TEMPLATES_DIR.glob("*.yaml")):
        try:
            content = f.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            if data and isinstance(data, dict):
                templates.append({
                    "name": data.get("name", f.stem),
                    "description": data.get("description", ""),
                    "yaml_definition": content,
                })
        except Exception:
            continue
    return templates


@router.get("/templates")
async def list_templates():
    """获取所有内置工作流模板。"""
    return _load_templates()


@router.post("/templates/{index}", response_model=WorkflowResponse, status_code=201)
async def import_template(index: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require_role("admin", "manager", "operator"))):
    """从模板库导入一个工作流。"""
    templates = _load_templates()
    if index < 0 or index >= len(templates):
        raise HTTPException(status_code=404, detail="模板不存在")

    tpl = templates[index]
    workflow = Workflow(
        name=tpl["name"],
        description=tpl["description"],
        yaml_definition=tpl["yaml_definition"],
    )
    db.add(workflow)
    await db.flush()
    await db.refresh(workflow)
    return workflow


@router.post("/validate")
async def validate_yaml(body: dict):
    yaml_content = body.get("yaml_content", "")
    valid, error = validate_workflow_yaml(yaml_content)
    return {"valid": valid, "error": error}



@router.get("/{workflow_id}/share")
async def share_workflow(workflow_id: str, db: AsyncSession = Depends(get_db), _user: User = Depends(require_role("admin", "manager"))):
    """生成工作流分享链接。"""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    # 将 YAML 内容编码为 base64
    yaml_bytes = workflow.yaml_definition.encode("utf-8")
    encoded = base64.urlsafe_b64encode(yaml_bytes).decode("ascii")

    return {
        "workflow_id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "share_code": encoded,
        "share_url": f"/workflows/import?code={encoded}",
    }


@router.post("/import-share")
async def import_shared_workflow(body: dict, db: AsyncSession = Depends(get_db), _user: User = Depends(require_role("admin", "manager", "operator"))):
    """从分享代码导入工作流。"""
    share_code = body.get("share_code", "")
    if not share_code:
        raise HTTPException(status_code=400, detail="分享代码不能为空")

    try:
        yaml_bytes = base64.urlsafe_b64decode(share_code)
        yaml_content = yaml_bytes.decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="无效的分享代码")

    valid, error = validate_workflow_yaml(yaml_content)
    if not valid:
        raise HTTPException(status_code=400, detail=f"工作流格式错误: {error}")

    # 解析名称
    try:
        data = yaml.safe_load(yaml_content)
        name = data.get("name", f"导入的工作流_{datetime.now().strftime('%H%M%S')}")
        description = data.get("description", "")
    except Exception:
        name = f"导入的工作流_{datetime.now().strftime('%H%M%S')}"
        description = ""

    workflow = Workflow(
        name=name,
        description=description,
        yaml_definition=yaml_content,
    )
    db.add(workflow)
    await db.flush()
    await db.refresh(workflow)
    return workflow


@router.get("/export/{workflow_id}")
async def export_workflow(workflow_id: str, db: AsyncSession = Depends(get_db), _user: User = Depends(require_role("admin", "manager", "operator"))):
    """导出工作流 YAML 文件。"""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    return {
        "name": workflow.name,
        "description": workflow.description,
        "yaml": workflow.yaml_definition,
        "filename": f"{workflow.name.replace(' ', '_')}.yaml",
    }


@router.get("/{workflow_id}/circuit-breaker")
async def get_circuit_breaker_status(workflow_id: str, _user: User = Depends(require_role("admin", "manager", "operator"))):
    """获取工作流断路器状态。"""
    from app.engine.circuit_breaker import circuit_breaker
    return circuit_breaker.get_status(workflow_id)


@router.post("/{workflow_id}/circuit-breaker/reset")
async def reset_circuit_breaker(workflow_id: str, _user: User = Depends(require_role("admin", "manager"))):
    """手动重置工作流断路器。"""
    from app.engine.circuit_breaker import circuit_breaker
    circuit_breaker.reset(workflow_id)
    return {"status": "reset", "workflow_id": workflow_id}
