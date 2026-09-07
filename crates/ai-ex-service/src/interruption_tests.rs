use super::*;
use ai_ex_core::TurnOutcome;
use ai_ex_stage::{StageAction, StageCapability};
use std::sync::atomic::{AtomicBool, Ordering};
use tokio::sync::Mutex;

struct SlowPresentation {
    stalled: Arc<AtomicBool>,
    stopped: Arc<AtomicBool>,
    stall_subtitle: bool,
}

#[async_trait]
impl StageExecutor for SlowPresentation {
    fn capabilities(&self) -> BTreeSet<StageCapability> {
        BTreeSet::from([
            StageCapability::Expression,
            StageCapability::Mouth,
            StageCapability::Subtitle,
        ])
    }
    async fn health(&self) -> ComponentHealth {
        ComponentHealth::ready("test-presentation")
    }
    async fn execute(&mut self, action: StageAction) -> Result<(), AppError> {
        if self.stalled.load(Ordering::Acquire)
            && self.stall_subtitle
            && matches!(action, StageAction::Subtitle { .. })
        {
            std::future::pending::<()>().await;
        }
        Ok(())
    }
    async fn interrupt(&mut self) -> Result<(), AppError> {
        self.stopped.store(true, Ordering::Release);
        if self.stalled.load(Ordering::Acquire) && !self.stall_subtitle {
            std::future::pending::<()>().await;
        }
        Ok(())
    }
}

#[tokio::test]
async fn stalled_presentation_cannot_block_real_speech_cancellation_or_recovery() {
    for stall_subtitle in [false, true] {
        let stalled = Arc::new(AtomicBool::new(true));
        let stopped = Arc::new(AtomicBool::new(false));
        let other_stopped = Arc::new(AtomicBool::new(false));
        let (speech, mut receiver) = SpeechQueue::new(2).unwrap();
        let player = receiver.player();
        let mut router = StageRouter::new();
        router.push(speech);
        router.push(SlowPresentation {
            stalled: stalled.clone(),
            stopped: stopped.clone(),
            stall_subtitle,
        });
        router.push(SlowPresentation {
            stalled: Arc::new(AtomicBool::new(false)),
            stopped: other_stopped.clone(),
            stall_subtitle: false,
        });
        let stage = StageOutput::new(router);
        let events = EventHub::new(64).unwrap();
        let mut observed = events.subscribe();
        let runtime = Runtime::new(
            ReplyModel {
                reply: "Hello.".to_owned(),
                requests: Arc::new(Mutex::new(Vec::new())),
            },
            stage.speech(),
            stage.avatar(),
            MemoryStore::disabled(),
            events,
        );
        let handle = spawn_runtime(runtime, 4).unwrap();
        tokio::time::timeout(Duration::from_secs(2), handle.submit("hello"))
            .await
            .unwrap()
            .unwrap();
        let job = receiver.receive().await.unwrap();
        assert_eq!(job.text, "Hello.");
        assert!(stopped.load(Ordering::Acquire));
        assert!(
            other_stopped.load(Ordering::Acquire),
            "a stalled stage must not prevent other stages from stopping"
        );
        let mut degraded = false;
        while let Ok(event) = observed.try_recv() {
            degraded |= matches!(
                event.event,
                SystemEvent::ComponentHealthChanged { ready: false, .. }
            );
        }
        assert!(degraded, "presentation failure must be observable");
        let stopper = handle.clone();
        let stopping = tokio::spawn(async move { stopper.interrupt("stop audio").await });
        tokio::time::timeout(
            Duration::from_millis(200),
            player.wait_for_cancellation(&job),
        )
        .await
        .expect("audio stops before slow presentation cleanup finishes");
        tokio::time::timeout(Duration::from_secs(2), stopping)
            .await
            .unwrap()
            .unwrap()
            .unwrap();
        stalled.store(false, Ordering::Release);
        tokio::time::timeout(Duration::from_secs(2), handle.submit("recovered"))
            .await
            .unwrap()
            .unwrap();
        assert_eq!(receiver.receive().await.unwrap().text, "Ready.");
        let mut recovered = false;
        while let Ok(event) = observed.try_recv() {
            recovered |= matches!(
                event.event,
                SystemEvent::ComponentHealthChanged { ready: true, .. }
            );
        }
        assert!(recovered);
        handle.shutdown().await.unwrap();
    }
}

struct ReplyModel {
    reply: String,
    requests: Arc<Mutex<Vec<ModelRequest>>>,
}

#[async_trait]
impl LanguageModelPort for ReplyModel {
    async fn stream(
        &mut self,
        request: ModelRequest,
    ) -> Result<tokio::sync::mpsc::Receiver<Result<String, AppError>>, AppError> {
        let mut requests = self.requests.lock().await;
        requests.push(request);
        let reply = if requests.len() == 1 {
            self.reply.clone()
        } else {
            "Ready.".to_owned()
        };
        let (sender, receiver) = tokio::sync::mpsc::channel(1);
        sender.send(Ok(reply)).await.unwrap();
        Ok(receiver)
    }

    async fn cancel(&mut self, _turn_id: TurnId) -> Result<(), AppError> {
        Ok(())
    }
}

#[tokio::test]
async fn full_audio_queue_and_final_unpunctuated_sentence_remain_interruptible() {
    for reply in ["First. Second.", "First. unfinished tail"] {
        let path =
            std::env::temp_dir().join(format!("companion-interrupt-{}.jsonl", TurnId::new().0));
        let memory = MemoryStore::open(&path).await.unwrap();
        let (speech, mut receiver) = SpeechQueue::new(1).unwrap();
        let mut router = StageRouter::new();
        router.push(speech);
        router.push(VtsClient::disabled());
        let stage = StageOutput::new(router);
        let events = EventHub::new(64).unwrap();
        let requests = Arc::new(Mutex::new(Vec::new()));
        let runtime = Runtime::new(
            ReplyModel {
                reply: reply.to_owned(),
                requests: requests.clone(),
            },
            stage.speech(),
            stage.avatar(),
            memory.clone(),
            events.clone(),
        );
        let handle = spawn_runtime(runtime, 4).unwrap();
        let submitter = handle.clone();
        let turn = tokio::spawn(async move { submitter.submit("initial").await });
        let mut snapshots = events.watch();
        tokio::time::timeout(Duration::from_secs(2), async {
            while snapshots.borrow().sentences_ready < 2 {
                snapshots.changed().await.unwrap();
            }
        })
        .await
        .expect("the second sentence is waiting for queue capacity");
        assert_eq!(events.current().turns_completed, 0);
        handle.interrupt("user spoke").await.unwrap();
        let outcome = tokio::time::timeout(Duration::from_secs(1), turn)
            .await
            .unwrap()
            .unwrap()
            .unwrap();
        assert!(matches!(outcome, TurnOutcome::Interrupted(_)));
        assert!(
            memory.is_empty().await,
            "an interrupted answer must not reach persistent memory"
        );
        let (next, fresh) = tokio::time::timeout(Duration::from_secs(2), async {
            tokio::join!(handle.submit("continue"), receiver.receive())
        })
        .await
        .unwrap();
        let next = next.unwrap();
        let TurnOutcome::Completed(next_id) = next else {
            panic!("next turn must complete")
        };
        let fresh = fresh.unwrap();
        assert_eq!(
            fresh.turn_id, next_id,
            "cancelled queued speech is discarded"
        );
        assert_eq!(fresh.text, "Ready.");
        assert_eq!(memory.len().await, 1);
        assert!(
            !requests.lock().await[1]
                .messages
                .iter()
                .any(|message| message.content == "initial")
        );
        handle.shutdown().await.unwrap();
        std::fs::remove_file(path).unwrap();
    }
}
