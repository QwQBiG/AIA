#![forbid(unsafe_code)]

use std::time::Duration;

use ai_ex_domain::{AppError, ComponentHealth};
use ai_ex_stage::{StageAction, StageCapability, StageExecutor};
use async_trait::async_trait;
use base64::{Engine, engine::general_purpose::STANDARD};
use futures_util::{SinkExt, StreamExt};
use ring::digest::{SHA256, digest};
use serde_json::{Value, json};
use tokio::net::TcpStream;
use tokio::sync::mpsc;
use tokio_tungstenite::{MaybeTlsStream, WebSocketStream, connect_async, tungstenite::Message};
use uuid::Uuid;

type ObsSocket = WebSocketStream<MaybeTlsStream<TcpStream>>;

#[derive(Debug, Clone)]
pub struct ObsSettings
{
    pub host: String,
    pub port: u16,
    pub password: Option<String>,
    pub subtitle_input: Option<String>,
    pub timeout: Duration,
}

impl ObsSettings
{
    pub fn new(host: impl Into<String>, port: u16) -> Result<Self, AppError>
    {
        let host = host.into();
        if host.trim().is_empty()
        {
            return Err(AppError::configuration("OBS host must not be empty"));
        }
        if port == 0
        {
            return Err(AppError::configuration("OBS port must be positive"));
        }
        Ok(Self {
            host,
            port,
            password: None,
            subtitle_input: None,
            timeout: Duration::from_secs(10),
        })
    }

    fn endpoint(&self) -> String
    {
        format!("ws://{}:{}", self.host.trim(), self.port)
    }
}

pub struct ObsWebSocketStage
{
    sender: mpsc::Sender<Command>,
    health: ComponentHealth,
    subtitle_input: Option<String>,
}

impl ObsWebSocketStage
{
    pub async fn connect(settings: ObsSettings) -> Result<Self, AppError>
    {
        let endpoint = settings.endpoint();
        let (mut socket, _response) = tokio::time::timeout(
            settings.timeout,
            connect_async(&endpoint),
        )
        .await
        .map_err(|_| AppError::connectivity("OBS WebSocket connection timed out"))?
        .map_err(|error| AppError::connectivity(format!("OBS WebSocket connect failed: {error}")))?;
        let hello = receive_json(&mut socket, settings.timeout).await?;
        let identify = identify_request(&hello, settings.password.as_deref())?;
        send_json(&mut socket, identify).await?;
        let identified = receive_json(&mut socket, settings.timeout).await?;
        if identified.get("op").and_then(Value::as_u64) != Some(2)
        {
            return Err(AppError::protocol(format!(
                "OBS WebSocket identify failed: {}",
                identified
                    .get("d")
                    .cloned()
                    .unwrap_or(Value::Null),
            )));
        }
        let (sender, receiver) = mpsc::channel(64);
        tokio::spawn(run_actor(socket, receiver));
        Ok(Self {
            sender,
            health: ComponentHealth {
                component: "obs-websocket".to_owned(),
                ready: true,
                detail: "OBS WebSocket v5 identified".to_owned(),
            },
            subtitle_input: settings
                .subtitle_input
                .filter(|value| !value.trim().is_empty()),
        })
    }

    pub fn health(&self) -> &ComponentHealth
    {
        &self.health
    }

    async fn send(&self, command: Command) -> Result<(), AppError>
    {
        self.sender
            .send(command)
            .await
            .map_err(|_| AppError::unavailable("OBS WebSocket actor stopped"))
    }
}

#[async_trait]
impl StageExecutor for ObsWebSocketStage
{
    fn capabilities(&self) -> std::collections::BTreeSet<StageCapability>
    {
        std::collections::BTreeSet::from([
            StageCapability::Hotkey,
            StageCapability::Interrupt,
            StageCapability::Scene,
            StageCapability::Subtitle,
        ])
    }

    async fn health(&self) -> ComponentHealth
    {
        self.health.clone()
    }

    async fn execute(&mut self, action: StageAction) -> Result<(), AppError>
    {
        action.validate()?;
        match action
        {
            StageAction::Subtitle {
                text,
                duration_ms,
            } =>
            {
                let input = self.subtitle_input.clone().ok_or_else(||
                {
                    AppError::configuration(
                        "OBS subtitle action requires subtitle_input configuration",
                    )
                })?;
                self.send(Command::Subtitle {
                    input,
                    text,
                    duration_ms,
                })
                .await
            }
            StageAction::Scene { scene } => self.send(Command::Scene(scene)).await,
            StageAction::Hotkey { id } => self.send(Command::Hotkey(id)).await,
            StageAction::Stop => self.interrupt().await,
            StageAction::Speak { .. }
            | StageAction::Expression { .. }
            | StageAction::Mouth { .. } => Err(AppError::configuration(
                "OBS WebSocket stage supports subtitle, scene and hotkey actions only",
            )),
        }
    }

    async fn interrupt(&mut self) -> Result<(), AppError>
    {
        self.send(Command::Stop(self.subtitle_input.clone())).await
    }
}

enum Command
{
    Subtitle {
        input: String,
        text: String,
        duration_ms: u64,
    },
    Scene(String),
    Hotkey(String),
    Stop(Option<String>),
}

async fn run_actor(mut socket: ObsSocket, mut receiver: mpsc::Receiver<Command>)
{
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
                let Some(request) = command_request(command) else
                {
                    continue;
                };
                if send_json(&mut socket, request).await.is_err()
                {
                    break;
                }
            }
            message = socket.next() =>
            {
                match message
                {
                    Some(Ok(Message::Close(_))) | Some(Err(_)) | None => break,
                    Some(_) =>
                    {
                    }
                }
            }
        }
    }
}

fn command_request(command: Command) -> Option<Value>
{
    match command
    {
        Command::Subtitle {
            input,
            text,
            duration_ms,
        } =>
        {
            let _ = duration_ms;
            Some(request("SetInputSettings", json!({
                "inputName": input,
                "inputSettings": { "text": text },
                "overlay": true,
            })))
        }
        Command::Scene(scene) => Some(request("SetCurrentProgramScene", json!({
            "sceneName": scene,
        }))),
        Command::Hotkey(id) => Some(request("TriggerHotkeyByName", json!({
            "hotkeyName": id,
        }))),
        Command::Stop(Some(input)) => Some(request("SetInputSettings", json!({
            "inputName": input,
            "inputSettings": { "text": "" },
            "overlay": true,
        }))),
        Command::Stop(None) => None,
    }
}
fn request(request_type: &str, request_data: Value) -> Value
{
    json!({
        "op": 6,
        "d": {
            "requestType": request_type,
            "requestId": Uuid::new_v4().to_string(),
            "requestData": request_data,
        },
    })
}

fn identify_request(hello: &Value, password: Option<&str>) -> Result<Value, AppError>
{
    if hello.get("op").and_then(Value::as_u64) != Some(0)
    {
        return Err(AppError::protocol("OBS WebSocket did not send Hello"));
    }
    let mut data = json!({ "rpcVersion": 1 });
    let authentication = hello
        .get("d")
        .and_then(|data| data.get("authentication"));
    if let Some(authentication) = authentication
    {
        let password = password
            .filter(|value| !value.is_empty())
            .ok_or_else(|| AppError::configuration("OBS password is required by the server"))?;
        let salt = authentication
            .get("salt")
            .and_then(Value::as_str)
            .ok_or_else(|| AppError::protocol("OBS Hello authentication salt is missing"))?;
        let challenge = authentication
            .get("challenge")
            .and_then(Value::as_str)
            .ok_or_else(|| AppError::protocol("OBS Hello authentication challenge is missing"))?;
        data["authentication"] = Value::String(authentication_value(password, salt, challenge));
    }
    Ok(json!({ "op": 1, "d": data }))
}

fn authentication_value(password: &str, salt: &str, challenge: &str) -> String
{
    let secret = digest(&SHA256, format!("{password}{salt}").as_bytes());
    let secret = STANDARD.encode(secret.as_ref());
    let auth = digest(&SHA256, format!("{secret}{challenge}").as_bytes());
    STANDARD.encode(auth.as_ref())
}

async fn receive_json(socket: &mut ObsSocket, timeout: Duration) -> Result<Value, AppError>
{
    loop
    {
        let message = tokio::time::timeout(timeout, socket.next())
            .await
            .map_err(|_| AppError::connectivity("OBS WebSocket response timed out"))?
            .ok_or_else(|| AppError::connectivity("OBS WebSocket closed during handshake"))?
            .map_err(|error| AppError::connectivity(format!("OBS WebSocket read failed: {error}")))?;
        match message
        {
            Message::Text(text) =>
            {
                return serde_json::from_str(&text)
                    .map_err(|error| AppError::protocol(format!("invalid OBS JSON: {error}")));
            }
            Message::Binary(bytes) =>
            {
                return serde_json::from_slice(&bytes)
                    .map_err(|error| AppError::protocol(format!("invalid OBS JSON: {error}")));
            }
            Message::Close(_) =>
            {
                return Err(AppError::connectivity("OBS WebSocket closed during handshake"));
            }
            Message::Ping(_) | Message::Pong(_) | Message::Frame(_) =>
            {
            }
        }
    }
}

async fn send_json(socket: &mut ObsSocket, value: Value) -> Result<(), AppError>
{
    socket
        .send(Message::Text(value.to_string().into()))
        .await
        .map_err(|error| AppError::connectivity(format!("OBS WebSocket write failed: {error}")))
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn rejects_invalid_settings()
    {
        assert!(ObsSettings::new("", 4455).is_err());
        assert!(ObsSettings::new("127.0.0.1", 0).is_err());
    }

    #[test]
    fn builds_authenticated_identify_request()
    {
        let hello = json!({
            "op": 0,
            "d": {
                "authentication": {
                    "salt": "salt",
                    "challenge": "challenge"
                }
            }
        });
        let request = identify_request(&hello, Some("password")).expect("identify builds");
        assert_eq!(request["op"], 1);
        assert!(request["d"]["authentication"].as_str().is_some());
    }

    #[test]
    fn builds_scene_and_hotkey_requests()
    {
        let scene = command_request(Command::Scene("main".to_owned())).expect("scene request");
        assert_eq!(scene["op"], 6);
        assert_eq!(scene["d"]["requestType"], "SetCurrentProgramScene");
        let hotkey = command_request(Command::Hotkey("start".to_owned())).expect("hotkey request");
        assert_eq!(hotkey["d"]["requestType"], "TriggerHotkeyByName");
    }
}