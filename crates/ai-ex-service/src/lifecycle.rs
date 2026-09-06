use std::io::Read;

use ai_ex_domain::AppError;

pub async fn wait_for_shutdown(managed: bool) -> Result<(), AppError>
{
    tracing::info!(managed, "background service ready");
    tokio::select!
    {
        result = tokio::signal::ctrl_c() => result.map_err(|error|
            AppError::unavailable(format!("cannot receive shutdown signal: {error}"))),
        result = parent_closed(), if managed => result,
    }
}

async fn parent_closed() -> Result<(), AppError>
{
    let (sender, receiver) = tokio::sync::oneshot::channel();
    // A dedicated thread avoids an uncancellable Tokio stdin task keeping the
    // async runtime alive after Ctrl+C. Pipe EOF also covers parent crashes.
    std::thread::Builder::new().name("ai-ex-parent-lifetime".to_owned()).spawn(move ||
    {
        let mut input = std::io::stdin().lock();
        let mut buffer = [0; 64];
        let result = loop
        {
            match input.read(&mut buffer)
            {
                Ok(0) => break Ok(()),
                Ok(_) => {},
                Err(error) if error.kind() == std::io::ErrorKind::Interrupted => {},
                Err(error) => break Err(AppError::unavailable(format!("parent pipe failed: {error}"))),
            }
        };
        let _ignored = sender.send(result);
    }).map_err(|error| AppError::unavailable(format!("cannot watch parent lifetime: {error}")))?;
    receiver.await.map_err(|_| AppError::unavailable("parent lifetime watcher stopped"))?
}
