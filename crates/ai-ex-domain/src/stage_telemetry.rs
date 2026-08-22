use serde::{Deserialize, Serialize};

pub const STAGE_TELEMETRY_SCHEMA_VERSION: u16 = 1;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StageActionSummary
{
    pub sequence: u64,
    pub schema_version: u16,
    pub kind: String,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StageSnapshot
{
    pub schema_version: u16,
    pub actions: Vec<StageActionSummary>,
}

impl Default for StageSnapshot
{
    fn default() -> Self
    {
        Self::empty()
    }
}

impl StageSnapshot
{
    pub fn empty() -> Self
    {
        Self {
            schema_version: STAGE_TELEMETRY_SCHEMA_VERSION,
            actions: Vec::new(),
        }
    }
}
