from fastapi import APIRouter, HTTPException

from app.schemas.sandbox import (
    SandboxCreate,
    SandboxExecuteRequest,
    SandboxExecuteResponse,
    SandboxListResponse,
    SandboxResponse,
)
from app.services.sandbox import sandbox_manager

router = APIRouter(prefix="/api/sandboxes", tags=["sandboxes"])


@router.post("", response_model=SandboxResponse, status_code=201)
async def create_sandbox(body: SandboxCreate):
    """创建沙箱容器。"""
    try:
        container_id = await sandbox_manager.create_sandbox(body.task_id, body.image)
        return SandboxResponse(task_id=body.task_id, container_id=container_id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建沙箱失败: {e}")


@router.get("", response_model=SandboxListResponse)
async def list_sandboxes():
    """列出所有活跃沙箱。"""
    items = sandbox_manager.list_sandboxes()
    return SandboxListResponse(
        items=[SandboxResponse(**s) for s in items],
        total=len(items),
    )


@router.post(
    "/{task_id}/execute",
    response_model=SandboxExecuteResponse,
)
async def execute_in_sandbox(task_id: str, body: SandboxExecuteRequest):
    """在沙箱中执行命令。"""
    try:
        result = await sandbox_manager.execute_in_sandbox(
            task_id, body.command, body.timeout
        )
        return SandboxExecuteResponse(**result)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行失败: {e}")


@router.delete("/{task_id}", status_code=204)
async def destroy_sandbox(task_id: str):
    """销毁沙箱。"""
    await sandbox_manager.destroy_sandbox(task_id)
