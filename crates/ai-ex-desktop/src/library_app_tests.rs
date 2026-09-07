use super::*;

#[test]
fn library_selection_waits_for_service_confirmation_and_tracks_its_source() {
    let (events, receiver) = std::sync::mpsc::channel();
    let (commands, mut sent) = tokio::sync::mpsc::unbounded_channel();
    let mut app = DesktopApp::with_storage(
        WorkerHandle {
            commands,
            events: receiver,
        },
        false,
        None,
    );
    let selected = app.character_library.entries[0].draft(false);
    let original = selected.character.clone();
    let source = selected.source.clone();
    app.apply_library_draft(selected);
    let context = egui::Context::default();
    let output = context.run_ui(
        egui::RawInput {
            screen_rect: Some(egui::Rect::from_min_size(
                egui::Pos2::ZERO,
                egui::vec2(720.0, 520.0),
            )),
            ..Default::default()
        },
        |ui| app.show_character_library(ui),
    );
    assert!(output.shapes.iter().any(|shape| matches!(&shape.shape,
        egui::epaint::Shape::Text(text) if text.galley.job.text.contains("载入草稿"))));
    events
        .send(WorkerEvent::Persona(PersonaSnapshot::default()))
        .unwrap();
    app.drain_events();
    assert_eq!(app.persona, original.persona);
    assert_eq!(app.active_persona.profile_id, "default");
    assert_eq!(app.character_files.draft_source, source);
    assert!(sent.try_recv().is_err());
    app.persona.tone = "Edited tone".to_owned();
    app.character_files.author = "Local author".to_owned();
    assert_ne!(
        app.character_draft(),
        *app.character_files.baseline.as_ref().unwrap()
    );
    app.state.connection = ConnectionState::Connected;
    app.apply_pending_persona(app.persona.clone());
    let WorkerCommand::SetPersona(profile) = sent.try_recv().unwrap() else {
        panic!("expected selected persona");
    };
    events
        .send(WorkerEvent::PersonaApplied(profile.clone()))
        .unwrap();
    app.drain_events();
    assert_eq!(app.active_persona, profile);
    assert_eq!(app.active_character.author, "Local author");
    assert_eq!(app.active_source, format!("{source}（含本次编辑）"));
    assert_eq!(
        app.character_draft(),
        *app.character_files.baseline.as_ref().unwrap()
    );
    events.send(WorkerEvent::Persona(profile.clone())).unwrap();
    app.drain_events();
    assert!(app.active_source.contains("角色收藏"));
    app.character_library.remove(0).unwrap();
    assert_eq!(app.active_persona, profile);
    assert!(sent.try_recv().is_err());
    app.character_library.undo_remove().unwrap();
    assert_eq!(app.character_library.entries[0].character, original);
    events
        .send(WorkerEvent::Persona(PersonaSnapshot::default()))
        .unwrap();
    app.drain_events();
    assert_eq!(app.active_source, "服务同步（未提供包来源）");
    assert_eq!(app.character_files.author, "");
    assert_eq!(app.character_files.draft_source, app.active_source);
}

#[test]
fn independent_library_copy_has_a_new_identity_and_preserves_original_attribution() {
    let (_events, receiver) = std::sync::mpsc::channel();
    let (commands, mut sent) = tokio::sync::mpsc::unbounded_channel();
    let mut app = DesktopApp::with_storage(
        WorkerHandle {
            commands,
            events: receiver,
        },
        false,
        None,
    );
    let original = app.character_library.entries[0].character.clone();
    let first = app.character_library.entries[0].draft(true);
    let second = app.character_library.entries[0].draft(true);
    assert_ne!(
        first.character.persona.profile_id,
        original.persona.profile_id
    );
    assert_ne!(
        first.character.persona.profile_id,
        second.character.persona.profile_id
    );
    assert_eq!(first.character.persona.revision, 1);
    assert_eq!(first.character.author, original.author);
    assert_eq!(first.character.license, original.license);
    first.character.validate().unwrap();
    app.apply_library_draft(first);
    assert!(app.persona_dirty);
    assert_eq!(app.active_persona.profile_id, "default");
    assert!(sent.try_recv().is_err());
}
