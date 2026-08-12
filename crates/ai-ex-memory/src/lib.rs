#![forbid(unsafe_code)]

mod record;

use std::io::ErrorKind;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use ai_ex_core::MemoryPort;
use ai_ex_domain::{AppError, ComponentHealth, Message, Role, TurnId};
use async_trait::async_trait;
use record::MemoryRecord;
use tokio::io::AsyncWriteExt;
use tokio::sync::RwLock;
use uuid::Uuid;

pub struct MemoryStore
{
    path: PathBuf,
    records: RwLock<Vec<MemoryRecord>>,
    enabled: bool,
}

impl MemoryStore
{
    pub async fn open(path: impl AsRef<Path>) -> Result<Self, AppError>
    {
        let path = path.as_ref().to_owned();
        let content = match tokio::fs::read_to_string(&path).await
        {
            Ok(content) => content,
            Err(error) if error.kind() == ErrorKind::NotFound => String::new(),
            Err(error) => return Err(AppError::unavailable(error.to_string())),
        };
        let mut records = Vec::new();
        for (line_number, line) in content.lines().enumerate()
        {
            if line.trim().is_empty()
            {
                continue;
            }
            let record = serde_json::from_str(line).map_err(|error| {
                AppError::protocol(format!("invalid memory line {}: {error}", line_number + 1))
            })?;
            records.push(record);
        }
        Ok(Self {
            path,
            records: RwLock::new(records),
            enabled: true,
        })
    }

    pub fn disabled() -> Self
    {
        Self {
            path: PathBuf::new(),
            records: RwLock::new(Vec::new()),
            enabled: false,
        }
    }

    pub async fn len(&self) -> usize
    {
        self.records.read().await.len()
    }

    pub async fn is_empty(&self) -> bool
    {
        self.records.read().await.is_empty()
    }

    pub async fn health(&self) -> ComponentHealth
    {
        if !self.enabled
        {
            return ComponentHealth {
                component: "memory".to_owned(),
                ready: true,
                detail: "disabled".to_owned(),
            };
        }
        ComponentHealth {
            component: "memory".to_owned(),
            ready: true,
            detail: format!("{} record(s)", self.len().await),
        }
    }
}

#[async_trait]
impl MemoryPort for MemoryStore
{
    async fn recall(&self, query: &str, limit: usize) -> Result<Vec<Message>, AppError>
    {
        if !self.enabled
        {
            return Ok(Vec::new());
        }
        let records = self.records.read().await;
        let mut ranked: Vec<_> = records
            .iter()
            .filter_map(|record|
            {
                let score = record.relevance(query);
                (score > 0).then_some((score, record))
            })
            .collect();
        ranked.sort_by_key(|item| std::cmp::Reverse(item.0));
        Ok(ranked
            .into_iter()
            .take(limit)
            .map(|(_score, record)|
            {
                Message::new(
                    Role::System,
                    format!(
                        "Relevant memory — User: {} Assistant: {}",
                        record.user_text,
                        record.assistant_text
                    ),
                )
            })
            .collect())
    }

    async fn remember(
        &mut self,
        turn_id: TurnId,
        user_text: String,
        assistant_text: String,
    ) -> Result<(), AppError>
    {
        if !self.enabled
        {
            return Ok(());
        }
        if let Some(parent) = self.path.parent()
        {
            tokio::fs::create_dir_all(parent)
                .await
                .map_err(|error| AppError::unavailable(error.to_string()))?;
        }
        let record = MemoryRecord {
            id: Uuid::new_v4(),
            turn_id,
            created_ms: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis(),
            user_text,
            assistant_text,
        };
        let mut file = tokio::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)
            .await
            .map_err(|error| AppError::unavailable(error.to_string()))?;
        let line = serde_json::to_string(&record)
            .map_err(|error| AppError::protocol(error.to_string()))?;
        file.write_all(format!("{line}\n").as_bytes())
            .await
            .map_err(|error| AppError::unavailable(error.to_string()))?;
        file.flush()
            .await
            .map_err(|error| AppError::unavailable(error.to_string()))?;
        file.sync_data()
            .await
            .map_err(|error| AppError::unavailable(error.to_string()))?;
        self.records.write().await.push(record);
        Ok(())
    }
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[tokio::test]
    async fn persists_and_recalls_relevant_turns()
    {
        let path = std::env::temp_dir().join(format!("ai-ex-memory-{}.jsonl", Uuid::new_v4()));
        let mut store = MemoryStore::open(&path).await.expect("store opens");
        store
            .remember(
                TurnId::new(),
                "我喜欢草莓蛋糕".to_owned(),
                "我记住了".to_owned(),
            )
            .await
            .expect("turn persisted");
        let results = store.recall("草莓", 3).await.expect("memory recalled");
        assert_eq!(results.len(), 1);

        let reopened = MemoryStore::open(&path).await.expect("store reopens");
        assert_eq!(reopened.len().await, 1);
        tokio::fs::remove_file(&path).await.expect("temporary memory removed");
    }
}
