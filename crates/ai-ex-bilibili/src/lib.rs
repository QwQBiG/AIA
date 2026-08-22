#![forbid(unsafe_code)]

use std::env;
use std::io::Read;
use std::sync::{Arc, RwLock};
use std::time::Duration;

use ai_ex_domain::{AppError, ComponentHealth};
use flate2::read::ZlibDecoder;
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
const HEARTBEAT_INTERVAL: Duration = Duration::from_secs(30);
const MAX_PACKET_BYTES: usize = 8 * 1024 * 1024;

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

    pub fn validate(&self) -> Result<(), AppError>
    {
        if self.room_id == 0
            || (!self.endpoint.starts_with("ws://") && !self.endpoint.starts_with("wss://"))
            || self.reconnect_delay_ms == 0
        {
            return Err(AppError::configuration("invalid bilibili connector settings"));
        }
        Ok(())
    }
}

pub struct BilibiliConnector
{
    settings: BilibiliSettings,
    connection: Option<BilibiliConnection>,
    health: Arc<RwLock<ComponentHealth>>,
}

impl BilibiliConnector
{
    pub fn new(settings: BilibiliSettings) -> Self
    {
        Self {
            settings,
            connection: None,
            health: Arc::new(RwLock::new(ComponentHealth::unavailable(
                "bilibili",
                "not connected",
            ))),
        }
    }

    pub fn health(&self) -> ComponentHealth
    {
        self.health
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .clone()
    }

    pub fn health_handle(&self) -> Arc<RwLock<ComponentHealth>>
    {
        Arc::clone(&self.health)
    }

    pub async fn next_events(&mut self) -> Result<Vec<LiveEventEnvelope>, AppError>
    {
        if let Err(error) = self.settings.validate()
        {
            self.set_health(false, error.to_string());
            return Err(error);
        }
        loop
        {
            if self.connection.is_none()
            {
                self.set_health(
                    false,
                    format!("connecting to room {}", self.settings.room_id),
                );
                match BilibiliConnection::connect(&self.settings).await
                {
                    Ok(connection) =>
                    {
                        self.connection = Some(connection);
                        self.set_health(true, "connected");
                    }
                    Err(error) =>
                    {
                        self.set_health(false, format!("connect failed: {error}"));
                        return Err(error);
                    }
                }
            }
            let result = self
                .connection
                .as_mut()
                .expect("connection exists")
                .next_events()
                .await;
            match result
            {
                Ok(events) =>
                {
                    self.set_health(true, format!("connected; received {} event(s)", events.len()));
                    return Ok(events);
                }
                Err(error) =>
                {
                    self.connection = None;
                    self.set_health(false, format!("connection lost: {error}"));
                    tokio::time::sleep(Duration::from_millis(
                        self.settings.reconnect_delay_ms,
                    ))
                    .await;
                }
            }
        }
    }

    fn set_health(&self, ready: bool, detail: impl Into<String>)
    {
        if let Ok(mut health) = self.health.write()
        {
            health.ready = ready;
            health.detail = detail.into();
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
        settings.validate()?;
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
        let mut heartbeat = tokio::time::interval(HEARTBEAT_INTERVAL);
        heartbeat.tick().await;
        loop
        {
            let message = tokio::select!
            {
                _ = heartbeat.tick() =>
                {
                    let packet = encode_packet(2, 1, &[])?;
                    self.socket
                        .send(Message::Binary(packet.into()))
                        .await
                        .map_err(|error| AppError::connectivity(format!("bilibili heartbeat failed: {error}")))?;
                    continue;
                }
                message = self.socket.next() => message
            };
            let message = message
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
        "protover": 2,
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
    if total as usize > MAX_PACKET_BYTES
    {
        return Err(AppError::configuration("bilibili packet exceeds safety limit"));
    }
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
    decode_packets_at_depth(bytes, 0)
}

fn decode_packets_at_depth(
    bytes: &[u8],
    depth: usize,
) -> Result<Vec<BilibiliPacket>, AppError>
{
    if depth > 4
    {
        return Err(AppError::protocol("bilibili packet nesting is too deep"));
    }
    if bytes.len() > MAX_PACKET_BYTES
    {
        return Err(AppError::protocol("bilibili packet exceeds safety limit"));
    }
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
        if header < 16
            || total < header
            || total > bytes.len() - offset
            || total > MAX_PACKET_BYTES
        {
            return Err(AppError::protocol("invalid bilibili packet length"));
        }
        let body = &bytes[offset + header..offset + total];
        match version
        {
            0 | 1 =>
            {
                packets.push(BilibiliPacket {
                    version,
                    operation,
                    body: body.to_vec(),
                });
            }
            2 =>
            {
                let mut decoder = ZlibDecoder::new(body);
                let mut decompressed = Vec::new();
                decoder
                    .read_to_end(&mut decompressed)
                    .map_err(|error| AppError::protocol(format!("bilibili zlib decompression failed: {error}")))?;
                if decompressed.len() > MAX_PACKET_BYTES
                {
                    return Err(AppError::protocol("bilibili decompressed packet exceeds safety limit"));
                }
                packets.extend(decode_packets_at_depth(&decompressed, depth + 1)?);
            }
            3 =>
            {
                return Err(AppError::protocol(
                    "bilibili brotli compression is not enabled in this build",
                ));
            }
            _ =>
            {
                return Err(AppError::protocol(format!(
                    "unsupported bilibili packet version {version}"
                )));
            }
        }
        offset += total;
    }
    Ok(packets)
}
fn value_id(value: Option<&Value>) -> Option<String>
{
    value.and_then(|value|
    {
        value
            .as_str()
            .map(str::to_owned)
            .or_else(|| value.as_u64().map(|number| number.to_string()))
    })
}

fn platform_event_id(data: &Value, primary: &str, discriminator: &str) -> String
{
    if let Some(id) = value_id(data.get(primary))
    {
        return id;
    }
    let user = value_id(data.get("uid")).unwrap_or_else(|| "unknown-user".to_owned());
    let timestamp = value_id(data.get("timestamp")).unwrap_or_else(|| "unknown-time".to_owned());
    let kind = value_id(data.get(discriminator)).unwrap_or_else(|| "unknown-event".to_owned());
    format!("{user}:{timestamp}:{kind}")
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
            event_id: platform_event_id(data, "tid", "giftId"),
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
            event_id: platform_event_id(data, "id", "price"),
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
    use ai_ex_event_bus::{EventBus, EventPolicy, PublishOutcome};

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
    fn decodes_zlib_compressed_inner_packets()
    {
        use flate2::write::ZlibEncoder;
        use flate2::Compression;
        use std::io::Write;

        let inner = encode_packet(5, 1, b"{}").expect("inner packet builds");
        let mut encoder = ZlibEncoder::new(Vec::new(), Compression::default());
        encoder.write_all(&inner).expect("packet compresses");
        let compressed = encoder.finish().expect("compression finishes");
        let packet = encode_packet(5, 2, &compressed).expect("outer packet builds");
        let decoded = decode_packets(&packet).expect("compressed packet decodes");
        assert_eq!(decoded.len(), 1);
        assert_eq!(decoded[0].version, 1);
        assert_eq!(decoded[0].body, b"{}");
    }

    #[test]
    fn decodes_nested_zlib_packets()
    {
        use flate2::write::ZlibEncoder;
        use flate2::Compression;
        use std::io::Write;

        let inner = encode_packet(5, 1, b"{\"cmd\":\"LIVE\"}").expect("inner packet builds");
        let mut first_encoder = ZlibEncoder::new(Vec::new(), Compression::default());
        first_encoder.write_all(&inner).expect("first compression writes");
        let first = first_encoder.finish().expect("first compression finishes");
        let nested = encode_packet(5, 2, &first).expect("nested packet builds");
        let mut second_encoder = ZlibEncoder::new(Vec::new(), Compression::default());
        second_encoder.write_all(&nested).expect("second compression writes");
        let second = second_encoder.finish().expect("second compression finishes");
        let packet = encode_packet(5, 2, &second).expect("outer packet builds");

        let decoded = decode_packets(&packet).expect("nested packet decodes");
        assert_eq!(decoded.len(), 1);
        assert_eq!(decoded[0].body, b"{\"cmd\":\"LIVE\"}");
    }

    #[test]
    fn preserves_batch_order_and_rejects_truncation()
    {
        let first = encode_packet(5, 1, b"first").expect("first packet builds");
        let second = encode_packet(5, 1, b"second").expect("second packet builds");
        let mut batch = first;
        batch.extend_from_slice(&second);
        let decoded = decode_packets(&batch).expect("batch decodes");
        assert_eq!(decoded.len(), 2);
        assert_eq!(decoded[0].body, b"first");
        assert_eq!(decoded[1].body, b"second");

        let truncated = &batch[..10];
        assert!(decode_packets(truncated).is_err());
    }

    #[test]
    fn maps_gift_follow_and_super_chat_events()
    {
        let gift = map_message(
            Uuid::new_v4(),
            123,
            json!({
                "cmd": "SEND_GIFT",
                "data": {
                    "giftId": 7,
                    "tid": "gift-1",
                    "uid": 42,
                    "uname": "小明",
                    "giftName": "星星",
                    "num": 2
                }
            })
            .to_string()
            .as_bytes(),
        )
        .expect("gift parses")
        .expect("gift maps");
        assert!(matches!(gift.payload, LiveEvent::Gift { count: 2, event_id, .. } if event_id == "gift-1"));

        let follow = map_message(
            Uuid::new_v4(),
            123,
            json!({
                "cmd": "INTERACT_WORD",
                "data": {"msg_type": 2, "uid": 42, "uname": "小明"}
            })
            .to_string()
            .as_bytes(),
        )
        .expect("follow parses")
        .expect("follow maps");
        assert!(matches!(follow.payload, LiveEvent::Follow { .. }));

        let donation = map_message(
            Uuid::new_v4(),
            123,
            json!({
                "cmd": "SUPER_CHAT_MESSAGE",
                "data": {
                    "id": 9,
                    "uid": 42,
                    "price": 30,
                    "message": "支持你",
                    "user_info": {"uname": "小明"}
                }
            })
            .to_string()
            .as_bytes(),
        )
        .expect("donation parses")
        .expect("donation maps");
        assert!(matches!(
            donation.payload,
            LiveEvent::Donation {
                amount_minor: 3000,
                ..
            }
        ));
    }
    async fn run_fake_bilibili_sessions(
        listener: tokio::net::TcpListener,
        body: Vec<u8>,
        sessions: usize,
    )
    {
        for _ in 0..sessions
        {
            let (stream, _) = listener.accept().await.expect("fake Bilibili accepts");
            let mut socket = tokio_tungstenite::accept_async(stream)
                .await
                .expect("fake Bilibili websocket accepts");
            let handshake = socket
                .next()
                .await
                .expect("fake Bilibili receives handshake")
                .expect("fake Bilibili handshake frame");
            let handshake = match handshake
            {
                Message::Binary(bytes) => bytes,
                other => panic!("unexpected Bilibili handshake frame: {other:?}"),
            };
            let packets = decode_packets(&handshake).expect("Bilibili handshake decodes");
            assert_eq!(packets.len(), 1);
            assert_eq!(packets[0].operation, 7);
            assert!(String::from_utf8_lossy(&packets[0].body).contains("roomid"));
            let event_packet = encode_packet(5, 1, &body).expect("event packet builds");
            socket
                .send(Message::Binary(event_packet.into()))
                .await
                .expect("fake Bilibili sends event");
        }
    }

    #[tokio::test]
    async fn connector_reconnects_and_event_bus_deduplicates_platform_id()
    {
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0")
            .await
            .expect("Bilibili listener binds");
        let port = listener
            .local_addr()
            .expect("Bilibili listener address")
            .port();
        let body = json!({
            "cmd": "SEND_GIFT",
            "data": {
                "tid": "gift-reconnect-1",
                "uid": 42,
                "uname": "小明",
                "giftName": "星星",
                "num": 1
            }
        })
        .to_string()
        .into_bytes();
        let server = tokio::spawn(run_fake_bilibili_sessions(listener, body, 2));
        let mut settings = BilibiliSettings::new(123).expect("Bilibili settings");
        settings.endpoint = format!("ws://127.0.0.1:{port}");
        settings.reconnect_delay_ms = 1;
        let mut connector = BilibiliConnector::new(settings);
        assert!(!connector.health().ready);
        let first = connector.next_events().await.expect("first event batch");
        assert!(connector.health().ready);
        let second = connector.next_events().await.expect("reconnected event batch");
        assert_eq!(first.len(), 1);
        assert_eq!(second.len(), 1);
        assert!(matches!(
            &first[0].payload,
            LiveEvent::Gift { event_id, .. } if event_id == "gift-reconnect-1"
        ));
        assert!(matches!(
            &second[0].payload,
            LiveEvent::Gift { event_id, .. } if event_id == "gift-reconnect-1"
        ));
        let (mut bus, _receiver) = EventBus::new(EventPolicy {
            per_user_cooldown_ms: 1_500,
            global_cooldown_ms: 0,
            max_queue: 8,
        });
        assert_eq!(bus.publish(first[0].clone()), PublishOutcome::Accepted);
        assert_eq!(bus.publish(second[0].clone()), PublishOutcome::Duplicate);
        server.await.expect("fake Bilibili task");
    }
    #[test]
    fn rejects_brotli_packets_until_codec_is_enabled()
    {
        let packet = encode_packet(5, 3, b"compressed").expect("packet builds");
        let error = decode_packets(&packet).expect_err("brotli must be explicit");
        assert!(error.to_string().contains("brotli compression"));
    }

    #[test]
    fn validates_settings_before_connecting()
    {
        let mut settings = BilibiliSettings::new(123).expect("settings build");
        assert!(settings.validate().is_ok());
        settings.endpoint = "https://example.invalid/sub".to_owned();
        assert!(settings.validate().is_err());
        settings.endpoint = "wss://example.invalid/sub".to_owned();
        settings.reconnect_delay_ms = 0;
        assert!(settings.validate().is_err());
    }

    #[test]
    fn rejects_oversized_packets_before_allocation()
    {
        let body = vec![0_u8; 8 * 1024 * 1024];
        let error = encode_packet(5, 1, &body).expect_err("safety limit must reject packet");
        assert!(error.to_string().contains("safety limit"));
    }
}
