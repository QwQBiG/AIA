#![forbid(unsafe_code)]

mod protocol;

use std::sync::Arc;
use std::time::Duration;

use ai_ex_core::{LanguageModelPort, ModelRequest};
use ai_ex_domain::{AppError, ComponentHealth, TurnId};
use async_trait::async_trait;
use futures_util::StreamExt;
use protocol::{ChatChunk, ChatRequest, drain_lines};
use tokio::sync::{Mutex, mpsc};
use tokio::task::AbortHandle;

pub struct OllamaClient
{
    client: reqwest::Client,
    base_url: String,
    model: String,
    active_turn: Arc<Mutex<Option<TurnId>>>,
    abort_handle: Option<AbortHandle>,
}

impl OllamaClient
{
    pub fn new(
        base_url: impl Into<String>,
        model: impl Into<String>,
        timeout: Duration,
    ) -> Result<Self, AppError>
    {
        let client = reqwest::Client::builder()
            .timeout(timeout)
            .build()
            .map_err(|error| AppError::configuration(error.to_string()))?;
        Ok(Self {
            client,
            base_url: base_url.into().trim_end_matches('/').to_owned(),
            model: model.into(),
            active_turn: Arc::new(Mutex::new(None)),
            abort_handle: None,
        })
    }

    pub async fn health(&self) -> ComponentHealth
    {
        let url = format!("{}/api/tags", self.base_url);
        match self.client.get(url).send().await
        {
            Ok(response) if response.status().is_success() => ComponentHealth::ready("ollama"),
            Ok(response) => ComponentHealth::unavailable(
                "ollama",
                format!("HTTP {}", response.status()),
            ),
            Err(error) => ComponentHealth::unavailable("ollama", error.to_string()),
        }
    }
}

#[async_trait]
impl LanguageModelPort for OllamaClient
{
    async fn stream(
        &mut self,
        request: ModelRequest,
    ) -> Result<mpsc::Receiver<Result<String, AppError>>, AppError>
    {
        let mut active_turn = self.active_turn.lock().await;
        if active_turn.is_some()
        {
            return Err(AppError::invalid_transition("an Ollama turn is already active"));
        }
        *active_turn = Some(request.turn_id);
        drop(active_turn);

        let (sender, receiver) = mpsc::channel(64);
        let client = self.client.clone();
        let url = format!("{}/api/chat", self.base_url);
        let body = ChatRequest::new(self.model.clone(), request.messages);
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
            return Err(AppError::invalid_transition("cannot cancel an inactive Ollama turn"));
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
    body: ChatRequest,
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
            if process_line(&line, &sender).await?
            {
                return Ok(());
            }
        }
    }

    if !buffer.iter().all(u8::is_ascii_whitespace)
    {
        process_line(&buffer, &sender).await?;
    }
    Ok(())
}

async fn process_line(
    line: &[u8],
    sender: &mpsc::Sender<Result<String, AppError>>,
) -> Result<bool, AppError>
{
    let chunk: ChatChunk = serde_json::from_slice(line).map_err(|error| {
        AppError::protocol(format!("invalid Ollama NDJSON: {error}"))
    })?;
    if let Some(error) = chunk.error
    {
        return Err(AppError::protocol(error));
    }
    if let Some(message) = chunk.message
    {
        if !message.content.is_empty()
        {
            sender
                .send(Ok(message.content))
                .await
                .map_err(|_| AppError::unavailable("conversation receiver closed"))?;
        }
    }
    Ok(chunk.done)
}
