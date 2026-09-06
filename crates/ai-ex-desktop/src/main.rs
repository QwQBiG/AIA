#![forbid(unsafe_code)]

mod app;
mod character_files;
mod scene_files;
mod scene_resume;
mod appearance;
mod appearance_import;
mod image_appearance;
mod preview;
mod service_process;
mod setup;
mod setup_storage;
mod startup;
mod worker;

use std::path::PathBuf;

use ai_ex_domain::AppError;
use app::DesktopApp;
use service_process::ManagedService;
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
    if options.preview
    {
        return preview::run(options.appearance_pack);
    }
    let setup_result = if options.setup
        || !options.config_path.exists()
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
    let config = startup::read_config(&config_path)?;
    if !config.control.enabled
    {
        return Err(AppError::configuration(
            "desktop requires control.enabled = true",
        ));
    }
    let token = startup::read_token(&config)?;
    let auto_start = !options.connect_only && (options.start_service || config.desktop.auto_start_service);
    let managed_service = if auto_start && !startup::service_is_running(&config, &token)?
    {
        Some(ManagedService::spawn(
            &config_path,
            setup_result.as_ref().and_then(|result| result.api_key.as_deref()),
            &config.deepseek.api_key_env,
        )?)
    }
    else
    {
        None
    };
    let resume = scene_resume::ResumeLaunch::new(&config_path, &config.control.bind, managed_service.is_some())?;
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
            Ok(Box::new(DesktopApp::new(context, worker, developer, resume)))
        }),
    )
    .map_err(|error| AppError::unavailable(error.to_string()))
}

struct LaunchOptions
{
    config_path: PathBuf,
    setup: bool,
    developer: bool,
    preview: bool,
    start_service: bool,
    connect_only: bool,
    appearance_pack: Option<PathBuf>,
}

fn parse_options(arguments: impl Iterator<Item = String>) -> Result<LaunchOptions, AppError>
{
    let mut config_path = PathBuf::from("config/ai-ex.local.toml");
    let mut setup = false;
    let mut developer = false;
    let mut preview = false;
    let mut start_service = false;
    let mut connect_only = false;
    let mut appearance_pack = None;
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
            "--preview" => preview = true,
            "--appearance-pack" =>
            {
                appearance_pack = Some(PathBuf::from(arguments.next().ok_or_else(||
                    AppError::configuration("--appearance-pack requires a manifest path"))?));
            }
            "--start-service" => start_service = true,
            "--connect-only" => connect_only = true,
            "--developer" | "--dev" => developer = true,
            "--help" | "-h" =>
            {
                return Err(AppError::configuration(
                    "usage: ai-ex-desktop [--config PATH] [--setup] [--developer] [--start-service | --connect-only] [--preview [--appearance-pack PATH]]",
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
    if start_service && connect_only
    {
        return Err(AppError::configuration("--start-service and --connect-only are mutually exclusive"));
    }
    if appearance_pack.is_some() && !preview
    {
        return Err(AppError::configuration("--appearance-pack requires --preview"));
    }
    if preview && (setup || start_service || connect_only)
    {
        return Err(AppError::configuration("--preview cannot be combined with --setup, --start-service, or --connect-only"));
    }
    Ok(LaunchOptions {
        config_path,
        setup,
        developer,
        preview,
        start_service,
        connect_only,
        appearance_pack,
    })
}
