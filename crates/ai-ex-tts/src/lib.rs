#![forbid(unsafe_code)]

use std::time::Duration;

use ai_ex_domain::{AppError, ComponentHealth};
use serde::Serialize;

#[derive(Debug, Clone)]
pub struct GptSovitsSettings
{
    pub base_url: String,
    pub timeout: Duration,
    pub text_lang: String,
    pub ref_audio_path: String,
    pub prompt_text: String,
    pub prompt_lang: String,
}

#[derive(Debug)]
pub struct SynthesizedAudio
{
    pub bytes: Vec<u8>,
    pub content_type: String,
}

pub struct GptSovitsClient
{
    client: reqwest::Client,
    settings: GptSovitsSettings,
}

impl GptSovitsClient
{
    pub fn new(settings: GptSovitsSettings) -> Result<Self, AppError>
    {
        if settings.base_url.trim().is_empty() || settings.ref_audio_path.trim().is_empty()
        {
            return Err(AppError::configuration(
                "GPT-SoVITS requires base_url and ref_audio_path",
            ));
        }
        let client = reqwest::Client::builder()
            .timeout(settings.timeout)
            .build()
            .map_err(|error| AppError::configuration(error.to_string()))?;
        Ok(Self { client, settings })
    }

    pub async fn synthesize(&self, text: &str) -> Result<SynthesizedAudio, AppError>
    {
        let text = text.trim();
        if text.is_empty()
        {
            return Err(AppError::configuration("TTS text must not be empty"));
        }
        let payload = SynthesisRequest {
            text,
            text_lang: &self.settings.text_lang,
            ref_audio_path: &self.settings.ref_audio_path,
            prompt_text: &self.settings.prompt_text,
            prompt_lang: &self.settings.prompt_lang,
            text_split_method: "cut5",
            batch_size: 1,
            media_type: "wav",
            streaming_mode: false,
            speed_factor: 1.0,
            top_k: 5,
            top_p: 1.0,
            temperature: 1.0,
        };
        let response = self
            .client
            .post(self.settings.base_url.trim_end_matches('/'))
            .json(&payload)
            .send()
            .await
            .map_err(|error| AppError::connectivity(error.to_string()))?;
        let status = response.status();
        let content_type = response
            .headers()
            .get(reqwest::header::CONTENT_TYPE)
            .and_then(|value| value.to_str().ok())
            .unwrap_or_default()
            .to_owned();
        if !status.is_success()
        {
            let detail = response.text().await.unwrap_or_default();
            return Err(AppError::protocol(format!(
                "GPT-SoVITS HTTP {status}: {}",
                detail.chars().take(300).collect::<String>()
            )));
        }
        if !content_type.starts_with("audio/")
        {
            return Err(AppError::protocol(format!(
                "GPT-SoVITS returned non-audio content: {content_type}"
            )));
        }
        let bytes = response
            .bytes()
            .await
            .map_err(|error| AppError::connectivity(error.to_string()))?
            .to_vec();
        if bytes.is_empty()
        {
            return Err(AppError::protocol("GPT-SoVITS returned empty audio"));
        }
        Ok(SynthesizedAudio {
            bytes,
            content_type,
        })
    }

    pub async fn health(&self) -> ComponentHealth
    {
        match self.client.get(&self.settings.base_url).send().await
        {
            Ok(response) if response.status().is_server_error() => ComponentHealth::unavailable(
                "gpt-sovits",
                format!("HTTP {}", response.status()),
            ),
            Ok(_) => ComponentHealth::ready("gpt-sovits"),
            Err(error) => ComponentHealth::unavailable("gpt-sovits", error.to_string()),
        }
    }
}

#[derive(Debug, Serialize)]
struct SynthesisRequest<'a>
{
    text: &'a str,
    text_lang: &'a str,
    ref_audio_path: &'a str,
    prompt_text: &'a str,
    prompt_lang: &'a str,
    text_split_method: &'a str,
    batch_size: u8,
    media_type: &'a str,
    streaming_mode: bool,
    speed_factor: f32,
    top_k: u8,
    top_p: f32,
    temperature: f32,
}
