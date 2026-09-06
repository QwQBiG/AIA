use super::*;
use ai_ex_domain::{PersonaSnapshot, SystemEvent};
use tokio::io::{AsyncReadExt, AsyncWriteExt};

async fn read_request(stream: &mut tokio::net::TcpStream) -> (bool, Vec<u8>)
{
    let mut bytes = Vec::new();
    let mut buffer = [0; 4096];
    let boundary = loop
    {
        let count = stream.read(&mut buffer).await.unwrap();
        assert!(count > 0 && bytes.len() < 65_536);
        bytes.extend_from_slice(&buffer[..count]);
        if let Some(position) = bytes.windows(4).position(|part| part == b"\r\n\r\n")
        {
            break position + 4;
        }
    };
    let header = String::from_utf8_lossy(&bytes[..boundary]);
    let chat = header.starts_with("POST /api/chat ");
    let length: usize = header.lines().find_map(|line|
        line.to_ascii_lowercase().strip_prefix("content-length:").map(|value| value.trim().parse().unwrap())).unwrap_or(0);
    assert!(length < 65_536);
    while bytes.len() < boundary + length
    {
        let count = stream.read(&mut buffer).await.unwrap();
        assert!(count > 0);
        bytes.extend_from_slice(&buffer[..count]);
    }
    (chat, bytes[boundary..boundary + length].to_vec())
}

async fn complete_turn(service: &ServiceProcess, text: &str)
{
    let ControlPayload::Events(before) = service.client.send(ControlCommand::Events { after: 0, limit: 1000 }).await.unwrap() else { panic!("events expected"); };
    let after = before.last().map(|event| event.sequence).unwrap_or(0);
    service.client.send(ControlCommand::Submit { text: text.to_owned() }).await.unwrap();
    tokio::time::timeout(Duration::from_secs(3), async
    {
        loop
        {
            let ControlPayload::Events(batch) = service.client.send(ControlCommand::Events { after, limit: 1000 }).await.unwrap() else { panic!("events expected"); };
            if let Some(fault) = batch.iter().find(|event| matches!(event.event, SystemEvent::Fault { .. }))
            {
                panic!("turn failed: {:?}; service log: {}", fault.event, fs::read_to_string(service.directory.join("stderr.log")).unwrap());
            }
            if batch.iter().any(|event| matches!(event.event, SystemEvent::TurnFinished { .. }))
            {
                break;
            }
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
    }).await.unwrap();
}

#[tokio::test]
async fn service_switches_profile_without_leaking_history_or_recalled_memory()
{
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!("http://{}", listener.local_addr().unwrap());
    let (sent, mut captured) = tokio::sync::mpsc::channel(8);
    let server = tokio::spawn(async move
    {
        loop
        {
            let (mut stream, _) = listener.accept().await.unwrap();
            let (chat, request) = read_request(&mut stream).await;
            let body = if chat
            {
                sent.send(serde_json::from_slice::<serde_json::Value>(&request).unwrap()).await.unwrap();
                "{\"message\":{\"role\":\"assistant\",\"content\":\"answer.\"},\"done\":true}\n"
            }
            else
            {
                "{\"models\":[]}"
            };
            let response = format!("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}", body.len());
            stream.write_all(response.as_bytes()).await.unwrap();
        }
    });
    let mut service = ServiceProcess::with_memory("--managed", true, &url, true);
    service.ready().await;
    complete_turn(&service, "shared clue: default-only tea").await;
    captured.recv().await.unwrap();
    let host = PersonaSnapshot { profile_id: "host".to_owned(), name: "Host".to_owned(), ..Default::default() };
    service.client.send(ControlCommand::SetPersona { profile: host.clone() }).await.unwrap();
    complete_turn(&service, "shared clue: host-only coffee").await;
    let request = captured.recv().await.unwrap().to_string();
    assert!(!request.contains("default-only tea"));
    service.client.send(ControlCommand::SetPersona { profile: PersonaSnapshot::default() }).await.unwrap();
    complete_turn(&service, "shared clue").await;
    let request = captured.recv().await.unwrap().to_string();
    assert!(request.contains("default-only tea"));
    assert!(!request.contains("host-only coffee"));
    service.client.send(ControlCommand::SetPersona { profile: host }).await.unwrap();
    complete_turn(&service, "shared clue").await;
    let request = captured.recv().await.unwrap().to_string();
    assert!(request.contains("host-only coffee"));
    assert!(!request.contains("default-only tea"));
    drop(service.child.stdin.take());
    service.exited().await;
    let config_path = service.directory.join("service.toml");
    let mut config = ai_ex_config::AppConfig::parse(&fs::read_to_string(&config_path).unwrap()).unwrap();
    config.persona.profile_id = "host".to_owned();
    fs::write(&config_path, config.to_toml().unwrap()).unwrap();
    service.child = Command::new(env!("CARGO_BIN_EXE_ai-ex-service"))
        .current_dir(&service.directory).args(["--config", "service.toml", "--managed"])
        .stdin(Stdio::piped())
        .stdout(File::create(service.directory.join("stdout.log")).unwrap())
        .stderr(File::create(service.directory.join("stderr.log")).unwrap())
        .spawn().unwrap();
    service.ready().await;
    complete_turn(&service, "shared clue").await;
    let request = captured.recv().await.unwrap().to_string();
    assert!(request.contains("host-only coffee"));
    assert!(!request.contains("default-only tea"));
    let ControlPayload::Persona(profile) = service.client.send(ControlCommand::Persona).await.unwrap() else { panic!("persona expected"); };
    assert_eq!(profile.profile_id, "host");
    drop(service.child.stdin.take());
    service.exited().await;
    server.abort();
    let _ignored = server.await;
}
