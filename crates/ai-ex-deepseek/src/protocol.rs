use ai_ex_domain::{AppError, Message, Role};
use serde_json::{Value, json};

#[derive(Debug, PartialEq, Eq)]
pub enum StreamEvent
{
    Text(String),
    Done,
    Ignore,
}

pub fn request_body(
    model: &str,
    messages: &[Message],
    thinking: bool,
    reasoning_effort: &str,
) -> Value
{
    let messages: Vec<Value> = messages
        .iter()
        .map(|message| {
            let role = match message.role
            {
                Role::System => "system",
                Role::User => "user",
                Role::Assistant => "assistant",
            };
            json!({ "role": role, "content": message.content })
        })
        .collect();
    let mut body = json!({
        "model": model,
        "messages": messages,
        "stream": true,
        "thinking": { "type": if thinking { "enabled" } else { "disabled" } },
    });
    if thinking
    {
        body["reasoning_effort"] = json!(reasoning_effort);
    }
    body
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
        .map_err(|error| AppError::protocol(format!("invalid DeepSeek SSE UTF-8: {error}")))?
        .trim();
    let Some(data) = line.strip_prefix("data:").map(str::trim) else
    {
        return Ok(StreamEvent::Ignore);
    };
    if data == "[DONE]"
    {
        return Ok(StreamEvent::Done);
    }
    let document: Value = serde_json::from_str(data)
        .map_err(|error| AppError::protocol(format!("invalid DeepSeek SSE JSON: {error}")))?;
    if let Some(error) = document.get("error")
    {
        return Err(AppError::protocol(format!("DeepSeek API error: {error}")));
    }
    let text = document
        .get("choices")
        .and_then(|choices| choices.get(0))
        .and_then(|choice| choice.get("delta"))
        .and_then(|delta| delta.get("content"))
        .and_then(Value::as_str);
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
    fn builds_openai_compatible_v4_request()
    {
        let messages = vec![
            Message::new(Role::System, "Be concise"),
            Message::new(Role::User, "Hello"),
        ];
        let body = request_body("deepseek-v4-flash", &messages, false, "high");
        assert_eq!(body["model"], "deepseek-v4-flash");
        assert_eq!(body["messages"][0]["role"], "system");
        assert_eq!(body["thinking"]["type"], "disabled");
        assert!(body.get("reasoning_effort").is_none());
    }

    #[test]
    fn thinking_request_includes_effort()
    {
        let body = request_body(
            "deepseek-v4-pro",
            &[Message::new(Role::User, "Solve")],
            true,
            "max",
        );
        assert_eq!(body["thinking"]["type"], "enabled");
        assert_eq!(body["reasoning_effort"], "max");
    }

    #[test]
    fn parses_content_and_ignores_private_reasoning()
    {
        let content = br#"data: {"choices":[{"delta":{"content":"hello"}}]}"#;
        let reasoning = br#"data: {"choices":[{"delta":{"reasoning_content":"private"}}]}"#;
        assert_eq!(parse_event(content).expect("content"), StreamEvent::Text("hello".to_owned()));
        assert_eq!(parse_event(reasoning).expect("reasoning"), StreamEvent::Ignore);
        assert_eq!(parse_event(b"data: [DONE]").expect("done"), StreamEvent::Done);
    }

    #[test]
    fn drains_split_crlf_sse_lines()
    {
        let mut buffer = b"data: one\r\ndata: two\npartial".to_vec();
        let lines = drain_lines(&mut buffer);
        assert_eq!(lines.len(), 2);
        assert_eq!(buffer, b"partial");
    }
}
