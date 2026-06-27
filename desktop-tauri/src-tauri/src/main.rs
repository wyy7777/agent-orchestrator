// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;
use tauri::{
    AppHandle, Manager,
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_global_shortcut::GlobalShortcutExt;

struct BackendState {
    child: Mutex<Option<tauri_plugin_shell::process::CommandChild>>,
}

/// 创建系统托盘菜单
fn create_tray_menu(app: &AppHandle) -> tauri::Result<Menu<tauri::Wry>> {
    let show = MenuItem::with_id(app, "show", "打开窗口", true, None::<&str>)?;
    let pending = MenuItem::with_id(app, "pending", "待审批: 加载中...", true, None::<&str>)?;
    let check_update = MenuItem::with_id(app, "check_update", "检查更新", true, None::<&str>)?;
    let version = MenuItem::with_id(app, "version", "v1.2.0", false, None::<&str>)?;
    let separator = MenuItem::with_id(app, "sep1", "", false, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
    Menu::with_items(app, &[&show, &pending, &check_update, &version, &separator, &quit])
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--minimized"]),
        ))
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .manage(BackendState {
            child: Mutex::new(None),
        })
        .setup(|app| {
            // 创建系统托盘
            let menu = create_tray_menu(app.handle())?;
            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("Agent Orchestrator")
                .menu(&menu)
                .on_menu_event(move |app, event| {
                    match event.id().as_ref() {
                        "show" => {
                            if let Some(window) = app.get_webview_window("main") {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                        "check_update" => {
                            // 显示窗口并触发前端检查更新
                            if let Some(window) = app.get_webview_window("main") {
                                let _ = window.show();
                                let _ = window.set_focus();
                                // 通过 evaluate_js 触发前端的更新检查
                                let _ = window.eval("window.dispatchEvent(new CustomEvent('tray-check-update'))");
                            }
                        }
                        "quit" => {
                            // 终止后端进程
                            if let Some(window) = app.get_webview_window("main") {
                                let state = window.state::<BackendState>();
                                let mut guard = state.child.lock().unwrap();
                                if let Some(child) = guard.take() {
                                    let _ = child.kill();
                                }
                            }
                            app.exit(0);
                        }
                        _ => {}
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            // 注册全局快捷键 Ctrl+Shift+O 打开窗口
            let app_handle = app.handle().clone();
            app.global_shortcut().on_shortcut(
                "CmdOrCtrl+Shift+O",
                move |_app, _shortcut, event| {
                    if event.state == tauri_plugin_global_shortcut::ShortcutState::Pressed {
                        if let Some(window) = app_handle.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                },
            )?;

            // 启动 Python 后端 sidecar
            let shell = app.shell();
            let sidecar_command = shell
                .sidecar("agent-orch-backend")
                .expect("sidecar 未找到");

            let (mut rx, child) = sidecar_command.spawn().expect("启动后端失败");

            // 存储子进程引用，用于关闭时 kill
            let state = app.state::<BackendState>();
            *state.child.lock().unwrap() = Some(child);

            // 读取后端输出（用于检测启动成功）
            tauri::async_runtime::spawn(async move {
                use tauri_plugin_shell::process::CommandEvent;
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            let line_str = String::from_utf8_lossy(&line);
                            if line_str.contains("Agent Orchestrator") {
                                println!("后端已启动: {}", line_str.trim());
                            }
                        }
                        CommandEvent::Stderr(line) => {
                            let line_str = String::from_utf8_lossy(&line);
                            eprintln!("后端错误: {}", line_str.trim());
                        }
                        CommandEvent::Terminated(status) => {
                            println!("后端已退出: {:?}", status);
                            break;
                        }
                        _ => {}
                    }
                }
            });

            // 启动时最小化到托盘（如果带 --minimized 参数）
            let args: Vec<String> = std::env::args().collect();
            if args.contains(&"--minimized".to_string()) {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.hide();
                }
            }

            // 定时轮询待审批数量并更新托盘菜单
            let app_handle_poll = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                // 等待后端启动
                tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
                loop {
                    // 发送 HTTP 请求获取待审批数量
                    let count = match reqwest::get("http://127.0.0.1:8000/api/dashboard/stats").await {
                        Ok(resp) => {
                            match resp.json::<serde_json::Value>().await {
                                Ok(data) => data.get("pending_approvals")
                                    .and_then(|v| v.as_u64())
                                    .unwrap_or(0),
                                Err(_) => 0,
                            }
                        }
                        Err(_) => 0,
                    };

                    // 更新托盘菜单文字
                    let label = if count > 0 {
                        format!("待审批: {} 条", count)
                    } else {
                        "待审批: 无".to_string()
                    };
                    if let Some(window) = app_handle_poll.get_webview_window("main") {
                        let _ = window.set_title(&format!("Agent Orchestrator{}", if count > 0 { format!(" ({} 待审批)", count) } else { String::new() }));
                    }
                    // TODO: Tauri 2.11 API changed — tray menu items are no longer accessible
                    // by string ID via try_menu/get_menu_item. The pending count is
                    // still shown in the window title (line above). Re-enable dynamic
                    // tray updates once the new API is adopted.
                    // if let Some(pending_item) = app_handle_poll.menu_item("pending") {
                    //     let _ = pending_item.set_text(&label);
                    // }
                    let _ = label; // suppress unused warning on label
                    println!("托盘待审批更新: {}", label);

                    tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            match event {
                tauri::WindowEvent::CloseRequested { api, .. } => {
                    // 点关闭按钮时隐藏到托盘而不是退出
                    let _ = window.hide();
                    api.prevent_close();
                }
                tauri::WindowEvent::Destroyed => {
                    // 窗口销毁时杀掉后端进程
                    let state = window.state::<BackendState>();
                    let mut guard = state.child.lock().unwrap();
                    if let Some(child) = guard.take() {
                        let _ = child.kill();
                        println!("后端进程已终止");
                    }
                }
                _ => {}
            }
        })
        .run(tauri::generate_context!())
        .expect("启动失败");
}
