use super::*;

struct ProfileMemory;

#[async_trait]
impl MemoryPort for ProfileMemory
{
    async fn select_profile(&mut self, _profile_id: &str) -> Result<(), AppError>
    {
        Ok(())
    }

    async fn recall(&self, _query: &str, _limit: usize) -> Result<Vec<Message>, AppError>
    {
        Ok(Vec::new())
    }

    async fn remember(&mut self, _turn_id: TurnId, _user: String, _assistant: String) -> Result<(), AppError>
    {
        Ok(())
    }
}

#[tokio::test]
async fn edits_keep_history_but_identity_switches_clear_it_and_stop_previous_audio()
{
    let request = Arc::new(Mutex::new(None));
    let state = Arc::new(TestState::default());
    let runtime = Runtime::new(CaptureModel(request.clone()), TestSpeech(state.clone()), TestAvatar(state.clone()), ProfileMemory, TestEvents);
    let handle = spawn_runtime(runtime, 4).unwrap();
    handle.set_persona("friend".to_owned(), "friend version one".to_owned()).await.unwrap();
    handle.submit("friend-only history").await.unwrap();
    handle.set_persona("friend".to_owned(), "friend version two".to_owned()).await.unwrap();
    handle.submit("continue").await.unwrap();
    let edited = request.lock().await.take().unwrap();
    assert!(edited.messages.iter().any(|message| message.content == "friend-only history"));
    assert_eq!(edited.messages[0].content, "friend version two");

    state.speech_interrupted.store(false, Ordering::Release);
    handle.set_persona("host".to_owned(), "host identity".to_owned()).await.unwrap();
    assert!(state.speech_interrupted.load(Ordering::Acquire));
    handle.submit("new scene").await.unwrap();
    let switched = request.lock().await.take().unwrap();
    assert_eq!(switched.messages, vec![Message::new(Role::System, "host identity"), Message::new(Role::User, "new scene")]);
    handle.set_persona("friend".to_owned(), "friend version two".to_owned()).await.unwrap();
    handle.submit("return").await.unwrap();
    assert_eq!(request.lock().await.take().unwrap().messages.len(), 2);
    handle.shutdown().await.unwrap();
}

#[tokio::test]
async fn failed_scope_switch_preserves_identity_prompt_and_history()
{
    let request = Arc::new(Mutex::new(None));
    let state = Arc::new(TestState::default());
    let mut runtime = Runtime::new(CaptureModel(request.clone()), TestSpeech(state.clone()), TestAvatar(state.clone()), TestMemory(state), TestEvents);
    runtime.set_persona("default".to_owned(), "original persona".to_owned()).await.unwrap();
    runtime.run_turn("original history").await.unwrap();
    assert!(runtime.set_persona("new".to_owned(), "replacement".to_owned()).await.is_err());
    assert!(runtime.set_persona(" ".to_owned(), "invalid".to_owned()).await.is_err());
    runtime.run_turn("still here").await.unwrap();
    let captured = request.lock().await.take().unwrap();
    assert_eq!(captured.messages[0].content, "original persona");
    assert!(captured.messages.iter().any(|message| message.content == "original history"));
}

#[tokio::test]
async fn active_turn_rejects_identity_switch_without_interrupting_the_reply()
{
    let state = Arc::new(TestState::default());
    let runtime = Runtime::new(TestModel { state: state.clone(), sender: None }, TestSpeech(state.clone()), TestAvatar(state.clone()), ProfileMemory, TestEvents);
    let handle = spawn_runtime(runtime, 4).unwrap();
    let turn_handle = handle.clone();
    let turn = tokio::spawn(async move { turn_handle.submit("still speaking").await });
    tokio::time::timeout(Duration::from_secs(2), async
    {
        while !state.model_started.load(Ordering::Acquire)
        {
            tokio::task::yield_now().await;
        }
    }).await.unwrap();
    assert!(handle.set_persona("other".to_owned(), "other persona".to_owned()).await.is_err());
    assert!(!state.speech_interrupted.load(Ordering::Acquire));
    handle.shutdown().await.unwrap();
    assert!(matches!(turn.await.unwrap().unwrap(), TurnOutcome::Shutdown(_)));
}
