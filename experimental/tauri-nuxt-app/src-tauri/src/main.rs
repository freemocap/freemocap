// Prevents additional console window on Windows in release, DO NOT REMOVE!!
// #![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{Manager};
// use tauri::WindowEvent;
// use std::process::Child;
// use std::process::Command;

fn main() {
  tauri::Builder::default()
//     .setup(|app| {
//         let child = Command::new("../dist/main-x86_64-pc-windows-msvc.exe")
//             .spawn()
//             .expect("failed to execute child process - main.exe");
//         app.manage(child);
//         Ok(())
//     })
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
