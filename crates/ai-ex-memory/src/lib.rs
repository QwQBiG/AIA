#![forbid(unsafe_code)]

mod record;

use std::io::ErrorKind;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use ai_ex_core::MemoryPort;
use ai_ex_domain::{AppError, ComponentHealth, MemoryKind, MemoryProjection, Message, Role, TurnId};
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

    pub async fn count(&self, kind: Option<MemoryKind>) -> usize
    {
        self.records
            .read()
            .await
            .iter()
            .filter(|record| kind.is_none_or(|expected| record.kind == expected))
            .count()
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

    pub async fn recall_kind(
        &self,
        kind: Option<MemoryKind>,
        query: &str,
        limit: usize,
    ) -> Result<Vec<Message>, AppError>
    {
        if !self.enabled
        {
            return Ok(Vec::new());
        }
        let records = self.records.read().await;
        let mut ranked: Vec<_> = records
            .iter()
            .filter(|record| kind.is_none_or(|expected| record.kind == expected))
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
                        "Relevant memory [{}] — User: {} Assistant: {}",
                        record.kind.as_str(),
                        record.user_text,
                        record.assistant_text
                    ),
                )
            })
            .collect())
    }

    pub async fn remember_kind(
        &mut self,
        kind: MemoryKind,
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
            kind,
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

    pub async fn remember_projection(
        &mut self,
        projection: &MemoryProjection,
    ) -> Result<(), AppError>
    {
        self.remember_kind(
            projection.kind,
            projection.turn_id.unwrap_or_default(),
            projection.user_text.clone(),
            projection.assistant_text.clone(),
        )
        .await
    }
    pub async fn export_kind(
        &self,
        kind: Option<MemoryKind>,
        destination: impl AsRef<Path>,
    ) -> Result<usize, AppError>
    {
        let records: Vec<_> = self
            .records
            .read()
            .await
            .iter()
            .filter(|record| kind.is_none_or(|expected| record.kind == expected))
            .cloned()
            .collect();
        let content = serialize_records(&records)?;
        let destination = destination.as_ref();
        if let Some(parent) = destination.parent()
        {
            tokio::fs::create_dir_all(parent)
                .await
                .map_err(|error| AppError::unavailable(error.to_string()))?;
        }
        tokio::fs::write(destination, content)
            .await
            .map_err(|error| AppError::unavailable(error.to_string()))?;
        Ok(records.len())
    }

    pub async fn clear_kind(&mut self, kind: MemoryKind) -> Result<usize, AppError>
    {
        if !self.enabled
        {
            return Ok(0);
        }
        let records = self.records.read().await;
        let retained: Vec<_> = records
            .iter()
            .filter(|record| record.kind != kind)
            .cloned()
            .collect();
        let removed = records.len().saturating_sub(retained.len());
        drop(records);
        if removed == 0
        {
            return Ok(0);
        }
        let content = serialize_records(&retained)?;
        let temporary = self.path.with_extension("jsonl.tmp");
        tokio::fs::write(&temporary, content)
            .await
            .map_err(|error| AppError::unavailable(error.to_string()))?;
        match tokio::fs::remove_file(&self.path).await
        {
            Ok(()) => {}
            Err(error) if error.kind() == ErrorKind::NotFound => {}
            Err(error) => return Err(AppError::unavailable(error.to_string())),
        }
        tokio::fs::rename(&temporary, &self.path)
            .await
            .map_err(|error| AppError::unavailable(error.to_string()))?;
        *self.records.write().await = retained;
        Ok(removed)
    }
}

#[async_trait]
impl MemoryPort for MemoryStore
{
    async fn recall(&self, query: &str, limit: usize) -> Result<Vec<Message>, AppError>
    {
        self.recall_kind(None, query, limit).await
    }

    async fn remember(
        &mut self,
        turn_id: TurnId,
        user_text: String,
        assistant_text: String,
    ) -> Result<(), AppError>
    {
        self.remember_kind(MemoryKind::Conversation, turn_id, user_text, assistant_text)
            .await
    }
}

fn serialize_records(records: &[MemoryRecord]) -> Result<String, AppError>
{
    let mut content = String::new();
    for record in records
    {
        let line = serde_json::to_string(record)
            .map_err(|error| AppError::protocol(error.to_string()))?;
        content.push_str(&line);
        content.push('\n');
    }
    Ok(content)
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

    #[tokio::test]
    async fn filters_exports_and_clears_memory_kinds()
    {
        let path = std::env::temp_dir().join(format!("ai-ex-memory-{}.jsonl", Uuid::new_v4()));
        let export_path = std::env::temp_dir().join(format!("ai-ex-memory-export-{}.jsonl", Uuid::new_v4()));
        let mut store = MemoryStore::open(&path).await.expect("store opens");
        store
            .remember_kind(
                MemoryKind::Viewer,
                TurnId::new(),
                "观众喜欢蓝莓".to_owned(),
                "已记录".to_owned(),
            )
            .await
            .expect("viewer memory persists");
        store
            .remember_kind(
                MemoryKind::Persona,
                TurnId::new(),
                "角色喜欢星星".to_owned(),
                "保持设定".to_owned(),
            )
            .await
            .expect("persona memory persists");
        assert_eq!(store.count(Some(MemoryKind::Viewer)).await, 1);
        assert_eq!(store.recall_kind(Some(MemoryKind::Persona), "星星", 3).await.unwrap().len(), 1);
        assert_eq!(store.export_kind(Some(MemoryKind::Viewer), &export_path).await.unwrap(), 1);
        assert_eq!(store.clear_kind(MemoryKind::Viewer).await.unwrap(), 1);
        assert_eq!(store.count(Some(MemoryKind::Viewer)).await, 0);

        let reopened = MemoryStore::open(&path).await.expect("store reopens");
        assert_eq!(reopened.count(Some(MemoryKind::Persona)).await, 1);
        assert_eq!(reopened.count(Some(MemoryKind::Viewer)).await, 0);
        tokio::fs::remove_file(&path).await.expect("temporary memory removed");
        tokio::fs::remove_file(&export_path).await.expect("temporary export removed");
    }

    #[tokio::test]
    async fn remembers_a_projected_live_event()
    {
        let path = std::env::temp_dir().join(format!("ai-ex-memory-projection-{}.jsonl", Uuid::new_v4()));
        let mut store = MemoryStore::open(&path).await.expect("store opens");
        let projection = MemoryProjection {
            kind: MemoryKind::LiveEvent,
            event_id: Uuid::new_v4(),
            turn_id: None,
            user_text: "收到礼物".to_owned(),
            assistant_text: "直播事件".to_owned(),
        };
        store
            .remember_projection(&projection)
            .await
            .expect("projection persists");
        assert_eq!(store.count(Some(MemoryKind::LiveEvent)).await, 1);
        tokio::fs::remove_file(&path).await.expect("projection memory removed");
    }
    #[tokio::test]
    async fn reads_legacy_records_without_a_kind()
    {
        let path = std::env::temp_dir().join(format!("ai-ex-memory-legacy-{}.jsonl", Uuid::new_v4()));
        let turn_id = serde_json::to_string(&TurnId::new()).expect("turn id serializes");
        let legacy = format!(
            "{{\"id\":\"{}\",\"turn_id\":{},\"created_ms\":1,\"user_text\":\"旧记录\",\"assistant_text\":\"兼容\"}}\n",
            Uuid::new_v4(),
            turn_id,
        );
        tokio::fs::write(&path, legacy).await.expect("legacy memory written");
        let store = MemoryStore::open(&path).await.expect("legacy memory opens");
        assert_eq!(store.count(Some(MemoryKind::Conversation)).await, 1);
        tokio::fs::remove_file(&path).await.expect("legacy memory removed");
    }
}
