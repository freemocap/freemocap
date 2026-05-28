//! FreeMoCap Rust — pipeline test harness + server.
//!
//! IMPORTANT: Always use `cargo run --release` for real performance testing.
//!
//! Usage:
//!   cargo run --release -- --help
//!   cargo run --release -- test all [--data-dir PATH] [--max-frames N]
//!   cargo run --release -- test detect [--data-dir PATH]
//!   cargo run --release -- test pipeline [--data-dir PATH] [--max-frames N]
//!   cargo run --release -- test calibration --calibration PATH
//!   cargo run --release -- test charuco [--data-dir PATH] [--max-frames N]
//!   cargo run --release -- test video [--data-dir PATH] [--max-frames N]
//!   cargo run --release -- test filtering
//!   cargo run --release -- --serve

use clap::Parser;

mod cli;
mod tests;

fn main() -> anyhow::Result<()> {
    if cfg!(debug_assertions) {
        tracing::warn!(
            "WARNING: Running in debug mode. Use `cargo run --release` for full performance.\n"
        );
    }
    freemocap::init_logging(freemocap::DEFAULT_LOG_LEVEL);

    let cli = cli::Cli::parse();
    dispatch_cli(cli)
}

fn dispatch_cli(cli: cli::Cli) -> anyhow::Result<()> {
    if cli.serve {
        return run_server();
    }
    match cli.command {
        Some(cli::Commands::Test { module }) => dispatch_test(module),
        Some(cli::Commands::Serve) => run_server(),
        None => Ok(()),
    }
}

fn dispatch_test(module: cli::TestModule) -> anyhow::Result<()> {
    use cli::TestModule;
    match module {
        TestModule::All(a) => tests::all_tests::run(&a),
        TestModule::Detect(a) => tests::detect_tests::run(&a),
        TestModule::Pipeline(a) => tests::pipeline_tests::run(&a),
        TestModule::Calibration(a) => tests::calibration_tests::run(&a),
        TestModule::Charuco(a) => tests::charuco_tests::run(&a),
        TestModule::Video(a) => tests::video_tests::run(&a),
        TestModule::Filtering(a) => tests::filtering_tests::run(&a),
    }
}

fn run_server() -> anyhow::Result<()> {
    use std::sync::Arc;

    let state = Arc::new(freemocap::api::AppState::new());
    let router = freemocap::api::build_router(state.clone());

    let addr = "0.0.0.0:53118";
    eprintln!("══════════════════════════════════════════════════");
    eprintln!("  FreeMoCap Server");
    eprintln!("  http://localhost:53118");
    eprintln!("  Press Ctrl+C to stop");
    eprintln!("══════════════════════════════════════════════════");

    let rt = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(4)
        .enable_all()
        .build()?;

    rt.block_on(async {
        let listener = tokio::net::TcpListener::bind(addr).await?;

        axum::serve(listener, router)
            .with_graceful_shutdown(async {
                tokio::signal::ctrl_c().await.ok();
                tracing::info!("Shutdown signal received");
            })
            .await?;

        Ok::<_, anyhow::Error>(())
    })?;

    state.camera_manager.blocking_lock().close_all_groups();
    state.pipeline_manager.blocking_lock().shutdown_all();
    eprintln!("Server stopped.");
    Ok(())
}
