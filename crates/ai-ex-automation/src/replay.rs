#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};

use ai_ex_domain::AppError;

use crate::AutomationAction;

pub const AUTOMATION_SCHEMA_VERSION: u16 = 1;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AutomationReplayRecord
{
    pub schema_version: u16,
    pub timestamp_ms: u64,
    pub target: String,
    pub rationale: String,
    pub action: AutomationAction,
}

impl AutomationReplayRecord
{
    pub fn new(
        timestamp_ms: u64,
        target: impl Into<String>,
        rationale: impl Into<String>,
        action: AutomationAction,
    ) -> Self
    {
        Self {
            schema_version: AUTOMATION_SCHEMA_VERSION,
            timestamp_ms,
            target: target.into(),
            rationale: rationale.into(),
            action,
        }
    }

    pub fn validate(&self) -> Result<(), AppError>
    {
        if self.schema_version != AUTOMATION_SCHEMA_VERSION
        {
            return Err(AppError::protocol(format!(
                "unsupported automation schema version {}",
                self.schema_version,
            )));
        }
        if self.target.trim().is_empty()
        {
            return Err(AppError::configuration(
                "automation replay target must not be empty",
            ));
        }
        if self.rationale.trim().is_empty()
        {
            return Err(AppError::configuration(
                "automation replay rationale must not be empty",
            ));
        }
        self.action.validate()
    }
}

pub fn parse_jsonl(input: &str) -> Result<Vec<AutomationReplayRecord>, AppError>
{
    let mut records = Vec::new();
    let mut previous_timestamp = None;
    for (index, line) in input.lines().enumerate()
    {
        if line.trim().is_empty()
        {
            continue;
        }
        let record: AutomationReplayRecord = serde_json::from_str(line).map_err(|error| {
            AppError::protocol(format!(
                "invalid automation replay record at line {}: {error}",
                index + 1,
            ))
        })?;
        record.validate().map_err(|error| {
            AppError::protocol(format!(
                "invalid automation replay record at line {}: {}",
                index + 1,
                error.message,
            ))
        })?;
        if records.len() >= 4_096
        {
            return Err(AppError::configuration(
                "automation replay contains too many records",
            ));
        }

        if let Some(previous) = previous_timestamp
            && record.timestamp_ms < previous
        {
            return Err(AppError::protocol(format!(
                "automation replay timestamps must be nondecreasing at line {}",
                index + 1,
            )));
        }
        previous_timestamp = Some(record.timestamp_ms);
        records.push(record);
    }
    if records.is_empty()
    {
        return Err(AppError::configuration(
            "automation replay file must contain at least one record",
        ));
    }
    Ok(records)
}

#[cfg(test)]
mod tests
{
    use super::*;
    use crate::PointerButton;

    #[test]
    fn parses_versioned_replay_records()
    {
        let record = AutomationReplayRecord::new(
            10,
            "game",
            "inspect state",
            AutomationAction::Click {
                button: PointerButton::Left,
            },
        );
        let encoded = serde_json::to_string(&record).expect("record encodes");
        let parsed = parse_jsonl(&(encoded + "\n")).expect("record parses");
        assert_eq!(parsed, vec![record]);
    }

    #[test]
    fn rejects_bad_version_and_time_order()
    {
        let bad_version = serde_json::json!({
            "schema_version": 99,
            "timestamp_ms": 0,
            "target": "game",
            "rationale": "inspect",
            "action": "capture_screen"
        });
        assert!(parse_jsonl(&bad_version.to_string()).is_err());

        let first = AutomationReplayRecord::new(
            20,
            "game",
            "inspect",
            AutomationAction::CaptureScreen,
        );
        let second = AutomationReplayRecord::new(
            10,
            "game",
            "inspect",
            AutomationAction::CaptureScreen,
        );
        let input = format!(
            "{}\n{}\n",
            serde_json::to_string(&first).expect("first encodes"),
            serde_json::to_string(&second).expect("second encodes"),
        );
        assert!(parse_jsonl(&input).is_err());
    }

    #[test]
    fn rejects_empty_replay()
    {
        assert!(parse_jsonl("\n").is_err());
    }
}
