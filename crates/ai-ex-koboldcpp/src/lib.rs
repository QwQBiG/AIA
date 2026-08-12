#![forbid(unsafe_code)]

mod protocol;

use std::sync::Arc;
use std::time::Duration;

use ai_ex_core::{LanguageModelPort, ModelRequest};
use ai_ex_domain::{AppError, ComponentHealth, TurnId};
use async_trait::async_trait;
use futures_util::StreamExt;
use protocol::{StreamEvent, drain_lines, parse_event, prompt, request_body};
use tokio::sync::{Mutex, mpsc};
use tokio::task::AbortHandle;

#[derive(Debug, Clone)]
pub struct KoboldCppSettings
{
    pub base_url: String,
    pub timeout: Duration,
    pub max_context_length: usize,
    pub max_length: usize,
    pub temperature: f32,
}

pub struct KoboldCppClient
{
    client: reqwest::Client,
    base_url: String,
    settings: KoboldCppSettings,
    active_turn: Arc<Mutex<Option<TurnId>>>,
    abort_handle: Option<AbortHandle>,
}

impl KoboldCppClient
{
    pub fn new(mut settings: KoboldCppSettings) -> Result<Self, AppError>
    {
        if !settings.base_url.starts_with("http://")
            && !settings.base_url.starts_with("https://")
        {
            return Err(AppError::configuration(
                "KoboldCpp base_url must be HTTP or HTTPS",
            ));
        }
        if settings.max_context_length == 0 || settings.max_length == 0
        {
            return Err(AppError::configuration(
                "KoboldCpp token limits must be positive",
            ));
        }
        if !settings.temperature.is_finite() || !(0.0..=2.0).contains(&settings.temperature)
        {
            return Err(AppError::configuration(
                "KoboldCpp temperature must be between 0 and 2",
            ));
        }
        settings.base_url = settings.base_url.trim_end_matches('/').to_owned();
        let client = reqwest::Client::builder()
            .timeout(settings.timeout)
            .build()
            .map_err(|error| AppError::configuration(error.to_string()))?;
        Ok(Self {
            client,
            base_url: settings.base_url.clone(),
            settings,
            active_turn: Arc::new(Mutex::new(None)),
            abort_handle: None,
        })
    }

    pub async fn health(&self) -> ComponentHealth
    {
        let url = format!("{}/api/v1/model", self.base_url);
        match self.client.get(url).send().await
        {
            Ok(response) if response.status().is_success() => {
                ComponentHealth::ready("koboldcpp")
            }
            Ok(response) => ComponentHealth::unavailable(
                "koboldcpp",
                format!("HTTP {}", response.status()),
            ),
            Err(error) => ComponentHealth::unavailable("koboldcpp", error.to_string()),
        }
    }
}

#[async_trait]
impl LanguageModelPort for KoboldCppClient
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
                "a KoboldCpp turn is already active",
            ));
        }
        *active_turn = Some(request.turn_id);
        drop(active_turn);

        let (sender, receiver) = mpsc::channel(64);
        let client = self.client.clone();
        let url = format!("{}/api/v1/generate", self.base_url);
        let body = request_body(
            prompt(&request.messages),
            self.settings.max_context_length,
            self.settings.max_length,
            self.settings.temperature,
        );
        let active_turn = Arc::clone(&self.active_turn);
        let task = tokio::spawn(async move
        {
            if let Err(error) = execute_stream(client, url, body, sender.clone()).await
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
                "cannot cancel an inactive KoboldCpp turn",
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
    body: serde_json::Value,
    sender: mpsc::Sender<Result<String, AppError>>,
) -> Result<(), AppError>
{
    let response = client
        .post(url)
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

    fn settings() -> KoboldCppSettings
    {
        KoboldCppSettings {
            base_url: "http://127.0.0.1:5001/".to_owned(),
            timeout: Duration::from_secs(1),
            max_context_length: 2_048,
            max_length: 256,
            temperature: 0.7,
        }
    }

    #[test]
    fn validates_settings_without_network_access()
    {
        assert!(KoboldCppClient::new(settings()).is_ok());
        let mut invalid = settings();
        invalid.temperature = f32::NAN;
        assert!(KoboldCppClient::new(invalid).is_err());
    }
}
