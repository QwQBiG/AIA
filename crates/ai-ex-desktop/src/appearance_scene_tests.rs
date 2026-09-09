use super::*;
use ai_ex_config::character::CharacterManifest;
use ai_ex_config::scene::SceneManifest;

#[test]
fn builtin_scene_round_trip_preserves_character_and_framing() {
    let context = egui::Context::default();
    for (builtin, framing) in [
        (BuiltinCharacter::Original, BuiltinFraming::Portrait),
        (BuiltinCharacter::Oc01, BuiltinFraming::Portrait),
        (BuiltinCharacter::Oc01, BuiltinFraming::FullBody),
    ] {
        let panel = AppearancePanel {
            builtin,
            framing,
            ..Default::default()
        };
        let (appearance, source) = panel.scene_snapshot().unwrap();
        assert!(source.is_none());
        assert_eq!(
            appearance.builtin_id.as_deref(),
            (builtin == BuiltinCharacter::Oc01).then_some("oc-01")
        );
        let manifest = SceneManifest {
            schema_version: appearance.schema_version(),
            id: "builtin.test".to_owned(),
            name: "Test character".to_owned(),
            character: CharacterManifest::from_persona(Default::default()),
            appearance,
        };
        let imported = SceneManifest::parse(&manifest.to_toml().unwrap()).unwrap();
        let restored = AppearancePanel::from_scene(&context, &imported.appearance, None).unwrap();
        assert_eq!(restored.builtin, builtin);
        assert_eq!(restored.framing, framing);
        assert_eq!(restored.scene_snapshot().unwrap().0, manifest.appearance);
    }
}

#[test]
fn original_scene_normalizes_dormant_framing_without_erasing_the_local_choice() {
    let (mut preset, _) = AppearancePanel::default().scene_snapshot().unwrap();
    preset.builtin_id = None;
    preset.framing = BuiltinFraming::FullBody;
    let restored = AppearancePanel::from_scene(&egui::Context::default(), &preset, None).unwrap();
    assert_eq!(restored.builtin, BuiltinCharacter::Original);
    assert_eq!(restored.framing, BuiltinFraming::FullBody);
    let (exported, source) = restored.scene_snapshot().unwrap();
    assert!(source.is_none());
    assert_eq!(exported.builtin_id, None);
    assert_eq!(exported.framing, BuiltinFraming::Portrait);
    assert_eq!(exported.schema_version(), 1);
    assert_eq!(restored.framing, BuiltinFraming::FullBody);
}

#[test]
fn legacy_scene_keeps_original_while_missing_local_preferences_default_to_oc() {
    assert_eq!(AppearancePanel::load(None).builtin, BuiltinCharacter::Oc01);
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/scenes/quiet");
    let scene = ai_ex_config::scene::SceneBundle::load(&path)
        .unwrap()
        .manifest;
    assert_eq!(scene.schema_version, 1);
    let legacy = scene
        .to_toml()
        .unwrap()
        .replace("body = \"companion\"", "body = \"orb\"");
    let scene = SceneManifest::parse(&legacy).unwrap();
    let panel =
        AppearancePanel::from_scene(&egui::Context::default(), &scene.appearance, None).unwrap();
    assert_eq!(panel.builtin, BuiltinCharacter::Original);
    assert_eq!(panel.framing, BuiltinFraming::Portrait);
    assert_eq!(panel.scene_snapshot().unwrap().0, scene.appearance);
}

#[test]
fn image_and_hidden_scenes_omit_dormant_builtin_preferences() {
    use ai_ex_config::appearance::AppearanceManifest;
    use std::collections::BTreeMap;

    let context = egui::Context::default();
    for kind in [AppearanceKind::Images, AppearanceKind::Hidden] {
        let mut panel = AppearancePanel {
            kind,
            builtin: BuiltinCharacter::Oc01,
            framing: BuiltinFraming::FullBody,
            ..Default::default()
        };
        if kind == AppearanceKind::Images {
            panel.use_images(
                &context,
                DecodedAppearance {
                    source: PathBuf::from("art/appearance.toml"),
                    manifest: AppearanceManifest {
                        schema_version: 1,
                        id: "art".to_owned(),
                        name: "Art".to_owned(),
                        author: String::new(),
                        license: String::new(),
                        images: BTreeMap::from([("default".to_owned(), "default.png".to_owned())]),
                    },
                    images: BTreeMap::from([(
                        "default".to_owned(),
                        egui::ColorImage::from_rgba_unmultiplied([1, 1], &[255; 4]),
                    )]),
                },
            );
        }
        let (appearance, source) = panel.scene_snapshot().unwrap();
        assert_eq!(appearance.builtin_id, None);
        assert_eq!(appearance.framing, BuiltinFraming::Portrait);
        assert_eq!(appearance.schema_version(), 1);
        assert_eq!(source.is_some(), kind == AppearanceKind::Images);
        assert_eq!(panel.builtin, BuiltinCharacter::Oc01);
        assert_eq!(panel.framing, BuiltinFraming::FullBody);
    }
}
