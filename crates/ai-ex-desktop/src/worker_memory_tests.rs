use super::*;
use ai_ex_control::MemoryReply;
use ai_ex_domain::{MemoryRequest, MemoryResponse};

fn request() -> MemoryRequest {
    MemoryRequest::Remember {
        profile_id: "default".to_owned(),
        text: "称呼我小林".to_owned(),
    }
}

#[tokio::test]
async fn memory_worker_preserves_request_ids_and_reply_snapshot_over_a_real_socket() {
    let reply = Box::new(MemoryReply {
        response: MemoryResponse::Changed,
        snapshot: RuntimeSnapshot {
            last_sequence: 41,
            ..Default::default()
        },
    });
    let (client, server) = scripted_responses(vec![
        (
            ControlCommand::Memory { request: request() },
            Ok(ControlPayload::Memory(reply.clone())),
        ),
        (
            ControlCommand::Memory { request: request() },
            Err(AppError::invalid_transition("memory changed")),
        ),
    ])
    .await;
    let (commands, receiver) = tokio::sync::mpsc::unbounded_channel();
    let (events, received) = mpsc::channel();
    let worker = tokio::spawn(async move {
        run_commands(&client, receiver, &events, &AtomicU64::new(0)).await;
    });
    for request_id in [17, 18] {
        commands
            .send(WorkerCommand::Memory {
                request_id,
                request: request(),
            })
            .unwrap();
    }
    wait_event(&received, |event| {
        matches!(event, WorkerEvent::Memory {
        request_id: 17, result: Ok(returned),
    } if returned == &reply)
    })
    .await;
    wait_event(&received, |event| matches!(event, WorkerEvent::Memory {
        request_id: 18, result: Err(error),
    } if error.kind == ai_ex_domain::ErrorKind::InvalidTransition && error.message == "memory changed")).await;
    server.await.unwrap();
    drop(commands);
    tokio::time::timeout(Duration::from_secs(2), worker)
        .await
        .unwrap()
        .unwrap();
}

#[tokio::test]
async fn full_regular_queue_returns_memory_failure_with_its_original_request_id() {
    let (commands, receiver) = tokio::sync::mpsc::unbounded_channel();
    let (regular, mut waiting) = tokio::sync::mpsc::channel(1);
    let (urgent, _priority) = tokio::sync::watch::channel(UrgentCommands::default());
    let (events, received) = mpsc::channel();
    commands
        .send(WorkerCommand::Submit("occupy the queue".to_owned()))
        .unwrap();
    commands
        .send(WorkerCommand::Memory {
            request_id: 99,
            request: request(),
        })
        .unwrap();
    drop(commands);
    route_commands(receiver, regular, urgent, &events, &AtomicU64::new(0)).await;
    assert!(matches!(
        waiting.try_recv().unwrap().command,
        WorkerCommand::Submit(_)
    ));
    assert!(waiting.try_recv().is_err());
    assert!(matches!(received.try_recv().unwrap(), WorkerEvent::Memory {
        request_id: 99, result: Err(error),
    } if error.kind == ai_ex_domain::ErrorKind::Unavailable));
    assert!(received.try_recv().is_err());
}
