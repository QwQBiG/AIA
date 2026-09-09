use super::*;
use crate::appearance::{AppearanceManifest, LoadedAppearance};
use std::collections::BTreeMap;

fn example() -> SceneManifest {
    SceneManifest {
        schema_version: 1,
        id: "quiet.scene".to_owned(),
        name: "安静陪伴".to_owned(),
        character: CharacterManifest::from_persona(Default::default()),
        appearance: SceneAppearance {
            body: SceneBody::Companion,
            accent: [30, 90, 180],
            reduced_motion: true,
            scale: 0.8,
            package: None,
            builtin_id: None,
            framing: BuiltinFraming::Portrait,
        },
    }
}

#[test]
fn shipped_scenes_reuse_the_documented_character_identities() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config");
    for (scene, character, body) in [
        ("quiet", "companion", SceneBody::Companion),
        ("host", "host", SceneBody::Companion),
    ] {
        let bundle = SceneBundle::load(&root.join("scenes").join(scene)).unwrap();
        let character =
            CharacterManifest::load(&root.join("characters").join(format!("{character}.toml")))
                .unwrap();
        assert_eq!(bundle.manifest.character, character);
        assert_eq!(bundle.manifest.appearance.body, body);
        assert!(bundle.appearance.is_none());
    }
}

#[test]
fn scene_round_trip_and_strict_nested_validation() {
    let mut scene = example();
    let text = scene.to_toml().unwrap();
    assert_eq!(SceneManifest::parse(&text).unwrap(), scene);
    let unknown = text.replace(
        "[character.persona]",
        "[character.persona]\nscript = 'run-me'",
    );
    assert!(SceneManifest::parse(&unknown).is_err());
    scene.appearance.scale = f32::NAN;
    assert!(scene.validate().is_err());
    scene.appearance.scale = 0.8;
    scene.appearance.body = SceneBody::Images;
    for path in [
        "../outside.toml",
        "D:/private.toml",
        "https://host/file.toml",
        "images\\appearance.toml",
        "/appearance.toml",
    ] {
        scene.appearance.package = Some(path.to_owned());
        assert!(scene.validate().is_err());
    }
    scene.appearance.package = Some("appearance/appearance.toml".to_owned());
    assert!(scene.validate().is_ok());
    scene.schema_version = 3;
    assert!(scene.validate().is_err());
}

#[test]
fn legacy_body_imports_as_a_character_and_exports_canonical_body() {
    let original = example();
    let legacy = original
        .to_toml()
        .unwrap()
        .replace("body = \"companion\"", "body = \"orb\"");
    let restored = SceneManifest::parse(&legacy).unwrap();
    assert_eq!(restored, original);
    let exported = restored.to_toml().unwrap();
    assert!(exported.contains("body = \"companion\""));
    assert!(!exported.contains("body = \"orb\""));
    assert_eq!(SceneManifest::parse(&exported).unwrap(), original);
}

#[test]
fn scene_versions_preserve_builtin_selection_and_omit_legacy_defaults() {
    let legacy = example();
    let text = legacy.to_toml().unwrap();
    assert!(!text.contains("builtin_id"));
    assert!(!text.contains("framing"));
    assert_eq!(legacy.appearance.schema_version(), 1);
    let explicit = text.replace("[appearance]", "[appearance]\nframing = 'portrait'");
    assert_eq!(SceneManifest::parse(&explicit).unwrap(), legacy);
    for (id, framing) in [
        (Some("oc-01"), BuiltinFraming::Portrait),
        (Some("oc-01"), BuiltinFraming::FullBody),
        (None, BuiltinFraming::FullBody),
    ] {
        let mut scene = example();
        scene.appearance.builtin_id = id.map(str::to_owned);
        scene.appearance.framing = framing;
        assert_eq!(scene.appearance.schema_version(), 2);
        assert!(scene.to_toml().is_err());
        let invalid_v1 = toml::to_string(&scene).unwrap();
        assert!(SceneManifest::parse(&invalid_v1).is_err());
        scene.schema_version = scene.appearance.schema_version();
        let text = scene.to_toml().unwrap();
        assert_eq!(SceneManifest::parse(&text).unwrap(), scene);
        assert_eq!(text.contains("builtin_id"), id.is_some());
        assert_eq!(
            text.contains("framing"),
            framing == BuiltinFraming::FullBody
        );
        if framing == BuiltinFraming::FullBody {
            assert!(text.contains("framing = \"full_body\""));
        }
    }
    let mut compatible_v2 = legacy;
    compatible_v2.schema_version = 2;
    assert!(compatible_v2.validate().is_ok());
}

#[test]
fn builtin_scene_fields_reject_other_bodies_and_unsafe_identifiers() {
    for body in [SceneBody::Images, SceneBody::Hidden] {
        let mut scene = example();
        scene.schema_version = 2;
        scene.appearance.body = body;
        scene.appearance.package =
            (body == SceneBody::Images).then(|| "appearance/appearance.toml".to_owned());
        assert!(scene.validate().is_ok());
        scene.appearance.builtin_id = Some("oc-01".to_owned());
        assert!(scene.validate().is_err());
        scene.appearance.builtin_id = None;
        scene.appearance.framing = BuiltinFraming::FullBody;
        assert!(scene.validate().is_err());
    }
    let mut scene = example();
    scene.schema_version = 2;
    for id in [
        "", "../oc-01", "oc/01", "oc\\01", "oc:01", "oc 01", "人物", "oc\0",
    ] {
        scene.appearance.builtin_id = Some(id.to_owned());
        assert!(scene.validate().is_err(), "invalid builtin_id: {id:?}");
    }
    scene.appearance.builtin_id = Some("a".repeat(129));
    assert!(scene.validate().is_err());
    for id in ["a".repeat(128), "future_OC.02".to_owned()] {
        scene.appearance.builtin_id = Some(id);
        assert!(scene.validate().is_ok());
    }
    let text = scene.to_toml().unwrap();
    let invalid = text.replace("[appearance]", "[appearance]\nframing = 'panorama'");
    assert!(SceneManifest::parse(&invalid).is_err());
}

#[test]
fn scene_bundle_contains_its_images_and_relocates_without_original_paths() {
    let nonce = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let root = std::env::temp_dir().join(format!("aiex-scene-{}-{nonce}", std::process::id()));
    std::fs::create_dir(&root).unwrap();
    let first = root.join("first");
    let relocated = root.join("relocated");
    let loaded = LoadedAppearance {
        source: root.join("original/appearance.toml"),
        manifest: AppearanceManifest {
            schema_version: 1,
            id: "art".to_owned(),
            name: "Art".to_owned(),
            author: "Artist".to_owned(),
            license: "MIT".to_owned(),
            images: BTreeMap::from([("default".to_owned(), "nested/original.png".to_owned())]),
        },
        images: BTreeMap::from([("default".to_owned(), b"encoded image bytes".to_vec())]),
    };
    let mut scene = example();
    scene.appearance.body = SceneBody::Images;
    scene.appearance.package = Some("original/appearance.toml".to_owned());
    SceneBundle::save_new(&first, &scene, Some(&loaded)).unwrap();
    let original = std::fs::read(first.join("scene.toml")).unwrap();
    assert!(SceneBundle::save_new(&first, &scene, Some(&loaded)).is_err());
    assert_eq!(std::fs::read(first.join("scene.toml")).unwrap(), original);
    assert!(!String::from_utf8(original).unwrap().contains("original"));
    assert!(first.starts_with(&root) && relocated.starts_with(&root) && !relocated.exists());
    std::fs::rename(&first, &relocated).unwrap();
    let bundle = SceneBundle::load(&relocated).unwrap();
    let appearance = bundle.appearance.unwrap();
    assert_eq!(appearance.images, loaded.images);
    assert_eq!(appearance.manifest.author, "Artist");
    assert_eq!(appearance.manifest.license, "MIT");
    std::fs::remove_file(relocated.join("appearance/default.png")).unwrap();
    assert!(SceneBundle::load(&relocated).is_err());
    std::fs::remove_file(relocated.join("appearance/appearance.toml")).unwrap();
    std::fs::remove_dir(relocated.join("appearance")).unwrap();
    std::fs::remove_file(relocated.join("scene.toml")).unwrap();
    std::fs::remove_dir(&relocated).unwrap();
    let missing = root.join("missing-assets");
    assert!(SceneBundle::save_new(&missing, &scene, None).is_err());
    assert!(!missing.exists());
    let plain = root.join("companion");
    SceneBundle::save_new(&plain, &example(), None).unwrap();
    assert_eq!(SceneBundle::load(&plain).unwrap().manifest, example());
    std::fs::remove_file(plain.join("scene.toml")).unwrap();
    std::fs::remove_dir(plain).unwrap();
    std::fs::remove_dir(root).unwrap();
}
