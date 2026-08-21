#![forbid(unsafe_code)]

mod protocol;
use std::sync::Arc;
use std::time::Duration;

use ai_ex_core::{LanguageModelPort, ModelRequest};
use ai_ex_domain::{AppError, ComponentHealth, TurnId};
use async_trait::async_trait;
use futures_util::StreamExt;
use protocol::{StreamEvent, drain_lines, parse_event, request_body};
use tokio::sync::{Mutex, mpsc};
use tokio::task::AbortHandle;

pub struct DeepSeekSettings
{
    pub base_url: String,
    pub model: String,
    pub api_key: String,
    pub timeout: Duration,
    pub thinking: bool,
    pub reasoning_effort: String,
}

pub struct DeepSeekClient
{
    client: reqwest::Client,
    settings: DeepSeekSettings,
    active_turn: Arc<Mutex<Option<TurnId>>>,
    abort_handle: Option<AbortHandle>,
}

impl DeepSeekClient
{
    pub fn new(mut settings: DeepSeekSettings) -> Result<Self, AppError>
    {
        if !settings.base_url.starts_with("http://")
            && !settings.base_url.starts_with("https://")
        {
            return Err(AppError::configuration(
                "DeepSeek base_url must be HTTP or HTTPS",
            ));
        }
        if settings.model.trim().is_empty()
            || settings.api_key.trim().is_empty()
            || settings.timeout.is_zero()
        {
            return Err(AppError::configuration(
                "DeepSeek model, API key, and timeout are required",
            ));
        }
        if !matches!(settings.reasoning_effort.as_str(), "high" | "max")
        {
            return Err(AppError::configuration(
                "DeepSeek reasoning_effort must be high or max",
            ));
        }
        settings.base_url = settings.base_url.trim_end_matches('/').to_owned();
        let client = reqwest::Client::builder()
            .timeout(settings.timeout)
            .build()
            .map_err(|error| AppError::configuration(error.to_string()))?;
        Ok(Self {
            client,
            settings,
            active_turn: Arc::new(Mutex::new(None)),
            abort_handle: None,
        })
    }

    pub async fn health(&self) -> ComponentHealth
    {
        let url = format!("{}/models", self.settings.base_url);
        match self
            .client
            .get(url)
            .bearer_auth(&self.settings.api_key)
            .send()
            .await
        {
            Ok(response) if response.status().is_success() => ComponentHealth {
                component: "deepseek".to_owned(),
                ready: true,
                detail: format!("API 可用；configured model={}", self.settings.model),
            },
            Ok(response) => ComponentHealth::unavailable(
                "deepseek",
                http_failure_detail(response.status().as_u16()),
            ),
            Err(error) => ComponentHealth::unavailable(
                "deepseek",
                request_failure_detail(&error),
            ),
        }
    }
}

fn http_failure_detail(status: u16) -> String
{
    match status
    {
        401 | 403 => format!("鉴权失败（HTTP {status}）；检查 DeepSeek API Key"),
        404 => "接口地址不存在（HTTP 404）；检查 base_url 是否为 DeepSeek API 地址".to_owned(),
        408 | 429 => format!("请求受限（HTTP {status}）；检查限流、余额或稍后重试"),
        500..=599 => format!("DeepSeek 服务端故障（HTTP {status}）；稍后重试"),
        _ => format!("DeepSeek 返回 HTTP {status}"),
    }
}

fn request_failure_detail(error: &reqwest::Error) -> String
{
    if error.is_timeout()
    {
        "请求超时；检查网络、代理和 timeout_seconds".to_owned()
    }
    else if error.is_connect()
    {
        "无法连接 DeepSeek；检查网络、代理和 base_url".to_owned()
    }
    else
    {
        format!("DeepSeek 请求失败：{error}")
    }
}
#[async_trait]
impl LanguageModelPort for DeepSeekClient
{
    async fn stream(
        &mut self,
        request: ModelRequest,
    ) -> Result<mpsc::Receiver<Result<String, AppError>>, AppError>
    {
        let mut active_turn = self.active_turn.lock().await;
        if active_turn.is_some()
        {
            return Err(AppError::invalid_transition(
                "a DeepSeek turn is already active",
            ));
        }
        *active_turn = Some(request.turn_id);
        drop(active_turn);

        let (sender, receiver) = mpsc::channel(64);
        let client = self.client.clone();
        let url = format!("{}/chat/completions", self.settings.base_url);
        let api_key = self.settings.api_key.clone();
        let body = request_body(
            &self.settings.model,
            &request.messages,
            self.settings.thinking,
            &self.settings.reasoning_effort,
        );
        let active_turn = Arc::clone(&self.active_turn);
        let task = tokio::spawn(async move
        {
            if let Err(error) = execute_stream(client, url, api_key, body, sender.clone()).await
            {
                let _ignored = sender.send(Err(error)).await;
            }
            *active_turn.lock().await = None;
        });
        self.abort_handle = Some(task.abort_handle());
        Ok(receiver)
    }

    async fn cancel(&mut self, turn_id: TurnId) -> Result<(), AppError>
    {
        let mut active_turn = self.active_turn.lock().await;
        if *active_turn != Some(turn_id)
        {
            return Err(AppError::invalid_transition(
                "cannot cancel an inactive DeepSeek turn",
            ));
        }
        if let Some(handle) = self.abort_handle.take()
        {
            handle.abort();
        }
        *active_turn = None;
        Ok(())
    }
}
async fn execute_stream(
    client: reqwest::Client,
    url: String,
    api_key: String,
    body: serde_json::Value,
    sender: mpsc::Sender<Result<String, AppError>>,
) -> Result<(), AppError>
{
    let response = client
        .post(url)
        .bearer_auth(api_key)
        .json(&body)
        .send()
        .await
        .map_err(|error| AppError::connectivity(error.to_string()))?
        .error_for_status()
        .map_err(|error| AppError::connectivity(error.to_string()))?;
    let mut stream = response.bytes_stream();
    let mut buffer = Vec::new();
    while let Some(next) = stream.next().await
    {
        let bytes = next.map_err(|error| AppError::connectivity(error.to_string()))?;
        buffer.extend_from_slice(&bytes);
        for line in drain_lines(&mut buffer)
        {
            if process_event(&line, &sender).await?
            {
                return Ok(());
            }
        }
    }
    if !buffer.iter().all(u8::is_ascii_whitespace)
    {
        process_event(&buffer, &sender).await?;
    }
    Ok(())
}

async fn process_event(
    line: &[u8],
    sender: &mpsc::Sender<Result<String, AppError>>,
) -> Result<bool, AppError>
{
    match parse_event(line)?
    {
        StreamEvent::Text(text) =>
        {
            sender
                .send(Ok(text))
                .await
                .map_err(|_| AppError::unavailable("conversation receiver closed"))?;
            Ok(false)
        }
        StreamEvent::Done => Ok(true),
        StreamEvent::Ignore => Ok(false),
    }
}
#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn classifies_auth_and_server_failures()
    {
        assert!(http_failure_detail(401).contains("鉴权失败"));
        assert!(http_failure_detail(503).contains("服务端故障"));
    }

    #[test]
    fn classifies_network_failures()
    {
        let error = reqwest::Client::new()
            .get("not a url")
            .build()
            .expect_err("invalid request build is not expected");
        let detail = request_failure_detail(&error);
        assert!(!detail.is_empty());
    }
}
