#![forbid(unsafe_code)]

mod legacy;

use std::path::{Path, PathBuf};

use ai_ex_domain::AppError;
use legacy::LegacyConfig;
use tokio::io::AsyncWriteExt;
use uuid::Uuid;

#[tokio::main]
async fn main()
{
    if let Err(error) = run().await
    {
        eprintln!("AIex migration failed: {error}");
        std::process::exit(1);
    }
}

async fn run() -> Result<(), AppError>
{
    let (input, output) = parse_args(std::env::args().skip(1))?;
    if tokio::fs::try_exists(&output)
        .await
        .map_err(|error| AppError::unavailable(format!("cannot inspect output path: {error}")))?
    {
        return Err(AppError::configuration(format!(
            "refusing to overwrite existing output {}",
            output.display(),
        )));
    }
    let content = tokio::fs::read_to_string(&input).await.map_err(|error| {
        AppError::configuration(format!("cannot read {}: {error}", input.display()))
    })?;
    let legacy: LegacyConfig = serde_json::from_str(&content)
        .map_err(|error| AppError::configuration(format!("invalid legacy JSON: {error}")))?;
    let migration = legacy.migrate();
    migration.config.validate()?;
    let output_content = toml::to_string_pretty(&migration.config)
        .map_err(|error| AppError::protocol(format!("cannot encode migrated TOML: {error}")))?;
    write_new_atomic(&output, output_content.as_bytes()).await?;
    println!("Migrated configuration written to {}", output.display());
    for warning in migration.warnings
    {
        eprintln!("warning: {warning}");
    }
    Ok(())
}

fn parse_args(arguments: impl Iterator<Item = String>) -> Result<(PathBuf, PathBuf), AppError>
{
    let mut arguments = arguments;
    let mut input = PathBuf::from("config.json");
    let mut output = PathBuf::from("config/ai-ex.local.toml");
    while let Some(argument) = arguments.next()
    {
        let value = arguments
            .next()
            .ok_or_else(|| AppError::configuration(format!("{argument} requires a path")))?;
        match argument.as_str()
        {
            "--input" => input = PathBuf::from(value),
            "--output" => output = PathBuf::from(value),
            _ =>
            {
                return Err(AppError::configuration(format!(
                    "unknown migration argument: {argument}",
                )));
            }
        }
    }
    Ok((input, output))
}

async fn write_new_atomic(path: &Path, content: &[u8]) -> Result<(), AppError>
{
    if let Some(parent) = path.parent().filter(|parent| !parent.as_os_str().is_empty())
    {
        tokio::fs::create_dir_all(parent).await.map_err(|error| {
            AppError::unavailable(format!("cannot create output directory: {error}"))
        })?;
    }
    let file_name = path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| AppError::configuration("output path requires a valid file name"))?;
    let temporary = path.with_file_name(format!(".{file_name}.{}.tmp", Uuid::new_v4()));
    let mut file = tokio::fs::OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&temporary)
        .await
        .map_err(|error| AppError::unavailable(format!("cannot create temporary output: {error}")))?;
    let result = async
    {
        file.write_all(content).await?;
        file.flush().await?;
        file.sync_data().await?;
        drop(file);
        tokio::fs::rename(&temporary, path).await
    }
    .await;
    if let Err(error) = result
    {
        let _ignored = tokio::fs::remove_file(&temporary).await;
        return Err(AppError::unavailable(format!("cannot commit migrated config: {error}")));
    }
    Ok(())
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn parses_explicit_paths()
    {
        let (input, output) = parse_args(
            ["--input", "old.json", "--output", "new.toml"]
                .into_iter()
                .map(str::to_owned),
        )
        .expect("arguments parse");

        assert_eq!(input, PathBuf::from("old.json"));
        assert_eq!(output, PathBuf::from("new.toml"));
    }

    #[test]
    fn rejects_unknown_argument()
    {
        assert!(parse_args(["--force", "yes"].into_iter().map(str::to_owned)).is_err());
    }
}
