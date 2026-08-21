#![forbid(unsafe_code)]

mod args;
mod events;

use std::path::PathBuf;
use std::collections::BTreeSet;
use std::sync::Arc;
use std::time::Duration;

use ai_ex_audio::{AudioPlayer, SpeechQueue, SpeechReceiver};
use ai_ex_asr::WhisperHttpTranscriber;
use ai_ex_audit::JsonlAuditLog;
use ai_ex_config::{AppConfig, ModelBackend};
use ai_ex_deepseek::{DeepSeekClient, DeepSeekSettings};
use ai_ex_control::{ControlBackend, ControlCommand, ControlPayload, ControlServer};
use ai_ex_core::{
    ConversationPolicy, LanguageModelPort, ModelRequest, Runtime, RuntimeHandle, spawn_runtime,
};
use ai_ex_domain::{AppError, ComponentHealth, ErrorKind, TurnId};
use ai_ex_koboldcpp::{KoboldCppClient, KoboldCppSettings};
use ai_ex_memory::MemoryStore;
use ai_ex_observability::{EventHub, TeeEventSink};
use ai_ex_ollama::OllamaClient;
use ai_ex_safety::{Capability, SafetyGate, SafetyPolicy};
use ai_ex_tts::{GptSovitsClient, GptSovitsSettings};
use ai_ex_vts::{VtsClient, VtsSettings};
use ai_ex_vision::{
    OllamaVisionClient, OllamaVisionSettings, VisionAnalyzerPort, VisionRequest, VisualFrame,
};
use async_trait::async_trait;
use args::Args;
use events::ConsoleEvents;
use tokio::io::{AsyncBufReadExt, BufReader};
use tracing_subscriber::EnvFilter;

#[cfg(feature = "native-capture")]
use ai_ex_capture::{CaptureSettings, NativeAudioSource};
#[cfg(feature = "native-capture")]
use ai_ex_duplex::{
    AudioSourcePort, DuplexController, DuplexDirective, EnergyVad, VadConfig,
};

enum ConfiguredModel
{
    Ollama(OllamaClient),
    DeepSeek(DeepSeekClient),
    KoboldCpp(KoboldCppClient),
}

impl ConfiguredModel
{
    async fn health(&self) -> ComponentHealth
    {
        match self
        {
            Self::Ollama(client) => client.health().await,
            Self::DeepSeek(client) => client.health().await,
            Self::KoboldCpp(client) => client.health().await,
        }
    }
}

#[async_trait]
impl LanguageModelPort for ConfiguredModel
{
    async fn stream(
        &mut self,
        request: ModelRequest,
    ) -> Result<tokio::sync::mpsc::Receiver<Result<String, AppError>>, AppError>
    {
        match self
        {
            Self::Ollama(client) => client.stream(request).await,
            Self::DeepSeek(client) => client.stream(request).await,
            Self::KoboldCpp(client) => client.stream(request).await,
        }
    }

    async fn cancel(&mut self, turn_id: TurnId) -> Result<(), AppError>
    {
        match self
        {
            Self::Ollama(client) => client.cancel(turn_id).await,
            Self::DeepSeek(client) => client.cancel(turn_id).await,
            Self::KoboldCpp(client) => client.cancel(turn_id).await,
        }
    }
}

#[tokio::main]
async fn main()
{
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();

    if let Err(error) = run().await
    {
        eprintln!("AIex failed: {error}");
        std::process::exit(1);
    }
}

async fn run() -> Result<(), AppError>
{
    let args = Args::parse(std::env::args().skip(1))?;
    let config = AppConfig::load(&args.config).await?;
    let vision = build_vision(&config)?;
    if let (Some(image_path), Some(prompt)) = (args.vision_image, args.vision_prompt)
    {
        let mut vision = vision.ok_or_else(|| {
            AppError::configuration("vision analysis requires vision.enabled = true")
        })?;
        let bytes = tokio::fs::read(&image_path).await.map_err(|error| {
            AppError::unavailable(format!(
                "failed to read vision image {}: {error}",
                image_path.display(),
            ))
        })?;
        let request = VisionRequest::new(prompt, VisualFrame::detect(bytes)?)?;
        let observation = vision.analyze(request).await?;
        println!("{}", observation.text);
        return Ok(());
    }
    let model = build_model(&config)?;
    let vts = connect_vts(&config).await;
    let (speech, receiver) = SpeechQueue::new(config.audio.queue_capacity)?;
    let player = receiver.player();
    let tts = build_tts(&config).await?;
    let safety = Arc::new(build_safety(&config)?);
    let audit = build_audit(&config).await?;
    let memory = if config.memory.enabled
    {
        MemoryStore::open(&config.memory.path).await?
    }
    else
    {
        MemoryStore::disabled()
    };

    if args.check
    {
        return run_check(HealthContext {
            model: &model,
            vts: &vts,
            speech: &speech,
            memory: &memory,
            player: &player,
            tts: tts.as_ref(),
            safety: safety.as_ref(),
            audit: audit.as_ref(),
            vision: vision.as_ref(),
            config: &config,
        })
        .await;
    }

    let speech_task = tokio::spawn(run_speech_worker(receiver, tts, player));
    let event_hub = EventHub::new(256)?;
    let events = TeeEventSink::new(ConsoleEvents, event_hub.clone());
    let runtime = Runtime::with_policy(
        model,
        speech,
        vts,
        memory,
        events,
        ConversationPolicy {
            system_prompt: config.conversation.system_prompt.clone(),
            history_turn_limit: config.conversation.history_turn_limit,
            memory_recall_limit: config.conversation.memory_recall_limit,
        },
    )?;
    let runtime = spawn_runtime(runtime, 32)?;
    if let Some(prompt) = args.prompt
    {
        runtime.submit(prompt).await?;
        runtime.shutdown().await?;
        join_speech_worker(speech_task).await?;
        return Ok(());
    }

    let control_task = spawn_control(
        &config,
        runtime.clone(),
        event_hub.clone(),
        Arc::clone(&safety),
    )
    .await?;
    let duplex_task = spawn_duplex(&config, runtime.clone())?;
    println!(
        "AIex Rust interactive mode. Commands: /status, /interrupt, /emergency-stop, /quit.",
    );
    let mut lines = BufReader::new(tokio::io::stdin()).lines();
    while let Some(line) = lines
        .next_line()
        .await
        .map_err(|error| AppError::unavailable(error.to_string()))?
    {
        let line = line.trim();
        if line.is_empty() || line == "/quit"
        {
            break;
        }
        if line == "/interrupt"
        {
            if let Err(error) = runtime.interrupt("interactive barge-in").await
            {
                eprintln!("interrupt failed: {error}");
            }
            continue;
        }
        if line == "/status"
        {
            println!(
                "{}",
                serde_json::to_string_pretty(&event_hub.current()).unwrap_or_default(),
            );
            continue;
        }
        if line == "/emergency-stop"
        {
            safety.trigger_emergency_stop();
            if let Err(error) = runtime.interrupt("emergency stop").await
                && error.kind != ErrorKind::InvalidTransition
            {
                eprintln!("emergency interrupt failed: {error}");
            }
            println!("Emergency stop is active until the service restarts.");
            continue;
        }
        let submitter = runtime.clone();
        let input = line.to_owned();
        tokio::spawn(async move
        {
            if let Err(error) = submitter.submit(input).await
            {
                eprintln!("turn failed: {error}");
            }
        });
    }
    if let Some(task) = duplex_task
    {
        task.abort();
    }
    if let Some(task) = control_task
    {
        task.abort();
    }
    runtime.shutdown().await?;
    join_speech_worker(speech_task).await?;
    Ok(())
}

async fn join_speech_worker(task: tokio::task::JoinHandle<()>) -> Result<(), AppError>
{
    task.await
        .map_err(|error| AppError::unavailable(format!("speech worker failed: {error}")))
}

async fn connect_vts(config: &AppConfig) -> VtsClient
{
    if !config.vts.enabled
    {
        return VtsClient::disabled();
    }
    let settings = VtsSettings {
        host: config.vts.host.clone(),
        port: config.vts.port,
        token_path: PathBuf::from(&config.vts.token_path),
        plugin_name: config.vts.plugin_name.clone(),
        developer: config.vts.developer.clone(),
        expression_hotkeys: config.vts.expression_hotkeys.clone(),
    };
    match VtsClient::connect(settings).await
    {
        Ok(client) => client,
        Err(error) =>
        {
            tracing::warn!(%error, "VTS unavailable; avatar output disabled");
            VtsClient::unavailable(error.to_string())
        }
    }
}

struct HealthContext<'a>
{
    model: &'a ConfiguredModel,
    vts: &'a VtsClient,
    speech: &'a SpeechQueue,
    memory: &'a MemoryStore,
    player: &'a AudioPlayer,
    tts: Option<&'a GptSovitsClient>,
    safety: &'a SafetyGate,
    audit: Option<&'a JsonlAuditLog>,
    vision: Option<&'a OllamaVisionClient>,
    config: &'a AppConfig,
}

async fn run_check(context: HealthContext<'_>) -> Result<(), AppError>
{
    let mut health = vec![
        context.model.health().await,
        context.vts.health().clone(),
        context.speech.health(),
        context.memory.health().await,
        context.safety.health(),
    ];
    if let Some(tts) = context.tts
    {
        health.push(tts.health().await);
        health.push(context.player.health().await);
    }
    if context.config.duplex.enabled
    {
        health.push(build_asr(context.config)?.health().await);
        health.push(capture_health(context.config));
    }
    if context.config.control.enabled
    {
        health.push(control_health(context.config).await);
    }
    if let Some(audit) = context.audit
    {
        health.push(audit.health());
    }
    if let Some(vision) = context.vision
    {
        health.push(vision.health().await);
    }
    println!("{}", serde_json::to_string_pretty(&health).unwrap_or_default());
    let failed: Vec<&ComponentHealth> = health.iter().filter(|item| !item.ready).collect();
    if !failed.is_empty()
    {
        return Err(AppError::unavailable(format!(
            "{} component(s) unavailable",
            failed.len()
        )));
    }
    Ok(())
}

async fn run_speech_worker(
    mut receiver: SpeechReceiver,
    tts: Option<GptSovitsClient>,
    player: AudioPlayer,
)
{
    while let Some(job) = receiver.receive().await
    {
        let Some(tts) = &tts else
        {
            tracing::debug!(turn_id = ?job.turn_id, "TTS disabled; speech job skipped");
            continue;
        };
        match tts.synthesize(&job.text).await
        {
            Ok(audio) =>
            {
                if let Err(error) = player.play_wav(&job, audio.bytes).await
                {
                    tracing::error!(%error, "audio playback failed");
                }
            }
            Err(error) => tracing::error!(%error, "speech synthesis failed"),
        }
    }
}

async fn build_tts(config: &AppConfig) -> Result<Option<GptSovitsClient>, AppError>
{
    if !config.tts.enabled
    {
        return Ok(None);
    }
    let reference = tokio::fs::canonicalize(&config.tts.ref_audio_path)
        .await
        .map_err(|error| {
            AppError::configuration(format!(
                "cannot resolve TTS reference audio {}: {error}",
                config.tts.ref_audio_path
            ))
        })?;
    let settings = GptSovitsSettings {
        base_url: config.tts.base_url.clone(),
        timeout: Duration::from_secs(config.tts.timeout_seconds),
        text_lang: config.tts.text_lang.clone(),
        ref_audio_path: reference.to_string_lossy().into_owned(),
        prompt_text: config.tts.prompt_text.clone(),
        prompt_lang: config.tts.prompt_lang.clone(),
    };
    Ok(Some(GptSovitsClient::new(settings)?))
}

fn build_safety(config: &AppConfig) -> Result<SafetyGate, AppError>
{
    let capabilities = config
        .safety
        .allowed_capabilities
        .iter()
        .map(|value| value.parse::<Capability>())
        .collect::<Result<BTreeSet<_>, _>>()?;
    if config.safety.automation_enabled
        && (capabilities.is_empty() || config.safety.allowed_targets.is_empty())
    {
        return Err(AppError::configuration(
            "enabled automation requires allowed capabilities and targets",
        ));
    }
    Ok(SafetyGate::new(SafetyPolicy {
        automation_enabled: config.safety.automation_enabled,
        allowed_capabilities: capabilities,
        allowed_targets: config.safety.allowed_targets.clone(),
    }))
}

async fn build_audit(config: &AppConfig) -> Result<Option<JsonlAuditLog>, AppError>
{
    if !config.safety.automation_enabled
    {
        return Ok(None);
    }
    Ok(Some(JsonlAuditLog::open(&config.safety.audit_path).await?))
}

fn build_vision(config: &AppConfig) -> Result<Option<OllamaVisionClient>, AppError>
{
    if !config.vision.enabled
    {
        return Ok(None);
    }
    Ok(Some(OllamaVisionClient::new(OllamaVisionSettings {
        base_url: config.vision.base_url.clone(),
        model: config.vision.model.clone(),
        timeout: Duration::from_secs(config.vision.timeout_seconds),
    })?))
}

fn build_model(config: &AppConfig) -> Result<ConfiguredModel, AppError>
{
    match config.model.backend
    {
        ModelBackend::Ollama => Ok(ConfiguredModel::Ollama(OllamaClient::new(
            &config.ollama.base_url,
            &config.ollama.model,
            Duration::from_secs(config.ollama.timeout_seconds),
        )?)),
        ModelBackend::DeepSeek =>
        {
            let api_key = std::env::var(&config.deepseek.api_key_env).map_err(|_| {
                AppError::configuration(format!(
                    "DeepSeek API key environment variable {} is not set",
                    config.deepseek.api_key_env,
                ))
            })?;
            Ok(ConfiguredModel::DeepSeek(DeepSeekClient::new(
                DeepSeekSettings {
                    base_url: config.deepseek.base_url.clone(),
                    model: config.deepseek.model.clone(),
                    api_key,
                    timeout: Duration::from_secs(config.deepseek.timeout_seconds),
                    thinking: config.deepseek.thinking,
                    reasoning_effort: config.deepseek.reasoning_effort.clone(),
                },
            )?))
        }
        ModelBackend::KoboldCpp => {
            Ok(ConfiguredModel::KoboldCpp(KoboldCppClient::new(
                KoboldCppSettings {
                    base_url: config.koboldcpp.base_url.clone(),
                    timeout: Duration::from_secs(config.koboldcpp.timeout_seconds),
                    max_context_length: config.koboldcpp.max_context_length,
                    max_length: config.koboldcpp.max_length,
                    temperature: config.koboldcpp.temperature,
                },
            )?))
        }
    }
}

fn build_asr(config: &AppConfig) -> Result<WhisperHttpTranscriber, AppError>
{
    let language = match config.duplex.asr.language.trim()
    {
        "" => None,
        language => Some(language.to_owned()),
    };
    WhisperHttpTranscriber::new(
        &config.duplex.asr.endpoint,
        &config.duplex.asr.model,
        language,
        Duration::from_secs(config.duplex.asr.timeout_seconds),
    )
}

#[derive(Clone)]
struct ServiceControl
{
    runtime: RuntimeHandle,
    events: EventHub,
    safety: Arc<SafetyGate>,
}

#[async_trait::async_trait]
impl ControlBackend for ServiceControl
{
    async fn execute(&self, command: ControlCommand) -> Result<ControlPayload, AppError>
    {
        match command
        {
            ControlCommand::Submit { text } =>
            {
                let text = text.trim();
                if text.is_empty()
                {
                    return Err(AppError::configuration("control submit text must not be empty"));
                }
                let runtime = self.runtime.clone();
                let text = text.to_owned();
                tokio::spawn(async move
                {
                    if let Err(error) = runtime.submit(text).await
                    {
                        tracing::error!(%error, "control turn failed");
                    }
                });
                Ok(ControlPayload::Accepted)
            }
            ControlCommand::Interrupt { reason } =>
            {
                let reason = if reason.trim().is_empty()
                {
                    "control interrupt"
                }
                else
                {
                    reason.trim()
                };
                self.runtime.interrupt(reason).await?;
                Ok(ControlPayload::Accepted)
            }
            ControlCommand::Status => Ok(ControlPayload::Snapshot(self.events.current())),
            ControlCommand::Events { after, limit } =>
            {
                if limit == 0 || limit > 1_000
                {
                    return Err(AppError::configuration(
                        "control event limit must be between 1 and 1000",
                    ));
                }
                Ok(ControlPayload::Events(self.events.events_since(after, limit)))
            }
            ControlCommand::EmergencyStop =>
            {
                self.safety.trigger_emergency_stop();
                if let Err(error) = self.runtime.interrupt("emergency stop").await
                    && error.kind != ErrorKind::InvalidTransition
                {
                    return Err(error);
                }
                Ok(ControlPayload::Accepted)
            }
        }
    }
}

async fn spawn_control(
    config: &AppConfig,
    runtime: RuntimeHandle,
    events: EventHub,
    safety: Arc<SafetyGate>,
) -> Result<Option<tokio::task::JoinHandle<()>>, AppError>
{
    if !config.control.enabled
    {
        return Ok(None);
    }
    let token = tokio::fs::read_to_string(&config.control.token_path)
        .await
        .map_err(|error| {
            AppError::configuration(format!(
                "cannot read control token {}: {error}",
                config.control.token_path,
            ))
        })?;
    let server = ControlServer::bind(
        &config.control.bind,
        token.trim(),
        config.control.max_message_bytes,
    )
    .await?;
    let address = server.local_addr()?;
    let backend = Arc::new(ServiceControl {
        runtime,
        events,
        safety,
    });
    tracing::info!(%address, "local control server ready");
    Ok(Some(tokio::spawn(async move
    {
        if let Err(error) = server.serve(backend).await
        {
            tracing::error!(%error, "control server stopped");
        }
    })))
}

async fn control_health(config: &AppConfig) -> ComponentHealth
{
    let token = match tokio::fs::read_to_string(&config.control.token_path).await
    {
        Ok(token) => token,
        Err(error) => return ComponentHealth::unavailable(
            "control",
            format!("cannot read token file: {error}"),
        ),
    };
    match ControlServer::bind(
        &config.control.bind,
        token.trim(),
        config.control.max_message_bytes,
    )
    .await
    {
        Ok(server) => match server.local_addr()
        {
            Ok(address) => ComponentHealth {
                component: "control".to_owned(),
                ready: true,
                detail: format!("loopback endpoint available at {address}"),
            },
            Err(error) => ComponentHealth::unavailable("control", error.to_string()),
        },
        Err(error) => ComponentHealth::unavailable("control", error.to_string()),
    }
}

#[cfg(not(feature = "native-capture"))]
fn capture_health(_config: &AppConfig) -> ComponentHealth
{
    ComponentHealth::unavailable(
        "audio-input",
        "binary was built without the native-capture feature",
    )
}

#[cfg(feature = "native-capture")]
fn capture_health(config: &AppConfig) -> ComponentHealth
{
    let device_name = match config.duplex.input_device.trim()
    {
        "" => None,
        name => Some(name.to_owned()),
    };
    let settings = CaptureSettings {
        device_name,
        queue_capacity: config.duplex.capture_queue_capacity,
    };
    match NativeAudioSource::open(settings)
    {
        Ok(_source) => ComponentHealth::ready("audio-input"),
        Err(error) => ComponentHealth::unavailable("audio-input", error.to_string()),
    }
}

#[cfg(not(feature = "native-capture"))]
fn spawn_duplex(
    config: &AppConfig,
    _runtime: RuntimeHandle,
) -> Result<Option<tokio::task::JoinHandle<()>>, AppError>
{
    if config.duplex.enabled
    {
        return Err(AppError::configuration(
            "duplex is enabled but this binary lacks the native-capture feature",
        ));
    }
    Ok(None)
}

#[cfg(feature = "native-capture")]
fn spawn_duplex(
    config: &AppConfig,
    runtime: RuntimeHandle,
) -> Result<Option<tokio::task::JoinHandle<()>>, AppError>
{
    if !config.duplex.enabled
    {
        return Ok(None);
    }
    let device_name = match config.duplex.input_device.trim()
    {
        "" => None,
        name => Some(name.to_owned()),
    };
    let source = NativeAudioSource::open(CaptureSettings {
        device_name,
        queue_capacity: config.duplex.capture_queue_capacity,
    })?;
    let transcriber = build_asr(config)?;
    let vad = EnergyVad::new(VadConfig {
        start_threshold: config.duplex.start_threshold,
        continue_threshold: config.duplex.continue_threshold,
        start_frames: config.duplex.start_frames,
        end_silence_frames: config.duplex.end_silence_frames,
        max_utterance_frames: config.duplex.max_utterance_frames,
    })?;
    let controller = DuplexController::new(vad, transcriber);
    Ok(Some(tokio::spawn(async move
    {
        if let Err(error) = run_duplex(source, controller, runtime).await
        {
            tracing::error!(%error, "full-duplex input stopped");
        }
    })))
}

#[cfg(feature = "native-capture")]
async fn run_duplex(
    mut source: NativeAudioSource,
    mut controller: DuplexController<WhisperHttpTranscriber>,
    runtime: RuntimeHandle,
) -> Result<(), AppError>
{
    while let Some(frame) = source.next_frame().await?
    {
        let Some(directive) = controller.process_frame(frame).await? else
        {
            continue;
        };
        match directive
        {
            DuplexDirective::InterruptCurrentTurn =>
            {
                if let Err(error) = runtime.interrupt("voice barge-in").await
                    && error.kind != ErrorKind::InvalidTransition
                {
                    return Err(error);
                }
            }
            DuplexDirective::SubmitTranscript(transcript) =>
            {
                let runtime = runtime.clone();
                tokio::spawn(async move
                {
                    if let Err(error) = runtime.submit(transcript).await
                    {
                        tracing::error!(%error, "transcribed turn failed");
                    }
                });
            }
        }
    }
    Ok(())
}
