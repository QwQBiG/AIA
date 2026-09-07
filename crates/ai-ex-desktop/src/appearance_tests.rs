use super::*;
use ai_ex_domain::{ConversationState, Emotion};

#[derive(Default)]
struct Storage(std::collections::HashMap<String, String>);

impl eframe::Storage for Storage {
    fn get_string(&self, key: &str) -> Option<String> {
        self.0.get(key).cloned()
    }

    fn set_string(&mut self, key: &str, value: String) {
        self.0.insert(key.to_owned(), value);
    }

    fn flush(&mut self) {}

    fn remove_string(&mut self, key: &str) {
        self.0.remove(key);
    }
}

#[test]
fn appearance_preferences_round_trip_and_invalid_color_falls_back() {
    let mut storage = Storage::default();
    let panel = AppearancePanel {
        kind: AppearanceKind::Orb,
        accent: [12, 34, 56],
        reduced_motion: true,
        ..Default::default()
    };
    panel.save(&mut storage);
    let restored = AppearancePanel::load(Some(&storage));
    assert_eq!(restored.kind, AppearanceKind::Orb);
    assert_eq!(restored.accent, [12, 34, 56]);
    assert!(restored.reduced_motion);
    storage
        .0
        .insert("appearance.kind".to_owned(), "images".to_owned());
    storage.0.insert(
        "appearance.image_source".to_owned(),
        "my-character/appearance.toml".to_owned(),
    );
    storage
        .0
        .insert("appearance.image_scale".to_owned(), "0.8".to_owned());
    let restored = AppearancePanel::load(Some(&storage));
    assert_eq!(restored.kind, AppearanceKind::Images);
    assert_eq!(restored.images.input, "my-character/appearance.toml");
    assert_eq!(restored.image_scale, 0.8);
    storage
        .0
        .insert("appearance.accent".to_owned(), "999,2".to_owned());
    assert_eq!(
        AppearancePanel::load(Some(&storage)).accent,
        AppearancePanel::default().accent
    );
}

#[test]
fn both_renderers_tessellate_all_expressions_at_compact_and_large_sizes() {
    for kind in [AppearanceKind::Companion, AppearanceKind::Orb] {
        for emotion in [
            Emotion::Neutral,
            Emotion::Happy,
            Emotion::Sad,
            Emotion::Angry,
            Emotion::Surprised,
        ] {
            for width in [320.0, 760.0] {
                let context = egui::Context::default();
                let mut panel = AppearancePanel {
                    kind,
                    ..Default::default()
                };
                let state = PresentationState {
                    connected: true,
                    synchronized: true,
                    activity: ConversationState::Speaking,
                    emotion,
                    mouth_level: None,
                };
                let output = context.run_ui(
                    egui::RawInput {
                        screen_rect: Some(egui::Rect::from_min_size(
                            egui::Pos2::ZERO,
                            egui::vec2(width, 480.0),
                        )),
                        time: Some(1.0),
                        ..Default::default()
                    },
                    |ui| panel.show(ui, state, "AIex", 180.0),
                );
                let primitives = context.tessellate(output.shapes, output.pixels_per_point);
                assert!(!primitives.is_empty());
                for primitive in primitives {
                    if let egui::epaint::Primitive::Mesh(mesh) = primitive.primitive {
                        assert!(mesh.is_valid());
                        assert!(
                            mesh.vertices
                                .iter()
                                .all(|vertex| vertex.pos.x.is_finite() && vertex.pos.y.is_finite())
                        );
                    }
                }
            }
        }
    }
}

#[test]
fn image_pack_preference_restores_loaded_body_after_restart() {
    let root = std::env::temp_dir().join(format!("aiex-body-restore-{}", uuid::Uuid::new_v4()));
    std::fs::create_dir(&root).unwrap();
    image::RgbaImage::new(2, 2)
        .save(root.join("face.png"))
        .unwrap();
    std::fs::write(root.join("appearance.toml"), "schema_version = 1\nid = 'restore.test'\nname = 'Restored friend'\n[images]\ndefault = 'face.png'\n").unwrap();
    let context = egui::Context::default();
    let mut panel = AppearancePanel::default();
    panel.use_images(
        &context,
        crate::image_appearance::DecodedAppearance::load(&root).unwrap(),
    );
    let mut storage = Storage::default();
    panel.save(&mut storage);
    let mut restored = AppearancePanel::load(Some(&storage));
    assert_eq!(restored.kind, AppearanceKind::Images);
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
    while restored.images.current.is_none() {
        assert!(
            !restored.images.poll(&context),
            "restoring should retain the saved body selection"
        );
        assert!(restored.images.error.is_none());
        assert!(std::time::Instant::now() < deadline);
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
    assert_eq!(
        restored.images.current.as_ref().unwrap().manifest.id,
        "restore.test"
    );
    std::fs::remove_file(root.join("face.png")).unwrap();
    std::fs::remove_file(root.join("appearance.toml")).unwrap();
    std::fs::remove_dir(root).unwrap();
}
