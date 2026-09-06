use super::*;
use tokio::io::AsyncBufReadExt;
use tokio::net::TcpListener;

#[tokio::test]
async fn times_out_after_partial_response_and_allows_a_later_request()
{
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let mut client = ControlClient::new(
        &listener.local_addr().unwrap().to_string(),
        "x".repeat(32),
        4096,
    ).unwrap();
    client.request_timeout = Duration::from_millis(100);
    let server = tokio::spawn(async move
    {
        let (first, _) = listener.accept().await.unwrap();
        let mut first = BufReader::new(first);
        let mut request = String::new();
        first.read_line(&mut request).await.unwrap();
        first.get_mut().write_all(b"{\"status\":").await.unwrap();
        // Keep the first connection open without completing its JSON line.
        let (second, _) = listener.accept().await.unwrap();
        let mut second = BufReader::new(second);
        request.clear();
        second.read_line(&mut request).await.unwrap();
        let request: ControlRequest = serde_json::from_str(&request).unwrap();
        assert_eq!(request.command, ControlCommand::EmergencyStop);
        let response = ControlResponse::Success {
            request_id: request.request_id,
            payload: ControlPayload::Accepted,
        };
        let mut bytes = serde_json::to_vec(&response).unwrap();
        bytes.push(b'\n');
        second.get_mut().write_all(&bytes).await.unwrap();
        drop(first);
    });
    let error = tokio::time::timeout(
        Duration::from_secs(2), client.send(ControlCommand::Status),
    ).await.expect("request must finish").unwrap_err();
    assert_eq!(error.kind, ai_ex_domain::ErrorKind::Connectivity);
    assert!(error.message.contains("timed out"));
    // A timed-out command is never automatically replayed.
    client.request_timeout = Duration::from_secs(2);
    assert_eq!(client.send(ControlCommand::EmergencyStop).await.unwrap(), ControlPayload::Accepted);
    server.await.unwrap();
}

#[tokio::test]
async fn preserves_protocol_error_for_mismatched_response_id()
{
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let client = ControlClient::new(
        &listener.local_addr().unwrap().to_string(), "x".repeat(32), 4096,
    ).unwrap();
    let server = tokio::spawn(async move
    {
        let (stream, _) = listener.accept().await.unwrap();
        let mut stream = BufReader::new(stream);
        let mut request = String::new();
        stream.read_line(&mut request).await.unwrap();
        let response = ControlResponse::Success {
            request_id: Uuid::nil(),
            payload: ControlPayload::Accepted,
        };
        let mut bytes = serde_json::to_vec(&response).unwrap();
        bytes.push(b'\n');
        stream.get_mut().write_all(&bytes).await.unwrap();
    });
    let error = client.send(ControlCommand::Status).await.unwrap_err();
    assert_eq!(error.kind, ai_ex_domain::ErrorKind::Protocol);
    assert!(error.message.contains("request ID mismatch"));
    server.await.unwrap();
}
