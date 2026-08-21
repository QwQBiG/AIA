use serde::{Deserialize, Serialize};

use crate::AppError;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PersonaSnapshot
{
    pub profile_id: String,
    pub revision: u64,
    pub name: String,
    pub system_prompt: String,
    pub tone: String,
    pub taboos: Vec<String>,
    pub live_mode: String,
}

impl Default for PersonaSnapshot
{
    fn default() -> Self
    {
        Self {
            profile_id: "default".to_owned(),
            revision: 1,
            name: "AIex".to_owned(),
            system_prompt: String::new(),
            tone: "warm, concise, and curious".to_owned(),
            taboos: Vec::new(),
            live_mode: "controlled".to_owned(),
        }
    }
}

impl PersonaSnapshot
{
    pub fn validate(&self) -> Result<(), AppError>
    {
        if self.profile_id.trim().is_empty()
            || self.profile_id.chars().count() > 128
            || self.revision == 0
            || self.name.trim().is_empty()
            || self.name.chars().count() > 128
            || self.system_prompt.chars().count() > 16_384
            || self.tone.chars().count() > 512
            || self.taboos.iter().any(|item| item.chars().count() > 512)
            || self.live_mode.chars().count() > 64
        {
            return Err(AppError::configuration("persona snapshot is outside supported bounds"));
        }
        Ok(())
    }

    pub fn compiled_system_prompt(&self) -> String
    {
        let mut prompt = format!("角色名：{}\n语气：{}", self.name, self.tone);
        if !self.system_prompt.trim().is_empty()
        {
            prompt.push('\n');
            prompt.push_str(self.system_prompt.trim());
        }
        if !self.taboos.is_empty()
        {
            prompt.push_str("\n禁忌：");
            prompt.push_str(&self.taboos.join("；"));
        }
        prompt
    }
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn compiles_a_stable_prompt()
    {
        let profile = PersonaSnapshot {
            profile_id: "stream".to_owned(),
            revision: 2,
            name: "小艾".to_owned(),
            system_prompt: "保持简短".to_owned(),
            tone: "温柔".to_owned(),
            taboos: vec!["不要泄露密钥".to_owned()],
            live_mode: "controlled".to_owned(),
        };
        profile.validate().expect("profile validates");
        let prompt = profile.compiled_system_prompt();
        assert!(prompt.contains("小艾"));
        assert!(prompt.contains("不要泄露密钥"));
    }

    #[test]
    fn rejects_zero_revision()
    {
        let profile = PersonaSnapshot {
            revision: 0,
            ..PersonaSnapshot::default()
        };
        assert!(profile.validate().is_err());
    }
}
