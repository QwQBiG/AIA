use super::*;
use ai_ex_core::SpeechPort;
use tokio::io::AsyncReadExt;

#[tokio::test]
async fn interrupted_synthesis_does_not_delay_speech_worker_shutdown()
{
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let tts = GptSovitsClient::new(GptSovitsSettings {
        base_url: format!("http://{}", listener.local_addr().unwrap()),
        timeout: Duration::from_secs(30),
        text_lang: "zh".to_owned(), ref_audio_path: "test-reference.wav".to_owned(),
        prompt_text: String::new(), prompt_lang: "zh".to_owned(),
    }).unwrap();
    let (started, received) = tokio::sync::oneshot::channel();
    let (release, held) = tokio::sync::oneshot::channel();
    let server = tokio::spawn(async move
    {
        let (mut stream, _) = listener.accept().await.unwrap();
        assert!(stream.read(&mut [0; 1024]).await.unwrap() > 0);
        started.send(()).unwrap();
        held.await.unwrap();
        drop(stream);
    });
    let (mut speech, receiver) = SpeechQueue::new(2).unwrap();
    let player = receiver.player();
    speech.enqueue(TurnId::new(), "hello".to_owned()).await.unwrap();
    let events = EventHub::new(8).unwrap();
    let worker = tokio::spawn(run_speech_worker(receiver, Some(tts), player, events.clone()));
    tokio::time::timeout(Duration::from_secs(2), received).await.unwrap().unwrap();
    SpeechPort::interrupt(&mut speech).await.unwrap();
    drop(speech);
    tokio::time::timeout(Duration::from_secs(1), worker).await.expect("cancelled TTS must not wait for HTTP timeout").unwrap();
    assert_eq!(events.current().playback, Default::default());
    release.send(()).unwrap();
    server.await.unwrap();
}
