use super::*;
use ai_ex_control::{ControlRequest, ControlResponse};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::TcpListener;

#[tokio::test]
async fn persona_refresh_discards_responses_that_overlap_an_apply() {
    for changed in [false, true] {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let client = ControlClient::new(
            &listener.local_addr().unwrap().to_string(),
            "x".repeat(32),
            4096,
        )
        .unwrap();
        let epoch = std::sync::Arc::new(AtomicU64::new(0));
        let server_epoch = epoch.clone();
        let server = tokio::spawn(async move {
            let (stream, _) = listener.accept().await.unwrap();
            let mut stream = BufReader::new(stream);
            let mut line = String::new();
            stream.read_line(&mut line).await.unwrap();
            let request: ControlRequest = serde_json::from_str(&line).unwrap();
            if changed {
                server_epoch.fetch_add(2, Ordering::AcqRel);
            }
            let response = ControlResponse::Success {
                request_id: request.request_id,
                payload: ControlPayload::Persona(PersonaSnapshot::default()),
            };
            stream
                .get_mut()
                .write_all(format!("{}\n", serde_json::to_string(&response).unwrap()).as_bytes())
                .await
                .unwrap();
        });
        let result = fetch_persona_current(&client, &epoch).await.unwrap();
        assert_eq!(result.is_none(), changed);
        server.await.unwrap();
        epoch.store(3, Ordering::Release);
        assert!(
            fetch_persona_current(&client, &epoch)
                .await
                .unwrap()
                .is_none()
        );
    }
}

#[tokio::test]
async fn stalled_poll_does_not_block_interrupt_stop_or_worker_exit() {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let client = ControlClient::new(
        &listener.local_addr().unwrap().to_string(),
        "x".repeat(32),
        4096,
    )
    .unwrap();
    let (poll_started, started) = tokio::sync::oneshot::channel();
    let (release_server, released) = tokio::sync::oneshot::channel();
    let server = tokio::spawn(async move {
        let (stream, _) = listener.accept().await.unwrap();
        let mut stalled = BufReader::new(stream);
        let mut line = String::new();
        stalled.read_line(&mut line).await.unwrap();
        let request: ControlRequest = serde_json::from_str(&line).unwrap();
        assert_eq!(request.command, ControlCommand::Status);
        poll_started.send(()).unwrap();
        // Hold the status response while accepting independent commands.
        for expected in ["interrupt", "emergency_stop"] {
            let (stream, _) = listener.accept().await.unwrap();
            let mut stream = BufReader::new(stream);
            line.clear();
            stream.read_line(&mut line).await.unwrap();
            let request: ControlRequest = serde_json::from_str(&line).unwrap();
            match (expected, request.command) {
                ("interrupt", ControlCommand::Interrupt { .. }) => {}
                ("emergency_stop", ControlCommand::EmergencyStop) => {}
                _ => panic!("unexpected command while status is stalled"),
            }
            let response = ControlResponse::Success {
                request_id: request.request_id,
                payload: ControlPayload::Accepted,
            };
            let mut bytes = serde_json::to_vec(&response).unwrap();
            bytes.push(b'\n');
            stream.get_mut().write_all(&bytes).await.unwrap();
        }
        released.await.unwrap();
        drop(stalled);
    });
    let (commands, receiver) = tokio::sync::mpsc::unbounded_channel();
    let (events, received) = mpsc::channel();
    let worker = tokio::spawn(run_worker(client, receiver, events));
    tokio::time::timeout(Duration::from_secs(2), started)
        .await
        .unwrap()
        .unwrap();
    commands.send(WorkerCommand::Interrupt).unwrap();
    commands.send(WorkerCommand::EmergencyStop).unwrap();
    drop(commands);
    // Complete both commands and exit before the five-second status timeout.
    tokio::time::timeout(Duration::from_secs(2), worker)
        .await
        .expect("polling must not hold up commands or shutdown")
        .unwrap();
    let mut acknowledged = 0;
    for event in received.try_iter() {
        match event {
            WorkerEvent::Log(message) if message == "control command sent" => acknowledged += 1,
            WorkerEvent::Failure(message) => panic!("unexpected worker failure: {message}"),
            _ => {}
        }
    }
    assert_eq!(acknowledged, 2);
    release_server.send(()).unwrap();
    server.await.unwrap();
}
