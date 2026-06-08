import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_create_workflow(client):
    yaml_def = "name: 测试\nsteps:\n  - name: 分析\n    type: analyze\n"
    resp = await client.post("/api/workflows", json={
        "name": "测试工作流",
        "description": "测试",
        "yaml_definition": yaml_def,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "测试工作流"
    assert data["version"] == 1


@pytest.mark.asyncio
async def test_create_workflow_invalid_yaml(client):
    resp = await client.post("/api/workflows", json={
        "name": "坏工作流",
        "yaml_definition": "name: test\n",  # 缺少 steps
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_workflows(client):
    # 创建一个
    yaml_def = "name: 测试\nsteps:\n  - name: s\n    type: analyze\n"
    await client.post("/api/workflows", json={
        "name": "列表测试",
        "yaml_definition": yaml_def,
    })
    # 列表
    resp = await client.get("/api/workflows")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_create_and_get_task(client):
    # 先创建工作流
    yaml_def = "name: 测试\nsteps:\n  - name: 分析\n    type: analyze\n"
    wf_resp = await client.post("/api/workflows", json={
        "name": "任务测试",
        "yaml_definition": yaml_def,
    })
    wf_id = wf_resp.json()["id"]

    # 创建任务
    task_resp = await client.post("/api/tasks", json={
        "workflow_id": wf_id,
        "trigger_type": "manual",
        "trigger_payload": {"input": "测试输入"},
    })
    assert task_resp.status_code == 201
    task = task_resp.json()
    assert task["status"] == "pending"

    # 获取任务
    get_resp = await client.get(f"/api/tasks/{task['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == task["id"]


@pytest.mark.asyncio
async def test_create_task_invalid_workflow(client):
    resp = await client.post("/api/tasks", json={
        "workflow_id": "nonexistent-id",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_stats(client):
    resp = await client.get("/api/dashboard/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_tasks" in data
    assert "success_rate" in data


@pytest.mark.asyncio
async def test_list_approvals(client):
    resp = await client.get("/api/approvals")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_workflow_crud(client):
    yaml_def = "name: CRUD\nsteps:\n  - name: s\n    type: analyze\n"
    # Create
    create_resp = await client.post("/api/workflows", json={
        "name": "CRUD测试",
        "yaml_definition": yaml_def,
    })
    wf_id = create_resp.json()["id"]

    # Read
    get_resp = await client.get(f"/api/workflows/{wf_id}")
    assert get_resp.json()["name"] == "CRUD测试"

    # Update
    update_resp = await client.put(f"/api/workflows/{wf_id}", json={
        "name": "更新后",
    })
    assert update_resp.json()["name"] == "更新后"

    # Delete
    del_resp = await client.delete(f"/api/workflows/{wf_id}")
    assert del_resp.status_code == 204

    # Verify deleted
    get_resp2 = await client.get(f"/api/workflows/{wf_id}")
    assert get_resp2.status_code == 404
