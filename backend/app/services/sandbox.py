import asyncio
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


class SandboxManager:
    """Docker 沙箱管理器，为每个任务创建隔离的执行环境。"""

    def __init__(self):
        self._client = None
        self._sandboxes: dict[str, str] = {}  # task_id -> container_id

    def _get_client(self):
        if self._client is None:
            try:
                import docker

                self._client = docker.from_env()
            except Exception as e:
                logger.warning(f"Docker 连接失败: {e}")
        return self._client

    async def create_sandbox(
        self, task_id: str, image: str = "python:3.12-slim"
    ) -> str:
        """为任务创建沙箱容器。"""
        client = self._get_client()
        if not client:
            raise RuntimeError("Docker 不可用")

        container_name = f"sandbox-{task_id[:8]}"
        try:
            container = client.containers.run(
                image,
                name=container_name,
                command="sleep 3600",
                detach=True,
                mem_limit="512m",
                cpu_quota=50000,  # 50% CPU
                network_disabled=True,
                volumes={
                    f"/tmp/sandbox-{task_id[:8]}": {
                        "bind": "/workspace",
                        "mode": "rw",
                    }
                },
                working_dir="/workspace",
            )
            self._sandboxes[task_id] = container.id
            logger.info(f"沙箱已创建: {container_name}")
            return container.id
        except Exception as e:
            logger.error(f"创建沙箱失败: {e}")
            raise

    async def execute_in_sandbox(
        self, task_id: str, command: str, timeout: int = 60
    ) -> dict:
        """在沙箱中执行命令。"""
        client = self._get_client()
        if not client:
            raise RuntimeError("Docker 不可用")

        container_id = self._sandboxes.get(task_id)
        if not container_id:
            raise RuntimeError(f"任务 {task_id} 的沙箱不存在")

        container = client.containers.get(container_id)
        try:
            result = container.exec_run(
                command,
                stdout=True,
                stderr=True,
                workdir="/workspace",
            )
            return {
                "exit_code": result.exit_code,
                "output": result.output.decode("utf-8", errors="replace"),
            }
        except Exception as e:
            return {"exit_code": -1, "output": str(e)}

    async def destroy_sandbox(self, task_id: str):
        """销毁任务的沙箱。"""
        client = self._get_client()
        if not client:
            return

        container_id = self._sandboxes.pop(task_id, None)
        if container_id:
            try:
                container = client.containers.get(container_id)
                container.stop(timeout=5)
                container.remove(force=True)
                logger.info(f"沙箱已销毁: {task_id}")
            except Exception as e:
                logger.warning(f"销毁沙箱失败: {e}")

    async def cleanup_all(self):
        """清理所有沙箱。"""
        for task_id in list(self._sandboxes.keys()):
            await self.destroy_sandbox(task_id)

    def list_sandboxes(self) -> list[dict]:
        """列出所有活跃沙箱。"""
        return [
            {"task_id": tid, "container_id": cid}
            for tid, cid in self._sandboxes.items()
        ]


sandbox_manager = SandboxManager()
