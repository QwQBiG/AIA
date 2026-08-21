#![forbid(unsafe_code)]

use std::env;
use std::time::Duration;

use ai_ex_domain::AppError;
use ai_ex_event_bus::{envelope, LiveEvent, LiveEventEnvelope};
use futures_util::{SinkExt, StreamExt};
use serde_json::{json, Value};
use tokio_tungstenite::{
    connect_async,
    tungstenite::Message,
    MaybeTlsStream,
    WebSocketStream,
};
use uuid::Uuid;

const DEFAULT_ENDPOINT: &str = "wss://broadcastlv.chat.bilibili.com:443/sub";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BilibiliSettings
{
    pub room_id: u64,
    pub endpoint: String,
    pub cookie_env: Option<String>,
    pub reconnect_delay_ms: u64,
}

impl BilibiliSettings
{
    pub fn new(room_id: u64) -> Result<Self, AppError>
    {
        if room_id == 0
        {
            return Err(AppError::configuration("bilibili room_id must be positive"));
        }
        Ok(Self {
            room_id,
            endpoint: DEFAULT_ENDPOINT.to_owned(),
            cookie_env: None,
            reconnect_delay_ms: 2_000,
        })
    }
}

pub struct BilibiliConnector
{
    settings: BilibiliSettings,
    connection: Option<BilibiliConnection>,
}

impl BilibiliConnector
{
    pub fn new(settings: BilibiliSettings) -> Self
    {
        Self {
            settings,
            connection: None,
        }
    }

    pub async fn next_events(&mut self) -> Result<Vec<LiveEventEnvelope>, AppError>
    {
        loop
        {
            if self.connection.is_none()
            {
                self.connection = Some(BilibiliConnection::connect(&self.settings).await?);
            }
            let result = self
                .connection
                .as_mut()
                .expect("connection exists")
                .next_events()
                .await;
            match result
            {
                Ok(events) => return Ok(events),
                Err(_) =>
                {
                    self.connection = None;
                    tokio::time::sleep(Duration::from_millis(
                        self.settings.reconnect_delay_ms,
                    ))
                    .await;
                }
            }
        }
    }
}

pub struct BilibiliConnection
{
    socket: WebSocketStream<MaybeTlsStream<tokio::net::TcpStream>>,
    session_id: Uuid,
    room_id: u64,
}

impl BilibiliConnection
{
    pub async fn connect(settings: &BilibiliSettings) -> Result<Self, AppError>
    {
        let (mut socket, _response) = connect_async(&settings.endpoint)
            .await
            .map_err(|error| AppError::connectivity(format!("bilibili websocket connect failed: {error}")))?;
        let handshake = build_handshake(settings.room_id, settings.cookie_env.as_deref())?;
        socket
            .send(Message::Binary(handshake.into()))
            .await
            .map_err(|error| AppError::connectivity(format!("bilibili handshake failed: {error}")))?;
        Ok(Self {
            socket,
            session_id: Uuid::new_v4(),
            room_id: settings.room_id,
        })
    }

    pub async fn next_events(&mut self) -> Result<Vec<LiveEventEnvelope>, AppError>
    {
        loop
        {
            let message = self
                .socket
                .next()
                .await
                .ok_or_else(|| AppError::connectivity("bilibili websocket closed"))?
                .map_err(|error| AppError::connectivity(format!("bilibili websocket read failed: {error}")))?;
            match message
            {
                Message::Binary(bytes) =>
                {
                    let packets = decode_packets(&bytes)?;
                    let mut events = Vec::new();
                    for packet in packets
                    {
                        if packet.operation != 5
                        {
                            continue;
                        }
                        let Some(event) = map_message(
                            self.session_id,
                            self.room_id,
                            &packet.body,
                        )? else
                        {
                            continue;
                        };
                        events.push(event);
                    }
                    if !events.is_empty()
                    {
                        return Ok(events);
                    }
                }
                Message::Ping(payload) =>
                {
                    self.socket
                        .send(Message::Pong(payload))
                        .await
                        .map_err(|error| AppError::connectivity(error.to_string()))?;
                }
                Message::Close(_) =>
                {
                    return Err(AppError::connectivity("bilibili websocket closed by peer"));
                }
                Message::Text(_) | Message::Pong(_) | Message::Frame(_) => {}
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BilibiliPacket
{
    pub version: u16,
    pub operation: u32,
    pub body: Vec<u8>,
}

pub fn build_handshake(room_id: u64, cookie_env: Option<&str>) -> Result<Vec<u8>, AppError>
{
    let uid = cookie_env
        .and_then(|name| env::var(name).ok())
        .and_then(|value| {
            value
                .split(';')
                .find_map(|part| part.trim().strip_prefix("DedeUserID="))
                .map(str::to_owned)
        })
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or_default();
    let body = json!({
        "uid": uid,
        "roomid": room_id,
        "protover": 1,
        "platform": "web",
        "type": 2,
        "key": ""
    });
    encode_packet(7, 1, body.to_string().as_bytes())
}

pub fn encode_packet(operation: u32, version: u16, body: &[u8]) -> Result<Vec<u8>, AppError>
{
    let total = 16_usize
        .checked_add(body.len())
        .ok_or_else(|| AppError::configuration("bilibili packet is too large"))?;
    let total = u32::try_from(total)
        .map_err(|_| AppError::configuration("bilibili packet exceeds protocol size"))?;
    let mut packet = Vec::with_capacity(total as usize);
    packet.extend_from_slice(&total.to_be_bytes());
    packet.extend_from_slice(&16_u16.to_be_bytes());
    packet.extend_from_slice(&version.to_be_bytes());
    packet.extend_from_slice(&operation.to_be_bytes());
    packet.extend_from_slice(&1_u32.to_be_bytes());
    packet.extend_from_slice(body);
    Ok(packet)
}

pub fn decode_packets(bytes: &[u8]) -> Result<Vec<BilibiliPacket>, AppError>
{
    let mut offset = 0_usize;
    let mut packets = Vec::new();
    while offset < bytes.len()
    {
        if bytes.len() - offset < 16
        {
            return Err(AppError::protocol("bilibili packet header is truncated"));
        }
        let total = u32::from_be_bytes(bytes[offset..offset + 4].try_into().unwrap()) as usize;
        let header = u16::from_be_bytes(bytes[offset + 4..offset + 6].try_into().unwrap()) as usize;
        let version = u16::from_be_bytes(bytes[offset + 6..offset + 8].try_into().unwrap());
        let operation = u32::from_be_bytes(bytes[offset + 8..offset + 12].try_into().unwrap());
        if header < 16 || total < header || total > bytes.len() - offset
        {
            return Err(AppError::protocol("invalid bilibili packet length"));
        }
        if version != 0 && version != 1
        {
            return Err(AppError::protocol(format!(
                "unsupported bilibili packet compression version {version}; enable a boundary decompressor"
            )));
        }
        packets.push(BilibiliPacket {
            version,
            operation,
            body: bytes[offset + header..offset + total].to_vec(),
        });
        offset += total;
    }
    Ok(packets)
}

fn map_message(session_id: Uuid, room_id: u64, body: &[u8]) -> Result<Option<LiveEventEnvelope>, AppError>
{
    let raw: Value = serde_json::from_slice(body)
        .map_err(|error| AppError::protocol(format!("invalid bilibili message JSON: {error}")))?;
    let command = raw.get("cmd").and_then(Value::as_str).unwrap_or_default();
    let data = raw.get("data").unwrap_or(&Value::Null);
    let source = format!("bilibili:{room_id}");
    let event = if command.starts_with("DANMU_MSG")
    {
        let info = data.as_array().cloned().unwrap_or_default();
        let text = info.get(1).and_then(Value::as_str).unwrap_or_default();
        let user = info
            .get(2)
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let user_id = user.first().and_then(Value::as_u64).unwrap_or_default().to_string();
        let display_name = user.get(1).and_then(Value::as_str).unwrap_or("观众");
        Some(LiveEvent::ChatMessage {
            message_id: format!("{user_id}:{text}"),
            user_id,
            display_name: display_name.to_owned(),
            text: text.to_owned(),
        })
    }
    else if command == "SEND_GIFT"
    {
        Some(LiveEvent::Gift {
            event_id: data.get("giftId").and_then(Value::as_u64).unwrap_or_default().to_string(),
            user_id: data.get("uid").and_then(Value::as_u64).unwrap_or_default().to_string(),
            display_name: data.get("uname").and_then(Value::as_str).unwrap_or("观众").to_owned(),
            gift_name: data.get("giftName").and_then(Value::as_str).unwrap_or("礼物").to_owned(),
            count: data.get("num").and_then(Value::as_u64).unwrap_or(1) as u32,
        })
    }
    else if command == "INTERACT_WORD"
        && data.get("msg_type").and_then(Value::as_u64) == Some(2)
    {
        Some(LiveEvent::Follow {
            user_id: data.get("uid").and_then(Value::as_u64).unwrap_or_default().to_string(),
            display_name: data.get("uname").and_then(Value::as_str).unwrap_or("观众").to_owned(),
        })
    }
    else if command == "SUPER_CHAT_MESSAGE"
    {
        Some(LiveEvent::Donation {
            event_id: data.get("id").and_then(Value::as_u64).unwrap_or_default().to_string(),
            user_id: data.get("uid").and_then(Value::as_u64).unwrap_or_default().to_string(),
            display_name: data.get("user_info").and_then(|value| value.get("uname")).and_then(Value::as_str).unwrap_or("观众").to_owned(),
            amount_minor: data.get("price").and_then(Value::as_u64).unwrap_or_default() * 100,
            currency: "CNY".to_owned(),
            message: data.get("message").and_then(Value::as_str).unwrap_or_default().to_owned(),
        })
    }
    else if command == "LIVE" || command == "PREPARING"
    {
        Some(LiveEvent::SystemNotice {
            level: "platform".to_owned(),
            text: command.to_owned(),
        })
    }
    else
    {
        None
    };
    Ok(event.map(|event| envelope(source, session_id, event)))
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn handshake_and_packet_round_trip()
    {
        let packet = build_handshake(123, None).expect("handshake builds");
        let decoded = decode_packets(&packet).expect("packet decodes");
        assert_eq!(decoded.len(), 1);
        assert_eq!(decoded[0].operation, 7);
        assert!(String::from_utf8_lossy(&decoded[0].body).contains("123"));
    }

    #[test]
    fn maps_danmaku_to_platform_neutral_chat()
    {
        let body = json!({
            "cmd": "DANMU_MSG",
            "data": [null, "你好", [42, "小明"]]
        });
        let event = map_message(Uuid::new_v4(), 123, body.to_string().as_bytes())
            .expect("message parses")
            .expect("message maps");
        assert!(matches!(event.payload, LiveEvent::ChatMessage { user_id, .. } if user_id == "42"));
    }

    #[test]
    fn rejects_compressed_packets_at_boundary()
    {
        let mut packet = encode_packet(5, 2, b"{}").expect("packet builds");
        packet[6..8].copy_from_slice(&2_u16.to_be_bytes());
        let error = decode_packets(&packet).expect_err("compression is explicit");
        assert!(error.to_string().contains("compression version"));
    }
}
