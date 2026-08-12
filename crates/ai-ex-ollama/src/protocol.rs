use ai_ex_domain::{Message, Role};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize)]
pub struct ChatRequest
{
    pub model: String,
    pub messages: Vec<ChatMessage>,
    pub stream: bool,
}

impl ChatRequest
{
    pub fn new(model: String, messages: Vec<Message>) -> Self
    {
        Self {
            model,
            messages: messages.into_iter().map(ChatMessage::from).collect(),
            stream: true,
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ChatMessage
{
    pub role: String,
    pub content: String,
}

impl From<Message> for ChatMessage
{
    fn from(message: Message) -> Self
    {
        let role = match message.role
        {
            Role::System => "system",
            Role::User => "user",
            Role::Assistant => "assistant",
        };
        Self {
            role: role.to_owned(),
            content: message.content,
        }
    }
}

#[derive(Debug, Deserialize)]
pub struct ChatChunk
{
    #[serde(default)]
    pub message: Option<ChatMessage>,
    #[serde(default)]
    pub done: bool,
    #[serde(default)]
    pub error: Option<String>,
}

pub fn drain_lines(buffer: &mut Vec<u8>) -> Vec<Vec<u8>>
{
    let mut lines = Vec::new();
    let mut consumed = 0;
    for (index, byte) in buffer.iter().enumerate()
    {
        if *byte == b'\n'
        {
            let line = buffer[consumed..index].to_vec();
            if !line.iter().all(u8::is_ascii_whitespace)
            {
                lines.push(line);
            }
            consumed = index + 1;
        }
    }
    if consumed > 0
    {
        buffer.drain(..consumed);
    }
    lines
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn retains_partial_ndjson_line()
    {
        let mut buffer = b"{\"done\":false}\n{\"done\"".to_vec();
        let lines = drain_lines(&mut buffer);
        assert_eq!(lines.len(), 1);
        assert_eq!(buffer, b"{\"done\"");
    }
}

