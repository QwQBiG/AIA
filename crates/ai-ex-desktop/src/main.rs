#![forbid(unsafe_code)]

mod app;
mod worker;

use std::path::PathBuf;

use ai_ex_config::AppConfig;
use ai_ex_domain::AppError;
use app::DesktopApp;
use worker::{WorkerSettings, spawn_worker};

fn main()
{
    if let Err(error) = run()
    {
        eprintln!("AIex desktop failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), AppError>
{
    let config_path = parse_config_path(std::env::args().skip(1))?;
    let content = std::fs::read_to_string(&config_path).map_err(|error| {
        AppError::configuration(format!("cannot read {}: {error}", config_path.display()))
    })?;
    let config = AppConfig::parse(&content)?;
    if !config.control.enabled
    {
        return Err(AppError::configuration(
            "desktop requires control.enabled = true",
        ));
    }
    let token = std::fs::read_to_string(&config.control.token_path).map_err(|error| {
        AppError::configuration(format!(
            "cannot read control token {}: {error}",
            config.control.token_path,
        ))
    })?;
    let worker = spawn_worker(WorkerSettings {
        address: config.control.bind,
        token: token.trim().to_owned(),
        max_message_bytes: config.control.max_message_bytes,
    })?;
    let options = eframe::NativeOptions {
        viewport: eframe::egui::ViewportBuilder::default()
            .with_inner_size([1_000.0, 720.0])
            .with_min_inner_size([720.0, 520.0]),
        ..Default::default()
    };
    eframe::run_native(
        "AIex",
        options,
        Box::new(move |context| Ok(Box::new(DesktopApp::new(context, worker)))),
    )
    .map_err(|error| AppError::unavailable(error.to_string()))
}

fn parse_config_path(arguments: impl Iterator<Item = String>) -> Result<PathBuf, AppError>
{
    let mut arguments = arguments;
    let mut path = PathBuf::from("config/ai-ex.local.toml");
    while let Some(argument) = arguments.next()
    {
        if argument != "--config"
        {
            return Err(AppError::configuration(format!(
                "unknown desktop argument: {argument}",
            )));
        }
        let value = arguments
            .next()
            .ok_or_else(|| AppError::configuration("--config requires a path"))?;
        path = PathBuf::from(value);
    }
    Ok(path)
}
