use ai_ex_domain::{AppError, Message, Role};
use serde_json::{Value, json};

#[derive(Debug, PartialEq, Eq)]
pub enum StreamEvent
{
    Text(String),
    Done,
    Ignore,
}

pub fn prompt(messages: &[Message]) -> String
{
    let mut output = String::new();
    for message in messages
    {
        let role = match message.role
        {
            Role::System => "System",
            Role::User => "User",
            Role::Assistant => "Assistant",
        };
        output.push_str(role);
        output.push_str(": ");
        output.push_str(&message.content);
        output.push('\n');
    }
    output.push_str("Assistant:");
    output
}

pub fn request_body(
    prompt: String,
    max_context_length: usize,
    max_length: usize,
    temperature: f32,
) -> Value
{
    json!({
        "prompt": prompt,
        "max_context_length": max_context_length,
        "max_length": max_length,
        "temperature": temperature,
        "stream": true,
    })
}

pub fn drain_lines(buffer: &mut Vec<u8>) -> Vec<Vec<u8>>
{
    let mut lines = Vec::new();
    let mut consumed = 0;
    for (index, byte) in buffer.iter().enumerate()
    {
        if *byte == b'\n'
        {
            lines.push(buffer[consumed..index].to_vec());
            consumed = index + 1;
        }
    }
    if consumed > 0
    {
        buffer.drain(..consumed);
    }
    lines
}

pub fn parse_event(line: &[u8]) -> Result<StreamEvent, AppError>
{
    let line = std::str::from_utf8(line)
        .map_err(|error| AppError::protocol(format!("invalid KoboldCpp SSE UTF-8: {error}")))?
        .trim();
    let Some(data) = line.strip_prefix("data:").map(str::trim) else
    {
        return Ok(StreamEvent::Ignore);
    };
    if data == "[DONE]"
    {
        return Ok(StreamEvent::Done);
    }
    let document: Value = serde_json::from_str(data).map_err(|error| {
        AppError::protocol(format!("invalid KoboldCpp SSE JSON: {error}"))
    })?;
    if let Some(error) = document.get("error").and_then(Value::as_str)
    {
        return Err(AppError::protocol(error));
    }
    let text = document
        .get("token")
        .and_then(|token| {
            token
                .as_str()
                .or_else(|| token.get("text").and_then(Value::as_str))
        })
        .or_else(|| {
            document
                .get("results")?
                .get(0)?
                .get("text")?
                .as_str()
        });
    Ok(match text
    {
        Some(text) if !text.is_empty() => StreamEvent::Text(text.to_owned()),
        _ => StreamEvent::Ignore,
    })
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn formats_complete_role_history()
    {
        let messages = vec![
            Message::new(Role::System, "Be concise"),
            Message::new(Role::User, "Hello"),
        ];

        assert_eq!(prompt(&messages), "System: Be concise\nUser: Hello\nAssistant:");
    }

    #[test]
    fn parses_token_shapes_and_done_marker()
    {
        assert_eq!(
            parse_event(br#"data: {"token":{"text":"hi"}}"#).expect("event"),
            StreamEvent::Text("hi".to_owned()),
        );
        assert_eq!(
            parse_event(br#"data: {"results":[{"text":"!"}]}"#).expect("event"),
            StreamEvent::Text("!".to_owned()),
        );
        assert_eq!(parse_event(b"data: [DONE]").expect("done"), StreamEvent::Done);
    }
}
