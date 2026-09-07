use super::*;

#[test]
fn launch_failure_is_reported() {
    let missing = std::env::temp_dir().join(format!("aiex-absent-{}.exe", uuid::Uuid::new_v4()));
    assert!(ManagedService::start_command(&mut Command::new(missing)).is_err());
}

#[cfg(windows)]
#[test]
fn owned_process_exits_after_its_lifetime_pipe_closes() {
    let mut command = Command::new("powershell.exe");
    command.args([
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "[Console]::In.ReadToEnd() | Out-Null",
    ]);
    let mut service = ManagedService::start_command(&mut command).unwrap();
    assert!(service.child.try_wait().unwrap().is_none());
    service
        .shutdown()
        .expect("pipe closure permits graceful exit");
    assert!(service.child.try_wait().unwrap().unwrap().success());
}

#[cfg(windows)]
#[test]
fn early_service_exit_is_reported_once_without_waiting_for_window_close() {
    let mut command = Command::new("powershell.exe");
    command.args(["-NoProfile", "-NonInteractive", "-Command", "exit 7"]);
    let mut service = ManagedService::start_command(&mut command).unwrap();
    let deadline = Instant::now() + Duration::from_secs(10);
    let failure = loop {
        if let Some(failure) = service.take_failure() {
            break failure;
        }
        assert!(
            Instant::now() < deadline,
            "owned child should exit promptly"
        );
        std::thread::sleep(Duration::from_millis(20));
    };
    assert!(failure.contains("7"));
    assert!(failure.contains("连接设置"));
    assert_eq!(service.take_failure(), None);
}
