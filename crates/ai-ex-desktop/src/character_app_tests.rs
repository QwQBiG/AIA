use super::*;

#[test]
fn imported_character_enters_the_editor_without_changing_the_running_identity()
{
    let (_events, receiver) = std::sync::mpsc::channel();
    let (commands, mut sent) = tokio::sync::mpsc::unbounded_channel();
    let mut app = DesktopApp::with_storage(WorkerHandle { commands, events: receiver }, false, None);
    let context = egui::Context::default();
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/characters/companion.toml");
    app.character_files.begin(&context, crate::character_files::FileAction::Import(path));
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(3);
    while app.character_files.is_loading()
    {
        let _output = context.run_ui(egui::RawInput::default(), |ui| app.show_persona_panel(ui));
        assert!(std::time::Instant::now() < deadline);
        std::thread::sleep(std::time::Duration::from_millis(5));
    }
    assert_eq!(app.persona.profile_id, "aiex.companion");
    assert_eq!(app.active_persona.profile_id, "default");
    assert!(app.persona_dirty);
    assert!(!app.persona_apply_pending);
    assert!(sent.try_recv().is_err());
}

#[test]
fn persona_polling_never_applies_a_draft_or_acknowledges_a_pending_command()
{
    let (events, receiver) = std::sync::mpsc::channel();
    let (commands, _receiver) = tokio::sync::mpsc::unbounded_channel();
    let mut app = DesktopApp::with_storage(WorkerHandle { commands, events: receiver }, false, None);
    let draft = PersonaSnapshot { profile_id: "friend".to_owned(), name: "Friend".to_owned(), ..Default::default() };
    app.persona = draft.clone();
    app.persona_dirty = true;
    events.send(WorkerEvent::Persona(PersonaSnapshot::default())).unwrap();
    app.drain_events();
    assert_eq!(app.persona, draft);
    assert_eq!(app.active_persona.profile_id, "default");
    app.persona_apply_pending = true;
    events.send(WorkerEvent::Persona(PersonaSnapshot::default())).unwrap();
    events.send(WorkerEvent::Failure("unrelated poll failure".to_owned())).unwrap();
    app.drain_events();
    assert!(app.persona_apply_pending);
    assert_eq!(app.persona, draft);
    events.send(WorkerEvent::PersonaApplied(draft.clone())).unwrap();
    app.drain_events();
    assert_eq!(app.active_persona, draft);
    assert!(!app.persona_apply_pending);
    assert!(!app.persona_dirty);
    app.persona.name = "unsaved edit".to_owned();
    app.persona_dirty = true;
    app.persona_apply_pending = true;
    events.send(WorkerEvent::PersonaApplyFailed("rejected".to_owned())).unwrap();
    app.drain_events();
    assert!(!app.persona_apply_pending);
    assert_eq!(app.persona.name, "unsaved edit");
    assert_eq!(app.active_persona, draft);
}
