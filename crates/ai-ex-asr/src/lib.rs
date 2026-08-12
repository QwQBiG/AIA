#![forbid(unsafe_code)]

mod wav;

use std::time::Duration;

use ai_ex_domain::{AppError, ComponentHealth};
use ai_ex_duplex::{TranscriberPort, Utterance};
use async_trait::async_trait;
use reqwest::multipart::{Form, Part};
use serde::Deserialize;

pub use wav::encode_pcm16_wav;

pub struct WhisperHttpTranscriber
{
    client: reqwest::Client,
    endpoint: String,
    model: String,
    language: Option<String>,
}

impl WhisperHttpTranscriber
{
    pub fn new(
        endpoint: impl Into<String>,
        model: impl Into<String>,
        language: Option<String>,
        timeout: Duration,
    ) -> Result<Self, AppError>
    {
        let endpoint = endpoint.into();
        if !endpoint.starts_with("http://") && !endpoint.starts_with("https://")
        {
            return Err(AppError::configuration("ASR endpoint must be HTTP or HTTPS"));
        }
        let model = model.into();
        if model.trim().is_empty()
        {
            return Err(AppError::configuration("ASR model must not be empty"));
        }
        let client = reqwest::Client::builder()
            .timeout(timeout)
            .build()
            .map_err(|error| AppError::configuration(format!("invalid ASR client: {error}")))?;
        Ok(Self {
            client,
            endpoint,
            model,
            language,
        })
    }

    pub async fn health(&self) -> ComponentHealth
    {
        match self.client.get(&self.endpoint).send().await
        {
            Ok(response)
                if response.status().is_success()
                    || response.status() == reqwest::StatusCode::METHOD_NOT_ALLOWED =>
            {
                ComponentHealth {
                    component: "asr".to_owned(),
                    ready: true,
                    detail: format!("endpoint reachable ({})", response.status()),
                }
            }
            Ok(response) => ComponentHealth::unavailable(
                "asr",
                format!("unexpected health status {}", response.status()),
            ),
            Err(error) => ComponentHealth::unavailable("asr", error.to_string()),
        }
    }
}

#[derive(Deserialize)]
struct TranscriptionResponse
{
    text: String,
}

#[async_trait]
impl TranscriberPort for WhisperHttpTranscriber
{
    async fn transcribe(&mut self, utterance: Utterance) -> Result<String, AppError>
    {
        let wav = encode_pcm16_wav(&utterance)?;
        let file = Part::bytes(wav)
            .file_name("utterance.wav")
            .mime_str("audio/wav")
            .map_err(|error| AppError::configuration(format!("invalid WAV MIME type: {error}")))?;
        let mut form = Form::new()
            .part("file", file)
            .text("model", self.model.clone());
        if let Some(language) = &self.language
        {
            form = form.text("language", language.clone());
        }
        let response = self
            .client
            .post(&self.endpoint)
            .multipart(form)
            .send()
            .await
            .map_err(|error| AppError::connectivity(format!("ASR request failed: {error}")))?;
        let status = response.status();
        if !status.is_success()
        {
            let body = response.text().await.unwrap_or_default();
            return Err(AppError::protocol(format!("ASR returned {status}: {body}")));
        }
        let result: TranscriptionResponse = response
            .json()
            .await
            .map_err(|error| AppError::protocol(format!("invalid ASR response: {error}")))?;
        Ok(result.text)
    }
}
