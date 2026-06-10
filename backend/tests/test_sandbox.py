"""Docker 沙箱功能测试（使用 mock，不实际调用 Docker）。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.sandbox import SandboxManager


def _make_mock_container(container_id="fake_container_id_12345"):
    container = MagicMock()
    container.id = container_id
    container.exec_run.return_value = MagicMock(exit_code=0, output=b"hello world\n")
    return container


def _make_mock_docker_client(container=None):
    if container is None:
        container = _make_mock_container()
    client = MagicMock()
    client.containers.run.return_value = container
    client.containers.get.return_value = container
    return client, container


@pytest.fixture
def manager():
    m = SandboxManager()
    # 预设 mock client，避免 import docker
    client, container = _make_mock_docker_client()
    m._client = client
    return m


# ---- 单元测试 ----


@pytest.mark.asyncio
async def test_create_sandbox(manager):
    container_id = await manager.create_sandbox("test-task-001")

    assert container_id == "fake_container_id_12345"
    assert "test-task-001" in manager._sandboxes
    manager._client.containers.run.assert_called_once()
    call_kwargs = manager._client.containers.run.call_args
    assert call_kwargs.kwargs["mem_limit"] == "512m"
    assert call_kwargs.kwargs["network_disabled"] is True


@pytest.mark.asyncio
async def test_execute_in_sandbox(manager):
    task_id = "test-task-002"

    await manager.create_sandbox(task_id)
    result = await manager.execute_in_sandbox(task_id, "echo hello")

    assert result["exit_code"] == 0
    assert "hello world" in result["output"]
    manager._client.containers.get.return_value.exec_run.assert_called_once()


@pytest.mark.asyncio
async def test_destroy_sandbox(manager):
    task_id = "test-task-003"

    await manager.create_sandbox(task_id)
    assert task_id in manager._sandboxes

    container = manager._client.containers.get.return_value
    await manager.destroy_sandbox(task_id)
    assert task_id not in manager._sandboxes
    container.stop.assert_called_once_with(timeout=5)
    container.remove.assert_called_once_with(force=True)


@pytest.mark.asyncio
async def test_execute_nonexistent_sandbox(manager):
    with pytest.raises(RuntimeError, match="沙箱不存在"):
        await manager.execute_in_sandbox("no-such-task", "echo hi")


@pytest.mark.asyncio
async def test_cleanup_all(manager):
    await manager.create_sandbox("task-a")
    await manager.create_sandbox("task-b")
    assert len(manager._sandboxes) == 2

    await manager.cleanup_all()
    assert len(manager._sandboxes) == 0


@pytest.mark.asyncio
async def test_list_sandboxes(manager):
    assert manager.list_sandboxes() == []

    await manager.create_sandbox("task-x")
    items = manager.list_sandboxes()

    assert len(items) == 1
    assert items[0]["task_id"] == "task-x"
    assert items[0]["container_id"] == "fake_container_id_12345"


@pytest.mark.asyncio
async def test_create_sandbox_docker_unavailable():
    m = SandboxManager()
    m._client = None
    with patch.object(m, "_get_client", return_value=None):
        with pytest.raises(RuntimeError, match="Docker 不可用"):
            await m.create_sandbox("task-fail")


# ---- API 集成测试 ----


@pytest_asyncio.fixture
async def sandbox_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_api_create_sandbox(sandbox_client):
    with patch("app.api.sandboxes.sandbox_manager") as mock_mgr:
        mock_mgr.create_sandbox = AsyncMock(return_value="fake_container_id_12345")

        resp = await sandbox_client.post(
            "/api/sandboxes",
            json={"task_id": "api-task-001", "image": "python:3.12-slim"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["task_id"] == "api-task-001"
        assert data["container_id"] == "fake_container_id_12345"


@pytest.mark.asyncio
async def test_api_list_sandboxes(sandbox_client):
    with patch("app.api.sandboxes.sandbox_manager") as mock_mgr:
        mock_mgr.list_sandboxes.return_value = [
            {"task_id": "t1", "container_id": "c1"},
        ]
        resp = await sandbox_client.get("/api/sandboxes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["task_id"] == "t1"


@pytest.mark.asyncio
async def test_api_execute_in_sandbox(sandbox_client):
    with patch("app.api.sandboxes.sandbox_manager") as mock_mgr:
        mock_mgr.execute_in_sandbox = AsyncMock(
            return_value={"exit_code": 0, "output": "ok"}
        )

        resp = await sandbox_client.post(
            "/api/sandboxes/test-task/execute",
            json={"command": "echo ok", "timeout": 30},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["exit_code"] == 0
        assert data["output"] == "ok"


@pytest.mark.asyncio
async def test_api_destroy_sandbox(sandbox_client):
    with patch("app.api.sandboxes.sandbox_manager") as mock_mgr:
        mock_mgr.destroy_sandbox = AsyncMock(return_value=None)

        resp = await sandbox_client.delete("/api/sandboxes/test-task")
        assert resp.status_code == 204
