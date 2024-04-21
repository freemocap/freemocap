// Prevents additional console window on Windows in release, DO NOT REMOVE!!
// #![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{Manager};
// use tauri::WindowEvent;
// use std::process::Child;
use std::process::Command;

fn build_sidecar_path() -> String {
    let arch = if cfg!(target_arch = "x86") {
        "i686"
    } else if cfg!(target_arch = "x86_64") {
        "x86_64"
    } else if cfg!(target_arch = "arm") {
        "arm"
    } else if cfg!(target_arch = "aarch64") {
        "aarch64"
    } else {
        panic!("Unsupported architecture");
    };

    let os = if cfg!(target_os = "windows") {
        "pc-windows"
    } else if cfg!(target_os = "macos") {
        "apple-darwin"
    } else if cfg!(target_os = "linux") {
        "unknown-linux"
    } else if cfg!(target_os = "android") {
        "linux-android"
    } else {
        panic!("Unsupported OS");
    };

    let env = if cfg!(target_env = "gnu") {
        "gnu"
    } else if cfg!(target_env = "msvc") {
        "msvc"
    } else {
        ""
    };

    let ext = if cfg!(target_os = "windows") {
        ".exe"
    } else {
        ""
    };

    format!("../dist/main-{}-{}{}{}", arch, os, env, ext) // Constructs the full sidecar path
}

fn main() {
  let sidecar_path = build_sidecar_path();
  println!("Sidecar path: {}", sidecar_path);

  tauri::Builder::default()
    .setup(|app| {
        let child = Command::new(sidecar_path)
            .spawn()
            .expect("failed to execute child process - main");
        app.manage(child);
        Ok(())
    })
//     .on_window_event(|event| match event.event() {
//         WindowEvent::Destroyed => {
//             if let Some(child) = event.window().app_handle().state::<Child>() {
//                 match child.try_wait() {
//                     Ok(None) => {
//                         let _  = child.kill();
//                         }
//                     Ok(Some(_)) | Err(_) => {
//                         // Child already exited
//                     }
//                 }
//             }
//         }
//         _ => {}
//         })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
