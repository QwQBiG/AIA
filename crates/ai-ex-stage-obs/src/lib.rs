#![forbid(unsafe_code)]

use std::collections::{BTreeSet, VecDeque};
use std::time::{SystemTime, UNIX_EPOCH};

use ai_ex_domain::{AppError, ComponentHealth};
use ai_ex_stage::{StageAction, StageCapability, StageExecutor};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};

pub const OBS_STAGE_SCHEMA_VERSION: u16 = 1;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ObsStageMode
{
    DryRun,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StageRecord
{
    pub schema_version: u16,
    pub sequence: u64,
    pub timestamp_ms: u64,
    pub mode: ObsStageMode,
    pub action: StageAction,
}

pub struct ObsDryRunStage
{
    actions: VecDeque<StageAction>,
    records: VecDeque<StageRecord>,
    capacity: usize,
    sequence: u64,
}

impl ObsDryRunStage
{
    pub fn new(capacity: usize) -> Result<Self, AppError>
    {
        if capacity == 0
        {
            return Err(AppError::configuration(
                "OBS dry-run capacity must be positive",
            ));
        }
        Ok(Self {
            actions: VecDeque::with_capacity(capacity),
            records: VecDeque::with_capacity(capacity),
            capacity,
            sequence: 0,
        })
    }

    pub fn actions(&self) -> impl Iterator<Item = &StageAction>
    {
        self.actions.iter()
    }

    pub fn records(&self) -> impl Iterator<Item = &StageRecord>
    {
        self.records.iter()
    }

    pub fn drain_records(&mut self) -> Vec<StageRecord>
    {
        self.records.drain(..).collect()
    }

    pub fn records_jsonl(&self) -> Result<String, AppError>
    {
        self.records
            .iter()
            .map(|record|
            {
                serde_json::to_string(record).map_err(|error|
                {
                    AppError::protocol(format!("OBS record encode failed: {error}"))
                })
            })
            .collect::<Result<Vec<_>, _>>()
            .map(|lines|
            {
                if lines.is_empty()
                {
                    String::new()
                }
                else
                {
                    format!("{}\n", lines.join("\n"))
                }
            })
    }

    fn record(&mut self, action: StageAction)
    {
        self.sequence = self.sequence.saturating_add(1);
        if self.records.len() == self.capacity
        {
            self.records.pop_front();
        }
        self.records.push_back(StageRecord {
            schema_version: OBS_STAGE_SCHEMA_VERSION,
            sequence: self.sequence,
            timestamp_ms: unix_timestamp_ms(),
            mode: ObsStageMode::DryRun,
            action,
        });
    }
}

#[async_trait]
impl StageExecutor for ObsDryRunStage
{
    fn capabilities(&self) -> BTreeSet<StageCapability>
    {
        BTreeSet::from([
            StageCapability::Hotkey,
            StageCapability::Interrupt,
            StageCapability::Scene,
            StageCapability::Subtitle,
        ])
    }

    async fn health(&self) -> ComponentHealth
    {
        ComponentHealth::ready("obs-dry-run")
    }

    async fn execute(&mut self, action: StageAction) -> Result<(), AppError>
    {
        action.validate()?;
        if matches!(action, StageAction::Stop)
        {
            return self.interrupt().await;
        }
        if !matches!(
            action,
            StageAction::Subtitle { .. }
                | StageAction::Scene { .. }
                | StageAction::Hotkey { .. }
        )
        {
            return Err(AppError::configuration(
                "OBS stage supports subtitle, scene and hotkey actions only",
            ));
        }
        if self.actions.len() >= self.capacity
        {
            return Err(AppError::unavailable("OBS dry-run queue is full"));
        }
        self.record(action.clone());
        self.actions.push_back(action);
        Ok(())
    }

    async fn interrupt(&mut self) -> Result<(), AppError>
    {
        self.actions.clear();
        self.record(StageAction::Stop);
        Ok(())
    }
}

fn unix_timestamp_ms() -> u64
{
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
        .try_into()
        .unwrap_or(u64::MAX)
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[tokio::test]
    async fn records_subtitle_scene_and_hotkey_actions()
    {
        let mut stage = ObsDryRunStage::new(4).expect("OBS stage creates");
        for action in [
            StageAction::Subtitle {
                text: "hello".to_owned(),
                duration_ms: 1_000,
            },
            StageAction::Scene {
                scene: "main".to_owned(),
            },
            StageAction::Hotkey {
                id: "camera".to_owned(),
            },
        ]
        {
            stage.execute(action).await.expect("action records");
        }
        assert_eq!(stage.actions().count(), 3);
        assert_eq!(stage.records().count(), 3);
        assert!(stage.capabilities().contains(&StageCapability::Subtitle));
        assert!(stage.health().await.ready);
    }

    #[tokio::test]
    async fn rejects_non_obs_actions_and_exports_jsonl()
    {
        let mut stage = ObsDryRunStage::new(2).expect("OBS stage creates");
        let error = stage
            .execute(StageAction::Speak {
                turn_id: ai_ex_domain::TurnId::new(),
                text: "hello".to_owned(),
                interruptible: true,
            })
            .await
            .expect_err("OBS must reject speech");
        assert!(error.to_string().contains("OBS"));
        stage
            .execute(StageAction::Subtitle {
                text: "hello".to_owned(),
                duration_ms: 500,
            })
            .await
            .expect("subtitle records");
        let jsonl = stage.records_jsonl().expect("records encode");
        let record: StageRecord = serde_json::from_str(jsonl.trim()).expect("record parses");
        assert_eq!(record.schema_version, OBS_STAGE_SCHEMA_VERSION);
        assert_eq!(record.action.kind(), "subtitle");
    }

    #[tokio::test]
    async fn interrupt_clears_pending_actions_but_keeps_audit_record()
    {
        let mut stage = ObsDryRunStage::new(2).expect("OBS stage creates");
        stage
            .execute(StageAction::Scene {
                scene: "main".to_owned(),
            })
            .await
            .expect("scene records");
        stage.interrupt().await.expect("interrupt records");
        assert_eq!(stage.actions().count(), 0);
        assert_eq!(stage.records().last().unwrap().action.kind(), "stop");
    }
}