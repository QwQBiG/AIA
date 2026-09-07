use std::net::{SocketAddr, TcpStream};
use std::path::Path;
use std::time::Duration;

use ai_ex_config::AppConfig;
use ai_ex_control::{ControlClient, ControlCommand, ControlPayload};
use ai_ex_domain::AppError;

pub fn read_config(path: &Path) -> Result<AppConfig, AppError> {
    let content = std::fs::read_to_string(path).map_err(|error| {
        AppError::configuration(format!("cannot read {}: {error}", path.display()))
    })?;
    AppConfig::parse(&content)
}

pub fn read_token(config: &AppConfig) -> Result<String, AppError> {
    let token = std::fs::read_to_string(&config.control.token_path).map_err(|error| {
        AppError::configuration(format!(
            "cannot read configured control token {}: {error}; repair the file or reopen --setup",
            config.control.token_path
        ))
    })?;
    let token = token.trim().to_owned();
    ControlClient::new(
        &config.control.bind,
        token.clone(),
        config.control.max_message_bytes,
    )?;
    Ok(token)
}

pub fn service_is_running(config: &AppConfig, token: &str) -> Result<bool, AppError> {
    let client = ControlClient::new(
        &config.control.bind,
        token,
        config.control.max_message_bytes,
    )?;
    let address: SocketAddr =
        config.control.bind.parse().map_err(|error| {
            AppError::configuration(format!("invalid control address: {error}"))
        })?;
    match TcpStream::connect_timeout(&address, Duration::from_millis(500)) {
        Ok(connection) => drop(connection),
        Err(error)
            if matches!(
                error.kind(),
                std::io::ErrorKind::ConnectionRefused | std::io::ErrorKind::TimedOut
            ) =>
        {
            // Windows can time out before reporting a refused loopback connection.
            // A successful bind proves there is no listener to authenticate.
            match std::net::TcpListener::bind(address) {
                Ok(reservation) => {
                    drop(reservation);
                    return Ok(false);
                }
                Err(bind_error) => {
                    return Err(AppError::connectivity(format!(
                        "control address is unavailable: {bind_error}; connection probe: {error}"
                    )));
                }
            }
        }
        Err(error) => {
            return Err(AppError::connectivity(format!(
                "cannot check existing service: {error}"
            )));
        }
    }
    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|error| {
            AppError::unavailable(format!("cannot verify existing service: {error}"))
        })?;
    match runtime.block_on(client.send(ControlCommand::Status)) {
        Ok(ControlPayload::Snapshot(_)) => Ok(true),
        Ok(_) => Err(AppError::protocol(
            "control address is occupied but did not return a service snapshot",
        )),
        Err(error) => Err(AppError::connectivity(format!(
            "control address is occupied; existing service could not be authenticated: {error}"
        ))),
    }
}

#[cfg(test)]
#[path = "startup_tests.rs"]
mod tests;
