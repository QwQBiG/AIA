use super::*;
use crate::appearance::AppearanceKind;
use crate::scene_resume::{ResumeLaunch, ResumePhase, ResumeSnapshot, SceneResume};
use std::path::Path;

#[derive(Default)]
struct Storage(std::collections::HashMap<String, String>);

impl eframe::Storage for Storage {
    fn get_string(&self, key: &str) -> Option<String> {
        self.0.get(key).cloned()
    }
    fn set_string(&mut self, key: &str, value: String) {
        self.0.insert(key.to_owned(), value);
    }
    fn remove_string(&mut self, key: &str) {
        self.0.remove(key);
    }
    fn flush(&mut self) {}
}

struct Rig {
    app: DesktopApp,
    events: std::sync::mpsc::Sender<WorkerEvent>,
    commands: tokio::sync::mpsc::UnboundedReceiver<WorkerCommand>,
    storage: Storage,
}

impl Rig {
    fn new(automatic: bool) -> Self {
        let mut storage = Storage::default();
        let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/scenes/quiet");
        let scene = ai_ex_config::scene::SceneBundle::load(&path)
            .unwrap()
            .manifest;
        let launch = || ResumeLaunch {
            scope: "test".to_owned(),
            automatic,
        };
        let mut resume = SceneResume::load(Some(&storage), launch());
        resume.snapshot = Some(ResumeSnapshot {
            scene,
            source: None,
        });
        resume.dirty = true;
        resume.save(&mut storage).unwrap();
        let (events, receiver) = std::sync::mpsc::channel();
        let (sender, commands) = tokio::sync::mpsc::unbounded_channel();
        let mut app = DesktopApp::with_storage(
            WorkerHandle {
                commands: sender,
                events: receiver,
            },
            false,
            None,
        );
        app.resume = SceneResume::load(Some(&storage), launch());
        Self {
            app,
            events,
            commands,
            storage,
        }
    }

    fn finish_loading(&mut self, context: &egui::Context) {
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(3);
        loop {
            let _output = context.run_ui(egui::RawInput::default(), |ui| {
                self.app.poll_scene(ui.ctx());
                self.app.show_resume_controls(ui);
                self.app.show_persona_confirmation(ui.ctx());
            });
            if !matches!(
                self.app.resume.phase,
                ResumePhase::Queued | ResumePhase::Loading
            ) {
                break;
            }
            assert!(std::time::Instant::now() < deadline);
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
    }

    fn connect(&mut self) {
        self.events.send(WorkerEvent::Connection(true)).unwrap();
        self.events
            .send(WorkerEvent::Persona(PersonaSnapshot::default()))
            .unwrap();
        self.app.drain_events();
    }
}

#[test]
fn startup_restore_waits_for_connection_profile_sync_and_its_command_ack() {
    let mut rig = Rig::new(true);
    let context = egui::Context::default();
    rig.finish_loading(&context);
    assert!(rig.app.resume.phase == ResumePhase::Prepared);
    assert!(rig.commands.try_recv().is_err());
    rig.events
        .send(WorkerEvent::Persona(PersonaSnapshot::default()))
        .unwrap();
    rig.app.drain_events();
    rig.events.send(WorkerEvent::Connection(true)).unwrap();
    rig.app.drain_events();
    rig.app.poll_scene(&context);
    assert!(
        rig.commands.try_recv().is_err(),
        "an offline profile must not authorize automatic restore"
    );
    rig.app.input = "Hello after restore".to_owned();
    rig.app.submit();
    assert!(
        rig.commands.try_recv().is_err(),
        "new input must wait for the selected identity"
    );
    assert_eq!(rig.app.input, "Hello after restore");
    rig.connect();
    rig.app.poll_scene(&context);
    let WorkerCommand::SetPersona(profile) = rig.commands.try_recv().unwrap() else {
        panic!("expected restore");
    };
    assert_eq!(profile.profile_id, "aiex.companion");
    assert_eq!(rig.app.active_persona.profile_id, "default");
    assert_eq!(rig.app.appearance.kind, AppearanceKind::Companion);
    rig.events
        .send(WorkerEvent::PersonaApplied(profile.clone()))
        .unwrap();
    rig.app.drain_events();
    assert_eq!(rig.app.active_persona, profile);
    assert_eq!(rig.app.appearance.kind, AppearanceKind::Companion);
    assert!(!rig.app.scene_busy());
    assert!(rig.app.resume.phase == ResumePhase::Idle);
    rig.app.submit();
    assert!(
        matches!(rig.commands.try_recv(), Ok(WorkerCommand::Submit(text)) if text == "Hello after restore")
    );
    rig.app.appearance.kind = AppearanceKind::Hidden;
    rig.app.save_resume(&mut rig.storage);
    let restored = SceneResume::load(
        Some(&rig.storage),
        ResumeLaunch {
            scope: "test".to_owned(),
            automatic: true,
        },
    );
    assert_eq!(
        restored.snapshot.unwrap().scene.appearance.body,
        ai_ex_config::scene::SceneBody::Companion
    );
}

#[test]
fn startup_restore_on_existing_service_needs_confirmation_and_never_retries_a_rejection() {
    let mut rig = Rig::new(false);
    let context = egui::Context::default();
    rig.connect();
    rig.finish_loading(&context);
    assert!(rig.app.confirm_persona);
    assert!(rig.commands.try_recv().is_err());
    rig.app.cancel_pending_persona();
    rig.app.poll_scene(&context);
    assert!(rig.commands.try_recv().is_err());
    assert!(rig.app.resume.snapshot.is_some());
    rig.app.resume.phase = ResumePhase::Queued;
    rig.finish_loading(&context);
    rig.app
        .apply_pending_persona(rig.app.pending_persona.clone().unwrap());
    assert!(matches!(
        rig.commands.try_recv(),
        Ok(WorkerCommand::SetPersona(_))
    ));
    rig.events
        .send(WorkerEvent::PersonaApplyFailed("active turn".to_owned()))
        .unwrap();
    rig.app.drain_events();
    for _ in 0..5 {
        rig.app.poll_scene(&context);
    }
    assert_eq!(rig.app.active_persona.profile_id, "default");
    assert_eq!(rig.app.appearance.kind, AppearanceKind::Companion);
    assert!(!rig.app.scene_busy());
    assert!(rig.commands.try_recv().is_err());
    rig.app.save_resume(&mut rig.storage);
    assert!(
        SceneResume::load(
            Some(&rig.storage),
            ResumeLaunch {
                scope: "test".to_owned(),
                automatic: true
            }
        )
        .snapshot
        .is_some()
    );
}

#[test]
fn broken_startup_images_do_not_change_identity_or_erase_the_saved_choice() {
    let mut rig = Rig::new(true);
    let context = egui::Context::default();
    let snapshot = rig.app.resume.snapshot.as_mut().unwrap();
    snapshot.scene.appearance.body = ai_ex_config::scene::SceneBody::Images;
    snapshot.scene.appearance.package = Some("appearance/appearance.toml".to_owned());
    snapshot.source = Some(
        std::env::temp_dir().join(format!("missing-aiex-image-{}.toml", uuid::Uuid::new_v4())),
    );
    rig.app.resume.dirty = true;
    rig.app.save_resume(&mut rig.storage);
    rig.connect();
    rig.finish_loading(&context);
    for _ in 0..5 {
        rig.app.poll_scene(&context);
    }
    assert!(rig.app.resume.phase == ResumePhase::Idle);
    assert!(
        rig.app
            .scene_files
            .feedback
            .as_ref()
            .unwrap()
            .contains("失败")
    );
    assert_eq!(rig.app.active_persona.profile_id, "default");
    assert_eq!(rig.app.appearance.kind, AppearanceKind::Companion);
    assert!(rig.commands.try_recv().is_err());
    assert!(rig.app.resume.snapshot.is_some());
    rig.app.persona.name = "Unapplied draft".to_owned();
    rig.app.persona_dirty = true;
    rig.app.pin_startup_scene();
    assert_eq!(
        rig.app
            .resume
            .snapshot
            .as_ref()
            .unwrap()
            .scene
            .character
            .persona,
        rig.app.active_persona
    );
    assert_ne!(
        rig.app
            .resume
            .snapshot
            .as_ref()
            .unwrap()
            .scene
            .character
            .persona
            .name,
        "Unapplied draft"
    );
    rig.app.save_resume(&mut rig.storage);
    let restored = SceneResume::load(
        Some(&rig.storage),
        ResumeLaunch {
            scope: "test".to_owned(),
            automatic: true,
        },
    );
    assert_eq!(
        restored.snapshot.unwrap().scene.appearance.body,
        ai_ex_config::scene::SceneBody::Companion
    );
}

#[test]
fn pinned_builtin_scenes_restore_their_version_character_and_framing_after_ack() {
    use crate::builtin_character::BuiltinCharacter;
    use ai_ex_config::scene::BuiltinFraming;

    for (builtin, framing, version) in [
        (BuiltinCharacter::Original, BuiltinFraming::Portrait, 1),
        (BuiltinCharacter::Oc01, BuiltinFraming::FullBody, 2),
    ] {
        let mut rig = Rig::new(true);
        rig.app.resume.phase = ResumePhase::Idle;
        rig.connect();
        rig.app.appearance.builtin = builtin;
        rig.app.appearance.framing = framing;
        rig.app.pin_startup_scene();
        let expected = rig.app.resume.snapshot.as_ref().unwrap().scene.clone();
        assert_eq!(expected.schema_version, version);
        assert_eq!(expected.appearance.framing, framing);
        assert_eq!(
            expected.appearance.builtin_id.as_deref(),
            (builtin == BuiltinCharacter::Oc01).then_some("oc-01")
        );
        rig.app.save_resume(&mut rig.storage);
        rig.app.resume = SceneResume::load(
            Some(&rig.storage),
            ResumeLaunch {
                scope: "test".to_owned(),
                automatic: true,
            },
        );
        assert_eq!(rig.app.resume.snapshot.as_ref().unwrap().scene, expected);
        let current = if builtin == BuiltinCharacter::Original {
            BuiltinCharacter::Oc01
        } else {
            BuiltinCharacter::Original
        };
        rig.app.appearance.builtin = current;
        rig.finish_loading(&egui::Context::default());
        let WorkerCommand::SetPersona(profile) = rig.commands.try_recv().unwrap() else {
            panic!("expected startup scene restore");
        };
        assert_eq!(rig.app.appearance.builtin, current);
        rig.events
            .send(WorkerEvent::PersonaApplied(profile))
            .unwrap();
        rig.app.drain_events();
        assert_eq!(rig.app.appearance.builtin, builtin);
        assert_eq!(rig.app.appearance.framing, framing);
        assert_eq!(
            rig.app.appearance.scene_snapshot().unwrap().0,
            expected.appearance
        );
    }
}

#[test]
fn startup_image_scene_round_trips_its_source_and_commits_only_after_confirmation() {
    let root = std::env::temp_dir().join(format!("aiex-startup-images-{}", uuid::Uuid::new_v4()));
    std::fs::create_dir(&root).unwrap();
    let source = root.join("appearance.toml");
    std::fs::write(
        &source,
        "schema_version=1\nid='startup.art'\nname='Art'\n[images]\ndefault='default.png'\n",
    )
    .unwrap();
    image::RgbaImage::from_pixel(8, 8, image::Rgba([90, 170, 240, 255]))
        .save(root.join("default.png"))
        .unwrap();
    let mut rig = Rig::new(true);
    let snapshot = rig.app.resume.snapshot.as_mut().unwrap();
    snapshot.scene.appearance.body = ai_ex_config::scene::SceneBody::Images;
    snapshot.scene.appearance.package = Some("appearance/appearance.toml".to_owned());
    snapshot.scene.appearance.scale = 0.6;
    snapshot.source = Some(source.clone());
    let expected = snapshot.scene.appearance.clone();
    rig.app.resume.dirty = true;
    rig.app.save_resume(&mut rig.storage);
    rig.app.resume = SceneResume::load(
        Some(&rig.storage),
        ResumeLaunch {
            scope: "test".to_owned(),
            automatic: true,
        },
    );
    let context = egui::Context::default();
    rig.connect();
    rig.finish_loading(&context);
    let WorkerCommand::SetPersona(profile) = rig.commands.try_recv().unwrap() else {
        panic!("expected restore");
    };
    assert_eq!(rig.app.appearance.kind, AppearanceKind::Companion);
    rig.events
        .send(WorkerEvent::PersonaApplied(profile))
        .unwrap();
    rig.app.drain_events();
    let (actual, actual_source) = rig.app.appearance.scene_snapshot().unwrap();
    assert_eq!(actual, expected);
    assert_eq!(actual_source.unwrap(), source.canonicalize().unwrap());
    let state = ai_ex_ui_model::PresentationState::from_ui(&rig.app.state);
    let output = context.run_ui(egui::RawInput::default(), |ui| {
        rig.app
            .appearance
            .show(ui, state, &rig.app.active_persona.name, 150.0);
    });
    let primitives = context.tessellate(output.shapes, output.pixels_per_point);
    assert!(!primitives.is_empty());
    assert!(
        primitives
            .iter()
            .all(|primitive| match &primitive.primitive {
                egui::epaint::Primitive::Mesh(mesh) => mesh.is_valid(),
                _ => true,
            })
    );
    std::fs::remove_file(&source).unwrap();
    std::fs::remove_file(root.join("default.png")).unwrap();
    std::fs::remove_dir(root).unwrap();
}
