use super::*;

struct SlowRecall {
    entered: Arc<Notify>,
    stalled: AtomicBool,
    state: Arc<TestState>,
}

#[async_trait]
impl MemoryPort for SlowRecall {
    async fn recall(&self, _query: &str, _limit: usize) -> Result<Vec<Message>, AppError> {
        if self.stalled.swap(false, Ordering::AcqRel) {
            self.entered.notify_one();
            std::future::pending::<()>().await;
        }
        Ok(Vec::new())
    }
    async fn remember(
        &mut self,
        _turn_id: TurnId,
        _user: String,
        _assistant: String,
    ) -> Result<(), AppError> {
        self.state.remembered.fetch_add(1, Ordering::AcqRel);
        Ok(())
    }
}

#[tokio::test]
async fn memory_recall_can_be_interrupted_before_model_starts() {
    let state = Arc::new(TestState::default());
    let entered = Arc::new(Notify::new());
    let captured = Arc::new(Mutex::new(None));
    let runtime = Runtime::new(
        CaptureModel(captured.clone()),
        TestSpeech(state.clone()),
        TestAvatar(state.clone()),
        SlowRecall {
            entered: entered.clone(),
            stalled: AtomicBool::new(true),
            state: state.clone(),
        },
        TestEvents,
    );
    let handle = spawn_runtime(runtime, 2).unwrap();
    let submitter = handle.clone();
    let turn = tokio::spawn(async move { submitter.submit("discard").await });
    tokio::time::timeout(Duration::from_secs(2), entered.notified())
        .await
        .unwrap();
    handle.interrupt("stop").await.unwrap();
    assert!(matches!(
        tokio::time::timeout(Duration::from_secs(2), turn)
            .await
            .unwrap()
            .unwrap()
            .unwrap(),
        TurnOutcome::Interrupted(_)
    ));
    assert!(captured.lock().await.is_none());
    assert_eq!(state.remembered.load(Ordering::Acquire), 0);
    handle.submit("retry").await.unwrap();
    assert_eq!(state.remembered.load(Ordering::Acquire), 1);
    handle.shutdown().await.unwrap();
}

#[tokio::test]
async fn pending_turn_queue_is_bounded_without_losing_interrupts() {
    let state = Arc::new(TestState::default());
    let entered = Arc::new(Notify::new());
    let runtime = Runtime::new(
        SlowModel {
            entered: entered.clone(),
            state: state.clone(),
            slow_cancel: false,
        },
        TestSpeech(state.clone()),
        TestAvatar(state.clone()),
        TestMemory(state),
        TestEvents,
    );
    let handle = spawn_runtime(runtime, 2).unwrap();
    let submitter = handle.clone();
    let active = tokio::spawn(async move { submitter.submit("active").await });
    tokio::time::timeout(Duration::from_secs(2), entered.notified())
        .await
        .unwrap();
    let mut waiting = tokio::task::JoinSet::new();
    for index in 0..8 {
        let submitter = handle.clone();
        waiting.spawn(async move { submitter.submit(format!("queued-{index}")).await });
    }
    tokio::time::timeout(Duration::from_secs(2), async {
        for _ in 0..6 {
            let error = waiting.join_next().await.unwrap().unwrap().unwrap_err();
            assert!(error.to_string().contains("conversation queue is full"));
        }
    })
    .await
    .unwrap();
    handle.interrupt("stop").await.unwrap();
    assert!(matches!(
        active.await.unwrap().unwrap(),
        TurnOutcome::Interrupted(_)
    ));
    tokio::time::timeout(Duration::from_secs(2), async {
        while let Some(result) = waiting.join_next().await {
            assert!(matches!(
                result.unwrap().unwrap(),
                TurnOutcome::Completed(_)
            ));
        }
    })
    .await
    .unwrap();
    handle.shutdown().await.unwrap();
}

#[tokio::test]
async fn closed_control_channel_does_not_spin_or_cancel_generation() {
    let state = Arc::new(TestState::default());
    let mut runtime = Runtime::new(
        CaptureModel(Arc::new(Mutex::new(None))),
        TestSpeech(state.clone()),
        TestAvatar(state.clone()),
        TestMemory(state.clone()),
        TestEvents,
    );
    let (sender, mut receiver) = mpsc::channel(1);
    drop(sender);
    assert!(matches!(
        tokio::time::timeout(
            Duration::from_secs(2),
            runtime.run_turn_controlled("hello", &mut receiver)
        )
        .await
        .unwrap()
        .unwrap(),
        TurnOutcome::Completed(_)
    ));
    assert_eq!(state.remembered.load(Ordering::Acquire), 1);
}

#[tokio::test]
async fn admission_acknowledges_queue_space_before_generation_and_rejects_overflow() {
    let state = Arc::new(TestState::default());
    let entered = Arc::new(Notify::new());
    let runtime = Runtime::new(
        SlowModel {
            entered: entered.clone(),
            state: state.clone(),
            slow_cancel: false,
        },
        TestSpeech(state.clone()),
        TestAvatar(state.clone()),
        TestMemory(state),
        TestEvents,
    );
    let handle = spawn_runtime(runtime, 1).unwrap();
    let active = tokio::time::timeout(Duration::from_secs(2), handle.enqueue("active"))
        .await
        .unwrap()
        .expect("admission must not wait for model completion");
    tokio::time::timeout(Duration::from_secs(2), entered.notified())
        .await
        .unwrap();
    let queued = tokio::time::timeout(Duration::from_secs(2), handle.enqueue("queued"))
        .await
        .unwrap()
        .expect("the single pending position is available");
    let rejected = tokio::time::timeout(Duration::from_secs(2), handle.enqueue("overflow"))
        .await
        .unwrap()
        .err()
        .expect("full queue must not acknowledge admission");
    assert!(rejected.message.contains("conversation queue is full"));
    handle.interrupt("continue queued turn").await.unwrap();
    assert!(matches!(
        tokio::time::timeout(Duration::from_secs(2), active.wait())
            .await
            .unwrap()
            .unwrap(),
        TurnOutcome::Interrupted(_)
    ));
    assert!(matches!(
        tokio::time::timeout(Duration::from_secs(2), queued.wait())
            .await
            .unwrap()
            .unwrap(),
        TurnOutcome::Completed(_)
    ));
    handle.shutdown().await.unwrap();
    assert!(handle.enqueue("after shutdown").await.is_err());
}

#[tokio::test]
async fn enqueue_cancelled_before_admission_does_not_start_a_turn() {
    use std::future::Future;
    use std::task::{Context, Waker};

    let state = Arc::new(TestState::default());
    let runtime = Runtime::new(
        CaptureModel(Arc::new(Mutex::new(None))),
        TestSpeech(state.clone()),
        TestAvatar(state.clone()),
        TestMemory(state.clone()),
        TestEvents,
    );
    let handle = spawn_runtime(runtime, 2).unwrap();
    // Current-thread execution keeps the actor idle until this test yields.
    // Queue the request, then cancel it while it is still waiting for admission.
    let mut cancelled = Box::pin(handle.enqueue("cancelled before admission"));
    assert!(
        cancelled
            .as_mut()
            .poll(&mut Context::from_waker(Waker::noop()))
            .is_pending()
    );
    drop(cancelled);
    handle.submit("the only admitted turn").await.unwrap();
    assert_eq!(state.remembered.load(Ordering::Acquire), 1);
    handle.shutdown().await.unwrap();
}

struct SlowModel {
    entered: Arc<Notify>,
    state: Arc<TestState>,
    slow_cancel: bool,
}

#[async_trait]
impl LanguageModelPort for SlowModel {
    async fn stream(
        &mut self,
        request: ModelRequest,
    ) -> Result<mpsc::Receiver<Result<String, AppError>>, AppError> {
        if self.state.stream_count.fetch_add(1, Ordering::AcqRel) == 0 {
            self.entered.notify_one();
            std::future::pending::<()>().await;
        }
        CaptureModel(Arc::new(Mutex::new(None)))
            .stream(request)
            .await
    }

    async fn cancel(&mut self, _turn_id: TurnId) -> Result<(), AppError> {
        assert!(self.state.speech_interrupted.load(Ordering::Acquire));
        if self.slow_cancel {
            std::future::pending::<()>().await;
        }
        Ok(())
    }
}

#[tokio::test]
async fn pending_model_start_and_cancel_do_not_prevent_next_turn() {
    for slow_cancel in [false, true] {
        let state = Arc::new(TestState::default());
        let entered = Arc::new(Notify::new());
        let runtime = Runtime::new(
            SlowModel {
                entered: entered.clone(),
                state: state.clone(),
                slow_cancel,
            },
            TestSpeech(state.clone()),
            TestAvatar(state.clone()),
            TestMemory(state.clone()),
            TestEvents,
        );
        let handle = spawn_runtime(runtime, 4).unwrap();
        let submitter = handle.clone();
        let turn = tokio::spawn(async move { submitter.submit("discard").await });
        tokio::time::timeout(Duration::from_secs(2), entered.notified())
            .await
            .unwrap();
        state.speech_interrupted.store(false, Ordering::Release);
        handle.interrupt("barge in").await.unwrap();
        let result = tokio::time::timeout(Duration::from_secs(2), turn)
            .await
            .unwrap()
            .unwrap();
        if slow_cancel {
            assert!(
                result
                    .unwrap_err()
                    .to_string()
                    .contains("model cancellation")
            );
        } else {
            assert!(matches!(result.unwrap(), TurnOutcome::Interrupted(_)));
        }
        assert_eq!(state.remembered.load(Ordering::Acquire), 0);
        assert!(matches!(
            handle.submit("retry").await.unwrap(),
            TurnOutcome::Completed(_)
        ));
        assert_eq!(state.remembered.load(Ordering::Acquire), 1);
        handle.shutdown().await.unwrap();
    }
}

struct GatedMemory {
    entered: Arc<Notify>,
    release: Arc<Notify>,
    state: Arc<TestState>,
}

#[async_trait]
impl MemoryPort for GatedMemory {
    async fn recall(&self, _query: &str, _limit: usize) -> Result<Vec<Message>, AppError> {
        Ok(Vec::new())
    }
    async fn remember(
        &mut self,
        _turn_id: TurnId,
        _user: String,
        _assistant: String,
    ) -> Result<(), AppError> {
        self.entered.notify_one();
        self.release.notified().await;
        self.state.remembered.fetch_add(1, Ordering::AcqRel);
        Ok(())
    }
}

#[tokio::test]
async fn repeated_interrupts_and_shutdown_preserve_in_flight_memory_write() {
    let state = Arc::new(TestState::default());
    let entered = Arc::new(Notify::new());
    let release = Arc::new(Notify::new());
    let runtime = Runtime::new(
        CaptureModel(Arc::new(Mutex::new(None))),
        TestSpeech(state.clone()),
        TestAvatar(state.clone()),
        GatedMemory {
            entered: entered.clone(),
            release: release.clone(),
            state: state.clone(),
        },
        TestEvents,
    );
    let handle = spawn_runtime(runtime, 4).unwrap();
    let submitter = handle.clone();
    let turn = tokio::spawn(async move { submitter.submit("remember").await });
    tokio::time::timeout(Duration::from_secs(2), entered.notified())
        .await
        .unwrap();
    state.speech_interrupted.store(false, Ordering::Release);
    assert_eq!(
        handle
            .memory(ai_ex_domain::MemoryRequest::Remember {
                profile_id: "default".to_owned(),
                text: "must wait for commit".to_owned(),
            })
            .await
            .unwrap_err()
            .kind,
        ai_ex_domain::ErrorKind::InvalidTransition,
    );
    tokio::time::timeout(Duration::from_secs(2), async {
        for _ in 0..32 {
            handle.interrupt("stop").await.unwrap();
        }
        while !state.speech_interrupted.load(Ordering::Acquire) {
            tokio::task::yield_now().await;
        }
    })
    .await
    .expect("control must not deadlock under repeated interrupts");
    let stopper = handle.clone();
    let mut shutdown = tokio::spawn(async move { stopper.shutdown().await });
    assert!(
        tokio::time::timeout(Duration::from_millis(30), &mut shutdown)
            .await
            .is_err()
    );
    assert_eq!(state.remembered.load(Ordering::Acquire), 0);
    release.notify_one();
    tokio::time::timeout(Duration::from_secs(2), shutdown)
        .await
        .unwrap()
        .unwrap()
        .unwrap();
    assert!(matches!(
        turn.await.unwrap().unwrap(),
        TurnOutcome::Shutdown(_)
    ));
    assert_eq!(state.remembered.load(Ordering::Acquire), 1);
}
