#![forbid(unsafe_code)]

mod protocol;

use std::collections::BTreeMap;
use std::path::PathBuf;

use ai_ex_core::AvatarPort;
use ai_ex_domain::{AppError, ComponentHealth, Emotion};
use async_trait::async_trait;
use futures_util::{SinkExt, StreamExt};
use serde_json::Value;
use tokio::sync::mpsc;
use tokio::net::TcpStream;
use tokio_tungstenite::{
    MaybeTlsStream, WebSocketStream, connect_async, tungstenite::Message,
};

#[derive(Debug, Clone)]
pub struct VtsSettings
{
    pub host: String,
    pub port: u16,
    pub token_path: PathBuf,
    pub plugin_name: String,
    pub developer: String,
    pub expression_hotkeys: BTreeMap<String, String>,
}

#[derive(Debug)]
enum Command
{
    Mouth(f64),
    Hotkey(String),
}

pub struct VtsClient
{
    sender: Option<mpsc::Sender<Command>>,
    health: ComponentHealth,
    expression_hotkeys: BTreeMap<String, String>,
}

impl VtsClient
{
    pub fn disabled() -> Self
    {
        Self {
            sender: None,
            health: ComponentHealth::unavailable("vts", "disabled"),
            expression_hotkeys: BTreeMap::new(),
        }
    }

    pub fn unavailable(detail: impl Into<String>) -> Self
    {
        Self {
            sender: None,
            health: ComponentHealth::unavailable("vts", detail),
            expression_hotkeys: BTreeMap::new(),
        }
    }

    pub async fn connect(settings: VtsSettings) -> Result<Self, AppError>
    {
        let token = read_token(&settings.token_path).await?;
        let endpoint = format!("ws://{}:{}", settings.host, settings.port);
        let (mut socket, _response) = connect_async(&endpoint)
            .await
            .map_err(|error| AppError::connectivity(error.to_string()))?;

        let request = protocol::authentication(
            &token,
            &settings.plugin_name,
            &settings.developer,
        );
        socket
            .send(Message::Text(request.to_string().into()))
            .await
            .map_err(|error| AppError::connectivity(error.to_string()))?;
        authenticate_response(&mut socket).await?;

        let (sender, receiver) = mpsc::channel(64);
        tokio::spawn(run_actor(socket, receiver));
        Ok(Self {
            sender: Some(sender),
            health: ComponentHealth::ready("vts"),
            expression_hotkeys: settings.expression_hotkeys,
        })
    }

    pub fn health(&self) -> &ComponentHealth
    {
        &self.health
    }

    pub async fn trigger_hotkey(&self, id: impl Into<String>) -> Result<(), AppError>
    {
        self.send(Command::Hotkey(id.into())).await
    }

    async fn send(&self, command: Command) -> Result<(), AppError>
    {
        let Some(sender) = &self.sender else
        {
            return Ok(());
        };
        sender
            .send(command)
            .await
            .map_err(|_| AppError::unavailable("VTS actor stopped"))
    }
}

#[async_trait]
impl AvatarPort for VtsClient
{
    async fn set_speaking(&mut self, speaking: bool) -> Result<(), AppError>
    {
        let value = if speaking
        {
            0.65
        }
        else
        {
            0.0
        };
        self.send(Command::Mouth(value)).await
    }

    async fn set_neutral(&mut self) -> Result<(), AppError>
    {
        self.send(Command::Mouth(0.0)).await?;
        self.set_emotion(Emotion::Neutral).await
    }

    async fn set_emotion(&mut self, emotion: Emotion) -> Result<(), AppError>
    {
        let Some(hotkey) = self.expression_hotkeys.get(emotion.as_str()).cloned() else
        {
            return Ok(());
        };
        self.send(Command::Hotkey(hotkey)).await
    }
}

type Socket = WebSocketStream<MaybeTlsStream<TcpStream>>;

async fn read_token(path: &PathBuf) -> Result<String, AppError>
{
    let content = tokio::fs::read_to_string(path).await.map_err(|error| {
        AppError::configuration(format!("cannot read VTS token {}: {error}", path.display()))
    })?;
    let document: Value = serde_json::from_str(&content).map_err(|error| {
        AppError::configuration(format!("invalid VTS token JSON: {error}"))
    })?;
    document
        .get("token")
        .and_then(Value::as_str)
        .map(str::to_owned)
        .ok_or_else(|| AppError::configuration("VTS token file requires a string 'token'"))
}

async fn authenticate_response(socket: &mut Socket) -> Result<(), AppError>
{
    let response = tokio::time::timeout(std::time::Duration::from_secs(10), socket.next())
        .await
        .map_err(|_| AppError::connectivity("VTS authentication timed out"))?
        .ok_or_else(|| AppError::connectivity("VTS closed during authentication"))?
        .map_err(|error| AppError::connectivity(error.to_string()))?;
    let text = response
        .into_text()
        .map_err(|error| AppError::protocol(error.to_string()))?;
    let document: Value = serde_json::from_str(&text)
        .map_err(|error| AppError::protocol(error.to_string()))?;
    if !protocol::authenticated(&document)
    {
        return Err(AppError::protocol(format!(
            "VTS rejected authentication: {}",
            document.get("data").cloned().unwrap_or(Value::Null)
        )));
    }
    Ok(())
}

async fn run_actor(socket: Socket, mut receiver: mpsc::Receiver<Command>)
{
    let (mut writer, mut reader) = socket.split();
    loop
    {
        tokio::select!
        {
            command = receiver.recv() =>
            {
                let Some(command) = command else
                {
                    break;
                };
                let request = match command
                {
                    Command::Mouth(value) => protocol::mouth_open(value),
                    Command::Hotkey(id) => protocol::trigger_hotkey(&id),
                };
                if writer.send(Message::Text(request.to_string().into())).await.is_err()
                {
                    break;
                }
            }
            message = reader.next() =>
            {
                match message
                {
                    Some(Ok(Message::Close(_))) | Some(Err(_)) | None => break,
                    _ =>
                    {
                    }
                }
            }
        }
    }
}
