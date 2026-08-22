#![forbid(unsafe_code)]

use std::sync::{Arc, RwLock};
use std::time::Duration;

use ai_ex_domain::{AppError, ComponentHealth};
use ai_ex_stage::{StageAction, StageCapability, StageExecutor};
use async_trait::async_trait;
use base64::{Engine, engine::general_purpose::STANDARD};
use futures_util::{SinkExt, StreamExt};
use ring::digest::{SHA256, digest};
use serde_json::{Value, json};
use tokio::net::TcpStream;
use tokio::sync::{mpsc, oneshot};
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
    sender: mpsc::Sender<PendingCommand>,
    health: Arc<RwLock<ComponentHealth>>,
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
        let health = Arc::new(RwLock::new(ComponentHealth {
            component: "obs-websocket".to_owned(),
            ready: true,
            detail: "OBS WebSocket v5 identified".to_owned(),
        }));
        tokio::spawn(run_actor(
            socket,
            receiver,
            settings.timeout,
            Arc::clone(&health),
        ));
        Ok(Self {
            sender,
            health,
            subtitle_input: settings
                .subtitle_input
                .filter(|value| !value.trim().is_empty()),
        })
    }

    pub fn health(&self) -> ComponentHealth
    {
        self.health
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .clone()
    }

    async fn send(&self, command: Command) -> Result<(), AppError>
    {
        let (response, receiver) = oneshot::channel();
        self.sender
            .send(PendingCommand { command, response })
            .await
            .map_err(|_| {
                self.mark_unavailable("OBS WebSocket actor stopped");
                AppError::unavailable("OBS WebSocket actor stopped")
            })?;
        match receiver.await
        {
            Ok(result) =>
            {
                if let Err(error) = &result
                {
                    self.mark_unavailable(error.to_string());
                }
                result
            }
            Err(_) =>
            {
                self.mark_unavailable("OBS WebSocket actor stopped");
                Err(AppError::unavailable("OBS WebSocket actor stopped"))
            }
        }
    }

    fn mark_unavailable(&self, detail: impl Into<String>)
    {
        if let Ok(mut health) = self.health.write()
        {
            health.ready = false;
            health.detail = detail.into();
        }
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
        ObsWebSocketStage::health(self)
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

struct PendingCommand
{
    command: Command,
    response: oneshot::Sender<Result<(), AppError>>,
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

async fn run_actor(
    mut socket: ObsSocket,
    mut receiver: mpsc::Receiver<PendingCommand>,
    timeout: Duration,
    health: Arc<RwLock<ComponentHealth>>,
)
{
    loop
    {
        tokio::select!
        {
            pending = receiver.recv() =>
            {
                let Some(PendingCommand { command, response }) = pending else
                {
                    break;
                };
                let Some(request) = command_request(command) else
                {
                    let _ignored = response.send(Ok(()));
                    continue;
                };
                let request_id = request["d"]["requestId"]
                    .as_str()
                    .unwrap_or_default()
                    .to_owned();
                let result = match send_json(&mut socket, request).await
                {
                    Ok(()) => receive_response(&mut socket, &request_id, timeout).await,
                    Err(error) => Err(error),
                };
                if let Err(error) = &result
                {
                    set_health_unavailable(&health, error.to_string());
                }
                let failed = result.is_err();
                let _ignored = response.send(result);
                if failed
                {
                    break;
                }
            }
            message = socket.next() =>
            {
                match message
                {
                    Some(Ok(Message::Close(_))) =>
                    {
                        set_health_unavailable(&health, "OBS WebSocket closed".to_owned());
                        break;
                    }
                    Some(Err(error)) =>
                    {
                        set_health_unavailable(&health, format!("OBS WebSocket read failed: {error}"));
                        break;
                    }
                    None =>
                    {
                        set_health_unavailable(&health, "OBS WebSocket stream ended".to_owned());
                        break;
                    }
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

async fn receive_response(
    socket: &mut ObsSocket,
    request_id: &str,
    timeout: Duration,
) -> Result<(), AppError>
{
    loop
    {
        let message = tokio::time::timeout(timeout, socket.next())
            .await
            .map_err(|_| AppError::connectivity("OBS WebSocket request response timed out"))?
            .ok_or_else(|| AppError::connectivity("OBS WebSocket closed while waiting for response"))?
            .map_err(|error| AppError::connectivity(format!("OBS WebSocket read failed: {error}")))?;
        let value: Value = match message
        {
            Message::Text(text) => serde_json::from_str(&text)
                .map_err(|error| AppError::protocol(format!("invalid OBS JSON: {error}")))?,
            Message::Binary(bytes) => serde_json::from_slice(&bytes)
                .map_err(|error| AppError::protocol(format!("invalid OBS JSON: {error}")))?,
            Message::Close(_) =>
            {
                return Err(AppError::connectivity(
                    "OBS WebSocket closed while waiting for response",
                ));
            }
            Message::Ping(_) | Message::Pong(_) | Message::Frame(_) => continue,
        };
        if let Some(result) = response_result(&value, request_id)
        {
            return result;
        }
    }
}
fn set_health_unavailable(health: &Arc<RwLock<ComponentHealth>>, detail: String)
{
    if let Ok(mut health) = health.write()
    {
        health.ready = false;
        health.detail = detail;
    }
}

fn response_result(value: &Value, request_id: &str) -> Option<Result<(), AppError>>
{
    if value.get("op").and_then(Value::as_u64) != Some(7)
    {
        return None;
    }
    let response_id = value["d"]["requestId"].as_str().unwrap_or_default();
    if response_id != request_id
    {
        return None;
    }
    let status = &value["d"]["requestStatus"];
    if status["result"].as_bool() == Some(true)
    {
        return Some(Ok(()));
    }
    let code = status["code"].as_u64().unwrap_or_default();
    let comment = status["comment"].as_str().unwrap_or("unknown OBS error");
    Some(Err(AppError::protocol(format!(
        "OBS request failed: code={code}, comment={comment}",
    ))))
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
    fn matches_success_and_failure_responses()
    {
        let success = json!({
            "op": 7,
            "d": {
                "requestId": "request-1",
                "requestStatus": { "result": true, "code": 100 }
            }
        });
        assert!(matches!(response_result(&success, "request-1"), Some(Ok(()))));

        let failure = json!({
            "op": 7,
            "d": {
                "requestId": "request-1",
                "requestStatus": { "result": false, "code": 402, "comment": "bad request" }
            }
        });
        let result = response_result(&failure, "request-1").expect("matching failure");
        assert!(result.is_err());
        assert!(response_result(&success, "other").is_none());
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
