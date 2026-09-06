use super::*;

#[test]
fn launch_failure_is_reported()
{
    let missing = std::env::temp_dir().join(format!("aiex-absent-{}.exe", uuid::Uuid::new_v4()));
    assert!(ManagedService::start_command(&mut Command::new(missing)).is_err());
}

#[cfg(windows)]
#[test]
fn owned_process_exits_after_its_lifetime_pipe_closes()
{
    let mut command = Command::new("powershell.exe");
    command.args(["-NoProfile", "-NonInteractive", "-Command", "[Console]::In.ReadToEnd() | Out-Null"]);
    let mut service = ManagedService::start_command(&mut command).unwrap();
    assert!(service.child.try_wait().unwrap().is_none());
    service.shutdown().expect("pipe closure permits graceful exit");
    assert!(service.child.try_wait().unwrap().unwrap().success());
}
