#![forbid(unsafe_code)]

use std::collections::{BTreeSet, VecDeque};

use ai_ex_domain::{AppError, ComponentHealth, Emotion, TurnId};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};

pub const STAGE_SCHEMA_VERSION: u16 = 1;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum StageAction
{
    Speak {
        turn_id: TurnId,
        text: String,
        interruptible: bool,
    },
    Expression {
        emotion: Emotion,
    },
    Mouth {
        value: f32,
    },
    Subtitle {
        text: String,
        duration_ms: u64,
    },
    Scene {
        scene: String,
    },
    Hotkey {
        id: String,
    },
    Stop,
}

impl StageAction
{
    pub fn kind(&self) -> &'static str
    {
        match self
        {
            Self::Speak { .. } => "speak",
            Self::Expression { .. } => "expression",
            Self::Mouth { .. } => "mouth",
            Self::Subtitle { .. } => "subtitle",
            Self::Scene { .. } => "scene",
            Self::Hotkey { .. } => "hotkey",
            Self::Stop => "stop",
        }
    }

    pub fn required_capability(&self) -> Option<StageCapability>
    {
        match self
        {
            Self::Speak { .. } => Some(StageCapability::Speech),
            Self::Expression { .. } => Some(StageCapability::Expression),
            Self::Mouth { .. } => Some(StageCapability::Mouth),
            Self::Subtitle { .. } => Some(StageCapability::Subtitle),
            Self::Scene { .. } => Some(StageCapability::Scene),
            Self::Hotkey { .. } => Some(StageCapability::Hotkey),
            Self::Stop => None,
        }
    }
    pub fn validate(&self) -> Result<(), AppError>
    {
        match self
        {
            Self::Speak { text, .. } if text.trim().is_empty() =>
            {
                Err(AppError::configuration("stage speak text must not be empty"))
            }
            Self::Speak { text, .. } if text.chars().count() > 4_096 =>
            {
                Err(AppError::configuration("stage speak text is too long"))
            }
            Self::Mouth { value } if !value.is_finite() || !(0.0..=1.0).contains(value) =>
            {
                Err(AppError::configuration("stage mouth value must be between 0 and 1"))
            }
            Self::Subtitle {
                text,
                duration_ms,
            } if text.trim().is_empty() || *duration_ms == 0 =>
            {
                Err(AppError::configuration(
                    "stage subtitle requires text and positive duration",
                ))
            }
            Self::Subtitle { text, .. } if text.chars().count() > 8_192 =>
            {
                Err(AppError::configuration("stage subtitle text is too long"))
            }
            Self::Scene { scene } if scene.trim().is_empty() =>
            {
                Err(AppError::configuration("stage scene must not be empty"))
            }
            Self::Hotkey { id } if id.trim().is_empty() =>
            {
                Err(AppError::configuration("stage hotkey id must not be empty"))
            }
            _ => Ok(()),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StageCapability
{
    Speech,
    Expression,
    Mouth,
    Subtitle,
    Scene,
    Hotkey,
    Interrupt,
}

#[async_trait]
pub trait StageExecutor: Send + Sync
{
    fn capabilities(&self) -> BTreeSet<StageCapability>;

    async fn health(&self) -> ComponentHealth;

    async fn execute(&mut self, action: StageAction) -> Result<(), AppError>;

    async fn interrupt(&mut self) -> Result<(), AppError>;
}

pub struct StageRouter
{
    executors: Vec<Box<dyn StageExecutor>>,
}

impl StageRouter
{
    pub fn new() -> Self
    {
        Self {
            executors: Vec::new(),
        }
    }

    pub fn push<E>(&mut self, executor: E)
    where
        E: StageExecutor + 'static,
    {
        self.executors.push(Box::new(executor));
    }

    pub fn push_box(&mut self, executor: Box<dyn StageExecutor>)
    {
        self.executors.push(executor);
    }
    pub fn len(&self) -> usize
    {
        self.executors.len()
    }

    pub fn is_empty(&self) -> bool
    {
        self.executors.is_empty()
    }
}

impl Default for StageRouter
{
    fn default() -> Self
    {
        Self::new()
    }
}

#[async_trait]
impl StageExecutor for StageRouter
{
    fn capabilities(&self) -> BTreeSet<StageCapability>
    {
        self.executors
            .iter()
            .flat_map(|executor| executor.capabilities())
            .collect()
    }

    async fn health(&self) -> ComponentHealth
    {
        ComponentHealth {
            component: "stage-router".to_owned(),
            ready: !self.executors.is_empty(),
            detail: format!("{} executor(s) configured", self.executors.len()),
        }
    }
    async fn execute(&mut self, action: StageAction) -> Result<(), AppError>
    {
        action.validate()?;
        let Some(capability) = action.required_capability() else
        {
            return self.interrupt().await;
        };
        let mut matched = false;
        for executor in &mut self.executors
        {
            if executor.capabilities().contains(&capability)
            {
                matched = true;
                executor.execute(action.clone()).await?;
            }
        }
        if !matched
        {
            return Err(AppError::unavailable(format!(
                "no stage executor supports {}",
                action.kind(),
            )));
        }
        Ok(())
    }

    async fn interrupt(&mut self) -> Result<(), AppError>
    {
        for executor in &mut self.executors
        {
            executor.interrupt().await?;
        }
        Ok(())
    }
}
pub struct DryRunStage
{
    actions: VecDeque<StageAction>,
    capacity: usize,
}

impl DryRunStage
{
    pub fn new(capacity: usize) -> Result<Self, AppError>
    {
        if capacity == 0
        {
            return Err(AppError::configuration("stage dry-run capacity must be positive"));
        }
        Ok(Self {
            actions: VecDeque::with_capacity(capacity),
            capacity,
        })
    }

    pub fn actions(&self) -> impl Iterator<Item = &StageAction>
    {
        self.actions.iter()
    }

    pub fn len(&self) -> usize
    {
        self.actions.len()
    }

    pub fn is_empty(&self) -> bool
    {
        self.actions.is_empty()
    }
}

#[async_trait]
impl StageExecutor for DryRunStage
{
    fn capabilities(&self) -> BTreeSet<StageCapability>
    {
        BTreeSet::from([
            StageCapability::Expression,
            StageCapability::Hotkey,
            StageCapability::Interrupt,
            StageCapability::Mouth,
            StageCapability::Scene,
            StageCapability::Speech,
            StageCapability::Subtitle,
        ])
    }

    async fn health(&self) -> ComponentHealth
    {
        ComponentHealth {
            component: "stage-dry-run".to_owned(),
            ready: true,
            detail: "actions are recorded without external side effects".to_owned(),
        }
    }

    async fn execute(&mut self, action: StageAction) -> Result<(), AppError>
    {
        action.validate()?;
        if self.actions.len() >= self.capacity
        {
            return Err(AppError::unavailable("stage dry-run queue is full"));
        }
        self.actions.push_back(action);
        Ok(())
    }

    async fn interrupt(&mut self) -> Result<(), AppError>
    {
        self.actions.clear();
        Ok(())
    }
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[tokio::test]
    async fn dry_run_records_valid_actions_and_capabilities()
    {
        let mut stage = DryRunStage::new(4).expect("stage creates");
        stage
            .execute(StageAction::Expression {
                emotion: Emotion::Happy,
            })
            .await
            .expect("expression executes");
        assert!(stage.capabilities().contains(&StageCapability::Expression));
        assert_eq!(stage.actions().next().map(StageAction::kind), Some("expression"));
        assert!(stage.health().await.ready);
    }

    #[tokio::test]
    async fn dry_run_rejects_invalid_actions()
    {
        let mut stage = DryRunStage::new(2).expect("stage creates");
        let error = stage
            .execute(StageAction::Mouth { value: 2.0 })
            .await
            .expect_err("mouth is out of range");
        assert!(error.to_string().contains("mouth"));
        let error = stage
            .execute(StageAction::Speak {
                turn_id: TurnId::new(),
                text: String::new(),
                interruptible: true,
            })
            .await
            .expect_err("empty speech is invalid");
        assert!(error.to_string().contains("speak"));
    }

    #[tokio::test]
    async fn dry_run_queue_is_bounded_and_interruptible()
    {
        let mut stage = DryRunStage::new(1).expect("stage creates");
        stage
            .execute(StageAction::Stop)
            .await
            .expect("stop executes");
        assert!(stage.execute(StageAction::Stop).await.is_err());
        stage.interrupt().await.expect("interrupt executes");
        assert!(stage.is_empty());
    }

    #[test]
    fn actions_round_trip_with_versioned_kind()
    {
        let action = StageAction::Subtitle {
            text: "hello".to_owned(),
            duration_ms: 1_000,
        };
        let encoded = serde_json::json!({
            "schema_version": STAGE_SCHEMA_VERSION,
            "action": action
        });
        let decoded: StageAction =
            serde_json::from_value(encoded["action"].clone()).expect("action parses");
        assert_eq!(decoded, action);
    }
    #[tokio::test]
    async fn router_routes_by_capability_and_broadcasts_interrupt()
    {
        let mut router = StageRouter::new();
        router.push(DryRunStage::new(4).expect("stage creates"));
        assert!(router.capabilities().contains(&StageCapability::Subtitle));
        router
            .execute(StageAction::Subtitle {
                text: "hello".to_owned(),
                duration_ms: 500,
            })
            .await
            .expect("subtitle routes");
        assert!(router.health().await.ready);
        router.interrupt().await.expect("interrupt broadcasts");
    }
}