use ai_ex_domain::AppError;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ConversationPolicy
{
    pub system_prompt: String,
    pub history_turn_limit: usize,
    pub memory_recall_limit: usize,
}

impl ConversationPolicy
{
    pub fn validate(&self) -> Result<(), AppError>
    {
        if self.system_prompt.chars().count() > 16_384
        {
            return Err(AppError::configuration(
                "conversation system prompt is too long",
            ));
        }
        if !(1..=128).contains(&self.history_turn_limit)
        {
            return Err(AppError::configuration(
                "conversation history_turn_limit must be between 1 and 128",
            ));
        }
        if self.memory_recall_limit > 64
        {
            return Err(AppError::configuration(
                "conversation memory_recall_limit must not exceed 64",
            ));
        }
        Ok(())
    }
}

impl Default for ConversationPolicy
{
    fn default() -> Self
    {
        Self {
            system_prompt: String::new(),
            history_turn_limit: 12,
            memory_recall_limit: 6,
        }
    }
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn rejects_unbounded_policy_values()
    {
        let policy = ConversationPolicy {
            history_turn_limit: 0,
            ..ConversationPolicy::default()
        };
        assert!(policy.validate().is_err());

        let policy = ConversationPolicy {
            memory_recall_limit: 65,
            ..ConversationPolicy::default()
        };
        assert!(policy.validate().is_err());
    }
}
