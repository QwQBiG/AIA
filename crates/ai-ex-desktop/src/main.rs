#![forbid(unsafe_code)]
#![cfg_attr(all(windows, not(debug_assertions)), windows_subsystem = "windows")]

mod app;
mod appearance;
mod appearance_import;
mod character_files;
mod character_library;
mod image_appearance;
mod portable;
mod preview;
mod scene_files;
mod scene_resume;
mod service_process;
mod setup;
mod setup_storage;
mod speech_panel;
mod startup;
mod welcome;
mod worker;

use std::path::PathBuf;

use ai_ex_domain::AppError;
use app::DesktopApp;
use service_process::ManagedService;
use worker::{WorkerSettings, spawn_worker};

fn main() {
    if let Err(error) = run() {
        eprintln!("AIex desktop failed: {error}");
        if !std::env::args().any(|argument| argument == "--check-install") {
            let _ignored = welcome::show_error(error.to_string());
        }
        std::process::exit(1);
    }
}

fn run() -> Result<(), AppError> {
    let arguments: Vec<_> = std::env::args().skip(1).collect();
    let executable =
        std::env::current_exe().map_err(|error| AppError::unavailable(error.to_string()))?;
    if arguments == ["--check-install"] {
        let directory = executable
            .parent()
            .ok_or_else(|| AppError::configuration("executable has no directory"))?;
        portable::check(directory)?;
        println!(
            "{}",
            serde_json::json!({"ready": true, "version": env!("CARGO_PKG_VERSION")})
        );
        return Ok(());
    }
    let show_welcome = arguments.is_empty();
    let mut options = parse_options(arguments.into_iter())?;
    let portable_root = portable::root(&executable).filter(|_| !options.config_explicit);
    if let Some(directory) = &portable_root {
        std::env::set_current_dir(directory).map_err(|error| {
            AppError::configuration(format!("cannot enter portable directory: {error}"))
        })?;
        options.config_path = PathBuf::from(portable::CONFIG);
    }
    if show_welcome {
        match welcome::run(portable::configured(&options.config_path))? {
            Some(welcome::Choice::Preview) => options.preview = true,
            Some(welcome::Choice::Setup) => options.setup = true,
            Some(welcome::Choice::Connect) => {}
            None => return Ok(()),
        }
    }
    if options.preview {
        return preview::run(options.appearance_pack);
    }
    if let Some(directory) = &portable_root {
        portable::check(directory)?;
    }
    let setup_result = if options.setup
        || !options.config_path.exists()
        || (portable_root.is_some() && !portable::configured(&options.config_path))
    {
        let Some(result) = setup::run(options.config_path.clone())? else {
            return Ok(());
        };
        Some(result)
    } else {
        None
    };
    let config_path = setup_result
        .as_ref()
        .map(|result| result.config_path.clone())
        .unwrap_or(options.config_path);
    let config = startup::read_config(&config_path)?;
    if !config.control.enabled {
        return Err(AppError::configuration(
            "desktop requires control.enabled = true",
        ));
    }
    let token = startup::read_token(&config)?;
    let auto_start =
        !options.connect_only && (options.start_service || config.desktop.auto_start_service);
    let managed_service = if auto_start && !startup::service_is_running(&config, &token)? {
        Some(ManagedService::spawn(
            &config_path,
            setup_result
                .as_ref()
                .and_then(|result| result.api_key.as_deref()),
            &config.deepseek.api_key_env,
        )?)
    } else {
        None
    };
    let resume = scene_resume::ResumeLaunch::new(
        &config_path,
        &config.control.bind,
        managed_service.is_some(),
    )?;
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
        Box::new(move |context| {
            Ok(Box::new(DesktopApp::new(
                context, worker, developer, resume,
            )))
        }),
    )
    .map_err(|error| AppError::unavailable(error.to_string()))
}

struct LaunchOptions {
    config_path: PathBuf,
    config_explicit: bool,
    setup: bool,
    developer: bool,
    preview: bool,
    start_service: bool,
    connect_only: bool,
    appearance_pack: Option<PathBuf>,
}

fn parse_options(arguments: impl Iterator<Item = String>) -> Result<LaunchOptions, AppError> {
    let mut config_path = PathBuf::from("config/ai-ex.local.toml");
    let mut config_explicit = false;
    let mut setup = false;
    let mut developer = false;
    let mut preview = false;
    let mut start_service = false;
    let mut connect_only = false;
    let mut appearance_pack = None;
    let mut arguments = arguments;
    while let Some(argument) = arguments.next() {
        match argument.as_str() {
            "--config" => {
                config_explicit = true;
                config_path = PathBuf::from(
                    arguments
                        .next()
                        .ok_or_else(|| AppError::configuration("--config requires a path"))?,
                );
            }
            "--setup" => setup = true,
            "--preview" => preview = true,
            "--appearance-pack" => {
                appearance_pack = Some(PathBuf::from(arguments.next().ok_or_else(|| {
                    AppError::configuration("--appearance-pack requires a manifest path")
                })?));
            }
            "--start-service" => start_service = true,
            "--connect-only" => connect_only = true,
            "--developer" | "--dev" => developer = true,
            "--help" | "-h" => {
                return Err(AppError::configuration(
                    "usage: ai-ex-desktop [--config PATH] [--setup] [--developer] [--start-service | --connect-only] [--preview [--appearance-pack PATH]]",
                ));
            }
            _ => {
                return Err(AppError::configuration(format!(
                    "unknown desktop argument: {argument}",
                )));
            }
        }
    }
    if start_service && connect_only {
        return Err(AppError::configuration(
            "--start-service and --connect-only are mutually exclusive",
        ));
    }
    if appearance_pack.is_some() && !preview {
        return Err(AppError::configuration(
            "--appearance-pack requires --preview",
        ));
    }
    if preview && (setup || start_service || connect_only) {
        return Err(AppError::configuration(
            "--preview cannot be combined with --setup, --start-service, or --connect-only",
        ));
    }
    Ok(LaunchOptions {
        config_path,
        config_explicit,
        setup,
        developer,
        preview,
        start_service,
        connect_only,
        appearance_pack,
    })
}
