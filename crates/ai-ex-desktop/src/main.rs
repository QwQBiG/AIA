#![forbid(unsafe_code)]

mod app;
mod setup;
mod worker;

use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};

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
    let options = parse_options(std::env::args().skip(1))?;
    let setup_result = if options.setup
        || !options.config_path.exists()
        || !control_token_exists(&options.config_path)
    {
        Some(setup::run(options.config_path.clone())?)
    }
    else
    {
        None
    };
    let config_path = setup_result
        .as_ref()
        .map(|result| result.config_path.clone())
        .unwrap_or(options.config_path);
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
    let _service_process = setup_result
        .as_ref()
        .filter(|result| result.start_service)
        .map(|result|
        {
            spawn_service(&config_path, result.api_key.as_deref())
        })
        .transpose()?
        .flatten();
    let worker = spawn_worker(WorkerSettings {
        address: config.control.bind,
        token: token.trim().to_owned(),
        max_message_bytes: config.control.max_message_bytes,
    })?;
    let developer = options.developer;
    let native_options = eframe::NativeOptions {
        viewport: eframe::egui::ViewportBuilder::default()
            .with_inner_size([1_000.0, 720.0])
            .with_min_inner_size([720.0, 520.0]),
        ..Default::default()
    };
    eframe::run_native(
        "AIex",
        native_options,
        Box::new(move |context|
        {
            Ok(Box::new(DesktopApp::new(context, worker, developer)))
        }),
    )
    .map_err(|error| AppError::unavailable(error.to_string()))
}

fn spawn_service(config_path: &Path, api_key: Option<&str>) -> Result<Option<Child>, AppError>
{
    let executable = std::env::current_exe()
        .map_err(|error| AppError::unavailable(format!("cannot locate desktop executable: {error}")))?
        .parent()
        .map(|path| path.join("ai-ex-service.exe"));
    let mut command = if let Some(executable) = executable.filter(|path| path.exists())
    {
        let mut command = Command::new(executable);
        command.arg("--config").arg(config_path);
        command
    }
    else
    {
        let mut command = Command::new("cargo");
        command
            .args(["run", "-p", "ai-ex-service", "--", "--config"])
            .arg(config_path);
        command
    };
    command
        .stdin(Stdio::null())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());
    if let Some(api_key) = api_key
    {
        command.env("DEEPSEEK_API_KEY", api_key);
    }
    let child = command
        .spawn()
        .map_err(|error| AppError::unavailable(format!("cannot start ai-ex-service: {error}")))?;
    Ok(Some(child))
}

fn control_token_exists(config_path: &Path) -> bool
{
    config_path
        .parent()
        .map(|parent| parent.join("control.token").exists())
        .unwrap_or(false)
}

struct LaunchOptions
{
    config_path: PathBuf,
    setup: bool,
    developer: bool,
}

fn parse_options(arguments: impl Iterator<Item = String>) -> Result<LaunchOptions, AppError>
{
    let mut config_path = PathBuf::from("config/ai-ex.local.toml");
    let mut setup = false;
    let mut developer = false;
    let mut arguments = arguments;
    while let Some(argument) = arguments.next()
    {
        match argument.as_str()
        {
            "--config" =>
            {
                config_path = PathBuf::from(arguments.next().ok_or_else(|| {
                    AppError::configuration("--config requires a path")
                })?);
            }
            "--setup" => setup = true,
            "--developer" | "--dev" => developer = true,
            "--help" | "-h" =>
            {
                return Err(AppError::configuration(
                    "usage: ai-ex-desktop [--config PATH] [--setup] [--developer]",
                ));
            }
            _ =>
            {
                return Err(AppError::configuration(format!(
                    "unknown desktop argument: {argument}",
                )));
            }
        }
    }
    Ok(LaunchOptions {
        config_path,
        setup,
        developer,
    })
}
