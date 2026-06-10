"""沙箱功能测试（支持 Docker 和本地两种模式）。"""

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
    # 使用本地模式（不依赖 Docker）
    m._docker_available = False
    return m


@pytest.fixture
def docker_manager():
    m = SandboxManager()
    # 预设 mock client，模拟 Docker 模式
    client, container = _make_mock_docker_client()
    m._client = client
    m._docker_available = True
    return m


# ---- 本地模式单元测试 ----


@pytest.mark.asyncio
async def test_create_local_sandbox(manager):
    sandbox_id = await manager.create_sandbox("test-task-001")

    assert sandbox_id.startswith("local-")
    assert "test-task-001" in manager._sandboxes
    assert manager._sandboxes["test-task-001"]["type"] == "local"


@pytest.mark.asyncio
async def test_execute_in_local_sandbox(manager):
    task_id = "test-task-002"

    await manager.create_sandbox(task_id)
    result = await manager.execute_in_sandbox(task_id, "echo hello")

    assert result["exit_code"] == 0
    assert "hello" in result["output"]


@pytest.mark.asyncio
async def test_destroy_local_sandbox(manager):
    task_id = "test-task-003"

    await manager.create_sandbox(task_id)
    assert task_id in manager._sandboxes

    await manager.destroy_sandbox(task_id)
    assert task_id not in manager._sandboxes


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
    assert items[0]["type"] == "local"


@pytest.mark.asyncio
async def test_sandbox_mode(manager):
    assert manager.mode == "local"


# ---- Docker 模式单元测试 ----


@pytest.mark.asyncio
async def test_create_docker_sandbox(docker_manager):
    container_id = await docker_manager.create_sandbox("test-task-docker")

    assert container_id == "fake_container_id_12345"
    assert "test-task-docker" in docker_manager._sandboxes
    assert docker_manager._sandboxes["test-task-docker"]["type"] == "docker"
    docker_manager._client.containers.run.assert_called_once()


@pytest.mark.asyncio
async def test_execute_in_docker_sandbox(docker_manager):
    task_id = "test-task-docker-exec"

    await docker_manager.create_sandbox(task_id)
    result = await docker_manager.execute_in_sandbox(task_id, "echo hello")

    assert result["exit_code"] == 0
    assert "hello world" in result["output"]


@pytest.mark.asyncio
async def test_docker_mode(docker_manager):
    assert docker_manager.mode == "docker"


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
