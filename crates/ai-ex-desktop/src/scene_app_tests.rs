use super::*;
use ai_ex_config::character::CharacterManifest;
use ai_ex_config::scene::{SceneAppearance, SceneBody, SceneManifest};
use crate::appearance::AppearanceKind;
use crate::scene_files::ReadyScene;

fn ready() -> ReadyScene
{
    let mut character = CharacterManifest::from_persona(PersonaSnapshot { profile_id: "friend".to_owned(), name: "Friend".to_owned(), ..Default::default() });
    character.author = "Scene author".to_owned();
    ReadyScene {
        manifest: SceneManifest {
            schema_version: 1, id: "quiet".to_owned(), name: "Quiet".to_owned(), character,
            appearance: SceneAppearance { body: SceneBody::Orb, accent: [10, 80, 160], scale: 0.5, reduced_motion: true, package: None },
        }, appearance: None,
    }
}

#[test]
fn scene_waits_for_its_ack_before_committing_identity_and_appearance()
{
    let (events, receiver) = std::sync::mpsc::channel();
    let (commands, mut sent) = tokio::sync::mpsc::unbounded_channel();
    let mut app = DesktopApp::with_storage(WorkerHandle { commands, events: receiver }, false, None);
    let context = egui::Context::default();
    app.persona.name = "Unsaved draft".to_owned();
    app.persona_dirty = true;
    app.character_files.author = "Unsaved author".to_owned();
    app.prepare_scene(&context, ready());
    let _output = context.run_ui(egui::RawInput::default(), |ui|
    {
        app.show_scene_panel(ui);
        app.show_persona_confirmation(ui.ctx());
    });
    assert_eq!(app.persona.name, "Unsaved draft");
    assert!(sent.try_recv().is_err());
    assert_eq!(app.appearance.kind, AppearanceKind::Companion);
    app.state.connection = ConnectionState::Connected;
    app.apply_pending_persona(app.pending_persona.clone().unwrap());
    let WorkerCommand::SetPersona(profile) = sent.try_recv().unwrap() else { panic!("expected persona command"); };
    events.send(WorkerEvent::Persona(profile.clone())).unwrap();
    app.drain_events();
    assert!(app.persona_apply_pending);
    assert_eq!(app.active_persona.profile_id, "default");
    assert_eq!(app.appearance.kind, AppearanceKind::Companion);
    events.send(WorkerEvent::PersonaApplied(profile.clone())).unwrap();
    app.drain_events();
    assert_eq!(app.active_persona, profile);
    assert_eq!(app.appearance.scene_snapshot().unwrap().0, ready().manifest.appearance);
    assert_eq!(app.active_character.author, "Scene author");
    assert!(!app.scene_busy());
    assert!(!app.persona_dirty);
}

#[test]
fn scene_cancel_rejection_and_disconnection_preserve_the_original_combo()
{
    let (events, receiver) = std::sync::mpsc::channel();
    let (commands, mut sent) = tokio::sync::mpsc::unbounded_channel();
    let mut app = DesktopApp::with_storage(WorkerHandle { commands, events: receiver }, false, None);
    let context = egui::Context::default();
    app.persona.name = "Unsaved".to_owned();
    app.persona_dirty = true;
    let original = app.appearance.scene_snapshot().unwrap().0;
    app.prepare_scene(&context, ready());
    app.cancel_pending_persona();
    assert!(!app.scene_busy());
    assert!(sent.try_recv().is_err());
    assert_eq!(app.persona.name, "Unsaved");
    app.prepare_scene(&context, ready());
    app.apply_pending_persona(app.pending_persona.clone().unwrap());
    assert!(!app.persona_apply_pending);
    assert!(app.confirm_persona);
    assert!(sent.try_recv().is_err());
    app.state.connection = ConnectionState::Connected;
    app.apply_pending_persona(app.pending_persona.clone().unwrap());
    assert!(matches!(sent.try_recv(), Ok(WorkerCommand::SetPersona(_))));
    events.send(WorkerEvent::PersonaApplyFailed("active turn".to_owned())).unwrap();
    app.drain_events();
    assert!(!app.scene_busy());
    assert_eq!(app.active_persona.profile_id, "default");
    assert_eq!(app.persona.name, "Unsaved");
    assert_eq!(app.appearance.scene_snapshot().unwrap().0, original);
    app.prepare_scene(&context, ready());
    drop(sent);
    app.apply_pending_persona(app.pending_persona.clone().unwrap());
    assert!(!app.persona_apply_pending);
    assert!(app.pending_scene.is_some());
    app.cancel_pending_persona();
    assert_eq!(app.appearance.scene_snapshot().unwrap().0, original);
}

#[test]
fn background_scene_import_reaches_confirmation_without_changing_the_editor()
{
    let (_events, receiver) = std::sync::mpsc::channel();
    let (commands, mut sent) = tokio::sync::mpsc::unbounded_channel();
    let mut app = DesktopApp::with_storage(WorkerHandle { commands, events: receiver }, false, None);
    let context = egui::Context::default();
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/scenes/quiet");
    app.persona.name = "Draft".to_owned();
    app.persona_dirty = true;
    app.scene_files.begin(&context, crate::scene_files::SceneAction::Import(path));
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(3);
    while app.scene_files.is_loading()
    {
        let _output = context.run_ui(egui::RawInput::default(), |ui|
        {
            app.poll_scene(ui.ctx());
            app.show_scene_panel(ui);
            app.show_persona_confirmation(ui.ctx());
        });
        assert!(std::time::Instant::now() < deadline);
        std::thread::sleep(std::time::Duration::from_millis(5));
    }
    assert!(app.confirm_persona);
    assert_eq!(app.pending_persona.as_ref().unwrap().profile_id, "aiex.companion");
    assert_eq!(app.active_persona.profile_id, "default");
    assert_eq!(app.persona.name, "Draft");
    assert_eq!(app.appearance.kind, AppearanceKind::Companion);
    assert!(sent.try_recv().is_err());
}
