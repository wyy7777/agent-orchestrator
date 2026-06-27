"""E2E 冒烟测试：端到端工作流创建→任务→执行→完成。"""
from __future__ import annotations

import pytest

# 最小可运行的工作流 YAML
MINIMAL_WORKFLOW_YAML = """
name: E2E冒烟测试
steps:
  - name: 条件判断
    type: condition
    condition: "{trigger_payload.always} > 0"
""".strip()


@pytest.mark.asyncio
async def test_full_lifecycle_condition_only(client):
    """完整生命周期：创建 workflow → 创建 task → 启动 → 检查完成状态。

    使用 condition 步骤（无需 AI API），确保可离线运行。
    """
    # 1. 创建工作流
    wf_resp = await client.post("/api/workflows", json={
        "name": "E2E测试工作流",
        "description": "冒烟测试",
        "yaml_definition": MINIMAL_WORKFLOW_YAML,
    })
    assert wf_resp.status_code == 201, f"创建工作流失败: {wf_resp.text}"
    wf = wf_resp.json()
    assert wf["id"] is not None
    assert wf["name"] == "E2E测试工作流"

    # 2. 创建任务
    task_resp = await client.post("/api/tasks", json={
        "workflow_id": wf["id"],
        "trigger_type": "manual",
        "trigger_payload": {"always": 1},
    })
    assert task_resp.status_code == 201, f"创建任务失败: {task_resp.text}"
    task = task_resp.json()
    assert task["status"] == "pending"
    task_id = task["id"]

    # 3. 启动任务
    start_resp = await client.post(f"/api/tasks/{task_id}/start")
    assert start_resp.status_code == 200, f"启动任务失败: {start_resp.text}"

    # 4. 等待完成（最多 10 秒）
    import asyncio
    for _ in range(20):
        await asyncio.sleep(0.5)
        check_resp = await client.get(f"/api/tasks/{task_id}")
        status = check_resp.json()["status"]
        if status in ("completed", "failed", "rolled_back"):
            break

    # 5. 验证最终状态
    final_resp = await client.get(f"/api/tasks/{task_id}")
    task_data = final_resp.json()
    assert task_data["status"] == "completed", f"任务未完成，状态: {task_data['status']}"
    assert len(task_data["step_executions"]) == 1
    assert task_data["step_executions"][0]["status"] == "completed"
    assert task_data["step_executions"][0]["step_type"] == "condition"


@pytest.mark.asyncio
async def test_workflow_with_script_step(client):
    """测试 script 步骤（无需 AI）。"""
    yaml = """
name: 脚本E2E
steps:
  - name: 执行脚本
    type: script
    config:
      command: echo done
  - name: 结果检查
    type: condition
    condition: "{results.执行脚本.exit_code} == 0"
""".strip()

    # 创建
    wf_resp = await client.post("/api/workflows", json={
        "name": "脚本测试",
        "yaml_definition": yaml,
    })
    assert wf_resp.status_code == 201
    wf_id = wf_resp.json()["id"]

    # 创建并启动任务
    task_resp = await client.post("/api/tasks", json={
        "workflow_id": wf_id,
        "trigger_type": "manual",
    })
    task_id = task_resp.json()["id"]
    await client.post(f"/api/tasks/{task_id}/start")

    # 等待
    import asyncio
    for _ in range(20):
        await asyncio.sleep(0.5)
        check = await client.get(f"/api/tasks/{task_id}")
        if check.json()["status"] in ("completed", "failed"):
            break

    final = await client.get(f"/api/tasks/{task_id}")
    assert final.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_workflow_not_found(client):
    """404 for nonexistent workflow。"""
    resp = await client.get("/api/workflows/nonexistent-id-12345")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_task_not_found(client):
    """404 for nonexistent task。"""
    resp = await client.get("/api/tasks/nonexistent-id-12345")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_health_check(client):
    """Health check endpoint。"""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
