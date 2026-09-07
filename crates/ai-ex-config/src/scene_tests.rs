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
            body: SceneBody::Orb,
            accent: [30, 90, 180],
            reduced_motion: true,
            scale: 0.8,
            package: None,
        },
    }
}

#[test]
fn shipped_scenes_reuse_the_documented_character_identities() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config");
    for (scene, character, body) in [
        ("quiet", "companion", SceneBody::Orb),
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
    scene.schema_version = 2;
    assert!(scene.validate().is_err());
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
    let plain = root.join("orb");
    SceneBundle::save_new(&plain, &example(), None).unwrap();
    assert_eq!(SceneBundle::load(&plain).unwrap().manifest, example());
    std::fs::remove_file(plain.join("scene.toml")).unwrap();
    std::fs::remove_dir(plain).unwrap();
    std::fs::remove_dir(root).unwrap();
}
