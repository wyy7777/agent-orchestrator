import asyncio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class SandboxManager:
    """沙箱管理器，支持 Docker 容器和本地进程两种模式。"""

    def __init__(self):
        self._client = None
        self._sandboxes: dict[str, dict] = {}  # task_id -> sandbox info
        self._docker_available = None

    def _check_docker(self) -> bool:
        """检查 Docker 是否可用。"""
        if self._docker_available is None:
            try:
                import docker
                client = docker.from_env()
                client.ping()
                self._docker_available = True
                self._client = client
                logger.info("Docker 可用，使用容器模式")
            except Exception as e:
                self._docker_available = False
                logger.warning(f"Docker 不可用，使用本地模式: {e}")
        return self._docker_available

    async def create_sandbox(
        self, task_id: str, image: str = "python:3.12-slim"
    ) -> str:
        """创建沙箱。Docker 可用时使用容器，否则使用本地目录。"""
        sandbox_id = f"sandbox-{task_id[:8]}"
        workspace = Path(tempfile.gettempdir()) / sandbox_id
        workspace.mkdir(parents=True, exist_ok=True)

        if self._check_docker():
            return await self._create_docker_sandbox(task_id, image, workspace)
        else:
            return await self._create_local_sandbox(task_id, workspace)

    async def _create_docker_sandbox(
        self, task_id: str, image: str, workspace: Path
    ) -> str:
        """创建 Docker 容器沙箱。"""
        container_name = f"sandbox-{task_id[:8]}"
        try:
            container = self._client.containers.run(
                image,
                name=container_name,
                command="sleep 3600",
                detach=True,
                mem_limit="512m",
                cpu_quota=50000,
                network_disabled=True,
                volumes={str(workspace): {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
            )
            self._sandboxes[task_id] = {
                "type": "docker",
                "container_id": container.id,
                "workspace": str(workspace),
            }
            logger.info(f"Docker 沙箱已创建: {container_name}")
            return container.id
        except Exception as e:
            logger.error(f"创建 Docker 沙箱失败: {e}")
            raise

    async def _create_local_sandbox(self, task_id: str, workspace: Path) -> str:
        """创建本地沙箱（进程隔离）。"""
        sandbox_id = f"local-{task_id[:8]}"
        self._sandboxes[task_id] = {
            "type": "local",
            "sandbox_id": sandbox_id,
            "workspace": str(workspace),
        }
        logger.info(f"本地沙箱已创建: {sandbox_id} (工作目录: {workspace})")
        return sandbox_id

    async def execute_in_sandbox(
        self, task_id: str, command: str, timeout: int = 60
    ) -> dict:
        """在沙箱中执行命令。"""
        sandbox = self._sandboxes.get(task_id)
        if not sandbox:
            raise RuntimeError(f"任务 {task_id} 的沙箱不存在")

        if sandbox["type"] == "docker":
            return await self._execute_in_docker(sandbox, command, timeout)
        else:
            return await self._execute_in_local(sandbox, command, timeout)

    async def _execute_in_docker(
        self, sandbox: dict, command: str, timeout: int
    ) -> dict:
        """在 Docker 容器中执行命令。"""
        try:
            container = self._client.containers.get(sandbox["container_id"])
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

    async def _execute_in_local(
        self, sandbox: dict, command: str, timeout: int
    ) -> dict:
        """在本地进程中执行命令。"""
        workspace = sandbox["workspace"]
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except TimeoutError:
                process.kill()
                return {"exit_code": -1, "output": f"命令执行超时 (>{timeout}s)"}

            output = stdout.decode("utf-8", errors="replace")
            if stderr:
                output += "\n" + stderr.decode("utf-8", errors="replace")

            return {
                "exit_code": process.returncode or 0,
                "output": output,
            }
        except Exception as e:
            return {"exit_code": -1, "output": str(e)}

    async def destroy_sandbox(self, task_id: str):
        """销毁沙箱。"""
        sandbox = self._sandboxes.pop(task_id, None)
        if not sandbox:
            return

        if sandbox["type"] == "docker":
            try:
                container = self._client.containers.get(sandbox["container_id"])
                container.stop(timeout=5)
                container.remove(force=True)
                logger.info(f"Docker 沙箱已销毁: {task_id}")
            except Exception as e:
                logger.warning(f"销毁 Docker 沙箱失败: {e}")
        else:
            logger.info(f"本地沙箱已销毁: {task_id}")

    async def cleanup_all(self):
        """清理所有沙箱。"""
        for task_id in list(self._sandboxes.keys()):
            await self.destroy_sandbox(task_id)

    def list_sandboxes(self) -> list[dict]:
        """列出所有活跃沙箱。"""
        result = []
        for tid, sandbox in self._sandboxes.items():
            info = {"task_id": tid, "type": sandbox["type"]}
            if sandbox["type"] == "docker":
                info["container_id"] = sandbox["container_id"]
            else:
                info["sandbox_id"] = sandbox["sandbox_id"]
            info["workspace"] = sandbox["workspace"]
            result.append(info)
        return result

    @property
    def mode(self) -> str:
        """当前沙箱模式。"""
        return "docker" if self._docker_available else "local"


sandbox_manager = SandboxManager()
