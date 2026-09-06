use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

use ai_ex_config::AppConfig;
use ai_ex_domain::AppError;

pub fn save(path: &Path, document: &str, original: Option<&str>) -> Result<(), AppError>
{
    let config = AppConfig::parse(document)?;
    let current = match fs::read_to_string(path)
    {
        Ok(text) => Some(text),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => None,
        Err(error) => return Err(failure(error)),
    };
    if current.as_deref() != original
    {
        return Err(AppError::configuration("configuration changed while setup was open; reopen setup before saving"));
    }
    let path = std::path::absolute(path).map_err(failure)?;
    let parent = path.parent().ok_or_else(|| AppError::configuration("configuration requires a directory"))?;
    fs::create_dir_all(parent).map_err(failure)?;
    let token_path = Path::new(&config.control.token_path);
    if let Some(parent) = token_path.parent().filter(|path| !path.as_os_str().is_empty())
    {
        fs::create_dir_all(parent).map_err(failure)?;
    }
    match OpenOptions::new().write(true).create_new(true).open(token_path)
    {
        Ok(mut file) =>
        {
            let token = format!("{}{}\n", uuid::Uuid::new_v4().simple(), uuid::Uuid::new_v4().simple());
            if let Err(error) = file.write_all(token.as_bytes()).and_then(|()| file.sync_all())
            {
                drop(file);
                let _ignored = fs::remove_file(token_path);
                return Err(failure(error));
            }
        }
        Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists =>
        {
            let token = fs::read_to_string(token_path).map_err(failure)?;
            if token.trim().len() < 32
            {
                return Err(AppError::configuration("existing control token is invalid; it was not replaced"));
            }
        }
        Err(error) => return Err(failure(error)),
    }
    let pending = PendingFile(parent.join(format!(".aiex-setup-{}.tmp", uuid::Uuid::new_v4())));
    let mut file = OpenOptions::new().write(true).create_new(true).open(&pending.0).map_err(failure)?;
    file.write_all(document.as_bytes()).and_then(|()| file.sync_all()).map_err(failure)?;
    drop(file);
    fs::rename(&pending.0, &path).map_err(failure)?;
    Ok(())
}

struct PendingFile(PathBuf);

impl Drop for PendingFile
{
    fn drop(&mut self)
    {
        let _ignored = fs::remove_file(&self.0);
    }
}

fn failure(error: std::io::Error) -> AppError
{
    AppError::configuration(format!("cannot save setup: {error}"))
}
