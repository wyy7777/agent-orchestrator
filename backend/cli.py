"""Agent Orchestrator CLI - 一键启动 AI Agent 工作流编排平台"""

from pathlib import Path

import typer
import uvicorn

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

    typer.echo("Agent Orchestrator 启动中...")
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
    typer.echo("Agent Orchestrator v1.3.0")


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


# ── 插件管理命令 ──

plugin_app = typer.Typer(name="plugin", help="插件管理")
app.add_typer(plugin_app, name="plugin")


@plugin_app.command("list")
def plugin_list():
    """列出所有已安装的插件"""
    from app.engine.plugin import PLUGIN_DIR, list_plugins, load_external_plugins

    load_external_plugins()
    plugins = list_plugins()

    if not plugins:
        typer.echo("暂无已安装的插件")
        typer.echo(f"插件目录: {PLUGIN_DIR}")
        return

    typer.echo(f"已安装 {len(plugins)} 个插件:")
    typer.echo("")
    for p in plugins:
        source = p.get("source", "builtin")
        typer.echo(f"  📦 {p['name']}")
        typer.echo(f"     描述: {p.get('description', '无')}")
        typer.echo(f"     来源: {source}")
        schema = p.get("schema", {})
        fields = schema.get("properties", {})
        if fields:
            typer.echo(f"     配置字段: {', '.join(fields.keys())}")
        typer.echo("")


@plugin_app.command("install")
def plugin_install(
    source: str = typer.Argument(..., help="插件来源：本地 .py 文件路径或 URL"),
    name: str = typer.Option(None, help="插件名称（可选，默认从文件推断）"),
):
    """安装插件（从本地文件或 URL）"""
    import shutil

    from app.engine.plugin import PLUGIN_DIR

    PLUGIN_DIR.mkdir(parents=True, exist_ok=True)

    source_path = Path(source)
    if source_path.exists() and source_path.suffix == ".py":
        # 本地文件安装
        dest = PLUGIN_DIR / source_path.name
        if name:
            dest = PLUGIN_DIR / f"{name}.py"
        shutil.copy2(source_path, dest)
        typer.echo(f"✅ 已安装插件: {dest}")
        typer.echo("   重启服务后生效")
    elif source.startswith("http://") or source.startswith("https://"):
        # URL 安装
        import httpx
        filename = name or source.split("/")[-1]
        if not filename.endswith(".py"):
            filename += ".py"
        dest = PLUGIN_DIR / filename
        typer.echo(f"正在从 {source} 下载插件...")
        try:
            resp = httpx.get(source, follow_redirects=True, timeout=30)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            typer.echo(f"✅ 已安装插件: {dest}")
            typer.echo("   重启服务后生效")
        except Exception as e:
            typer.echo(f"❌ 下载失败: {e}")
            raise typer.Exit(1)
    else:
        typer.echo(f"❌ 不支持的插件来源: {source}")
        typer.echo("   支持: 本地 .py 文件路径 或 HTTP(S) URL")
        raise typer.Exit(1)


@plugin_app.command("uninstall")
def plugin_uninstall(
    name: str = typer.Argument(..., help="插件名称"),
):
    """卸载插件"""
    from app.engine.plugin import PLUGIN_DIR

    plugin_file = PLUGIN_DIR / f"{name}.py"
    if not plugin_file.exists():
        # 尝试直接用 name 匹配
        matches = list(PLUGIN_DIR.glob(f"*{name}*.py"))
        if not matches:
            typer.echo(f"❌ 未找到插件: {name}")
            typer.echo(f"   插件目录: {PLUGIN_DIR}")
            raise typer.Exit(1)
        plugin_file = matches[0]

    confirm = typer.confirm(f"确认卸载插件 {plugin_file.name}？")
    if not confirm:
        raise typer.Abort()

    plugin_file.unlink()
    typer.echo(f"✅ 已卸载插件: {plugin_file.name}")
    typer.echo("   重启服务后生效")


def main():
    app()


if __name__ == "__main__":
    main()
