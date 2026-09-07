use std::path::{Path, PathBuf};

use ai_ex_domain::AppError;

pub const MARKER: &str = "AIex.portable";
pub const CONFIG: &str = "data/ai-ex.local.toml";

pub fn root(executable: &Path) -> Option<PathBuf> {
    executable
        .parent()
        .filter(|parent| parent.join(MARKER).is_file())
        .map(Path::to_path_buf)
}

pub fn check(root: &Path) -> Result<(), AppError> {
    for relative in [MARKER, "ai-ex-service.exe", CONFIG] {
        if !root.join(relative).is_file() {
            return Err(AppError::configuration(format!(
                "便携包缺少 {relative}，请重新完整解压程序包。"
            )));
        }
    }
    let marker = std::fs::read_to_string(root.join(MARKER)).map_err(|error| {
        AppError::configuration(format!("cannot read portable marker: {error}"))
    })?;
    if marker.trim() != "1" {
        return Err(AppError::configuration(
            "unsupported portable package version",
        ));
    }
    let config = crate::startup::read_config(&root.join(CONFIG))?;
    if !config.control.enabled {
        return Err(AppError::configuration("便携桌面需要启用本地控制连接。"));
    }
    Ok(())
}

pub fn configured(path: &Path) -> bool {
    let Ok(config) = crate::startup::read_config(path) else {
        return false;
    };
    let credentials_available = config.model.backend != ai_ex_config::ModelBackend::DeepSeek
        || std::env::var(&config.deepseek.api_key_env).is_ok_and(|value| !value.trim().is_empty());
    credentials_available && crate::startup::read_token(&config).is_ok()
}

pub fn service_log(root: &Path) -> Result<std::fs::File, AppError> {
    let directory = root.join("data/logs");
    std::fs::create_dir_all(&directory).map_err(|error| {
        AppError::unavailable(format!("cannot create service log directory: {error}"))
    })?;
    std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(directory.join("service.log"))
        .map_err(|error| AppError::unavailable(format!("cannot open service log: {error}")))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn package_discovery_is_based_on_executable_and_reports_missing_service() {
        let directory =
            std::env::temp_dir().join(format!("companion-package-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&directory).unwrap();
        let executable = directory.join("AIex.exe");
        assert!(root(&executable).is_none());
        std::fs::write(directory.join(MARKER), "1\n").unwrap();
        assert_eq!(root(&executable), Some(directory.clone()));
        assert!(
            check(&directory)
                .unwrap_err()
                .to_string()
                .contains("ai-ex-service.exe")
        );
        std::fs::remove_file(directory.join(MARKER)).unwrap();
        std::fs::remove_dir(directory).unwrap();
    }
}
