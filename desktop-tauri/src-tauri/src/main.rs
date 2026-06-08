// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;
use tauri::Manager;
use tauri_plugin_shell::ShellExt;

struct BackendState {
    child: Mutex<Option<tauri_plugin_shell::process::CommandChild>>,
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendState {
            child: Mutex::new(None),
        })
        .setup(|app| {
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

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                // 窗口关闭时杀掉后端进程
                let state = window.state::<BackendState>();
                let mut guard = state.child.lock().unwrap();
                if let Some(child) = guard.take() {
                    let _ = child.kill();
                    println!("后端进程已终止");
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("启动失败");
}
