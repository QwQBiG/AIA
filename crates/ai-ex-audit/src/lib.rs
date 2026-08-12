#![forbid(unsafe_code)]

use std::path::{Path, PathBuf};

use ai_ex_automation::{AuditRecord, AuditSink};
use ai_ex_domain::{AppError, ComponentHealth};
use async_trait::async_trait;
use tokio::io::AsyncWriteExt;

pub struct JsonlAuditLog
{
    path: PathBuf,
    file: tokio::fs::File,
}

impl JsonlAuditLog
{
    pub async fn open(path: impl AsRef<Path>) -> Result<Self, AppError>
    {
        let path = path.as_ref().to_path_buf();
        if path.as_os_str().is_empty()
        {
            return Err(AppError::configuration("audit path must not be empty"));
        }
        if let Some(parent) = path.parent().filter(|parent| !parent.as_os_str().is_empty())
        {
            tokio::fs::create_dir_all(parent).await.map_err(|error| {
                AppError::unavailable(format!("cannot create audit directory: {error}"))
            })?;
        }
        validate_existing(&path).await?;
        let file = tokio::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)
            .await
            .map_err(|error| AppError::unavailable(format!("cannot open audit log: {error}")))?;
        Ok(Self { path, file })
    }

    pub fn health(&self) -> ComponentHealth
    {
        ComponentHealth {
            component: "automation-audit".to_owned(),
            ready: true,
            detail: self.path.display().to_string(),
        }
    }
}

#[async_trait]
impl AuditSink for JsonlAuditLog
{
    async fn record(&mut self, record: AuditRecord) -> Result<(), AppError>
    {
        let mut bytes = serde_json::to_vec(&record)
            .map_err(|error| AppError::protocol(format!("cannot encode audit record: {error}")))?;
        bytes.push(b'\n');
        self.file
            .write_all(&bytes)
            .await
            .map_err(|error| AppError::unavailable(format!("cannot write audit record: {error}")))?;
        self.file
            .flush()
            .await
            .map_err(|error| AppError::unavailable(format!("cannot flush audit record: {error}")))?;
        self.file
            .sync_data()
            .await
            .map_err(|error| AppError::unavailable(format!("cannot sync audit record: {error}")))
    }
}

async fn validate_existing(path: &Path) -> Result<(), AppError>
{
    let content = match tokio::fs::read_to_string(path).await
    {
        Ok(content) => content,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(()),
        Err(error) =>
        {
            return Err(AppError::unavailable(format!(
                "cannot read existing audit log: {error}",
            )));
        }
    };
    for (index, line) in content.lines().enumerate()
    {
        if line.trim().is_empty()
        {
            continue;
        }
        serde_json::from_str::<AuditRecord>(line).map_err(|error| {
            AppError::protocol(format!("invalid audit record at line {}: {error}", index + 1))
        })?;
    }
    Ok(())
}

#[cfg(test)]
mod tests
{
    use ai_ex_automation::AuditStage;
    use ai_ex_safety::Capability;
    use uuid::Uuid;

    use super::*;

    fn temporary_path() -> PathBuf
    {
        std::env::temp_dir().join(format!("ai-ex-audit-{}.jsonl", Uuid::new_v4()))
    }

    fn record() -> AuditRecord
    {
        AuditRecord {
            action_id: Uuid::new_v4(),
            timestamp_ms: 42,
            stage: AuditStage::Requested,
            capability: Capability::ScreenRead,
            target: "game".to_owned(),
            action: "capture_screen".to_owned(),
            detail: "inspect".to_owned(),
        }
    }

    #[tokio::test]
    async fn persists_and_reopens_a_valid_log()
    {
        let path = temporary_path();
        let expected = record();
        let mut log = JsonlAuditLog::open(&path).await.expect("open audit");
        log.record(expected.clone()).await.expect("record audit");
        drop(log);

        JsonlAuditLog::open(&path).await.expect("reopen valid audit");
        let content = tokio::fs::read_to_string(&path).await.expect("read audit");
        let actual: AuditRecord = serde_json::from_str(content.trim()).expect("parse audit");
        assert_eq!(actual, expected);
        tokio::fs::remove_file(path).await.expect("remove audit");
    }

    #[tokio::test]
    async fn rejects_a_corrupted_existing_log()
    {
        let path = temporary_path();
        tokio::fs::write(&path, b"not-json\n")
            .await
            .expect("write corrupt audit");

        assert!(JsonlAuditLog::open(&path).await.is_err());
        tokio::fs::remove_file(path).await.expect("remove audit");
    }
}
