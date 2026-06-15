"""Agent Orchestrator CLI - 一键启动 AI Agent 工作流编排平台"""

import sys
import uvicorn
import typer
from pathlib import Path

app = typer.Typer(
    name="agent-orch",
    help="Agent Orchestrator - AI Agent 工作流编排平台",
    add_completion=False,
)


@app.command()
def start(
    host: str = typer.Option("0.0.0.0", help="监听地址"),
    port: int = typer.Option(8000, help="监听端口"),
    db_path: str = typer.Option(None, help="数据库文件路径（默认 ~/.agent-orch/data.db）"),
    reload: bool = typer.Option(False, help="开发模式：代码变更自动重启"),
    demo: bool = typer.Option(False, help="Demo 模式：自动创建示例工作流和任务"),
):
    """启动 Agent Orchestrator 服务"""
    import os

    if db_path is None:
        data_dir = Path.home() / ".agent-orch"
        data_dir.mkdir(exist_ok=True)
        db_path = str(data_dir / "data.db")

    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

    if demo:
        os.environ["DEMO_MODE"] = "true"
        typer.echo("🎭 Demo 模式已启用 — 将自动创建示例数据")

    static_dir = Path(__file__).parent / "static"
    if not static_dir.exists():
        typer.echo("提示: 未找到前端静态文件，将以纯 API 模式启动")
        typer.echo(f"       前端请访问 http://localhost:{port}/docs 查看 API 文档")

    typer.echo(f"Agent Orchestrator 启动中...")
    typer.echo(f"  地址: http://localhost:{port}")
    typer.echo(f"  数据库: {db_path}")
    typer.echo(f"  API 文档: http://localhost:{port}/docs")
    typer.echo("")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@app.command()
def version():
    """显示版本信息"""
    typer.echo("Agent Orchestrator v1.1.0")


@app.command()
def init(
    workflow_dir: str = typer.Option(".", help="工作流示例文件输出目录"),
):
    """初始化项目，生成示例工作流文件"""
    from app.engine.yaml_parser import EXAMPLE_YAML

    out_dir = Path(workflow_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    example_file = out_dir / "example_workflow.yaml"
    if example_file.exists():
        overwrite = typer.confirm(f"{example_file} 已存在，是否覆盖？")
        if not overwrite:
            raise typer.Abort()

    example_file.write_text(EXAMPLE_YAML, encoding="utf-8")
    typer.echo(f"已生成示例工作流: {example_file}")


def main():
    app()


if __name__ == "__main__":
    main()
