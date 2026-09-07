use super::*;
use ai_ex_config::character::CharacterManifest;
use ai_ex_config::scene::{SceneAppearance, SceneBody};

#[test]
fn scene_export_copies_validated_image_bytes_and_rejects_corrupt_images() {
    let root = std::env::temp_dir().join(format!("aiex-scene-files-{}", uuid::Uuid::new_v4()));
    std::fs::create_dir(&root).unwrap();
    let source = root.join("appearance.toml");
    std::fs::write(&source, "schema_version=1\nid='art'\nname='Art'\nauthor='Artist'\nlicense='MIT'\n[images]\ndefault='default.png'\n").unwrap();
    image::RgbaImage::from_pixel(8, 8, image::Rgba([80, 120, 180, 255]))
        .save(root.join("default.png"))
        .unwrap();
    let manifest = SceneManifest {
        schema_version: 1,
        id: "images".to_owned(),
        name: "图片角色".to_owned(),
        character: CharacterManifest::from_persona(Default::default()),
        appearance: SceneAppearance {
            body: SceneBody::Images,
            accent: [30, 60, 90],
            reduced_motion: true,
            scale: 0.7,
            package: Some("appearance/appearance.toml".to_owned()),
        },
    };
    let target = root.join("exported");
    assert!(matches!(
        execute(SceneAction::Export(
            target.clone(),
            Box::new(manifest.clone()),
            Some(source.clone())
        ))
        .unwrap(),
        SceneResult::Saved(_)
    ));
    std::fs::remove_file(root.join("default.png")).unwrap();
    std::fs::remove_file(&source).unwrap();
    let SceneResult::Loaded(ready) = execute(SceneAction::Import(target.clone())).unwrap() else {
        panic!("expected scene");
    };
    let decoded = ready.appearance.unwrap();
    assert_eq!(decoded.images["default"].size, [8, 8]);
    assert_eq!(decoded.manifest.author, "Artist");
    assert_eq!(decoded.manifest.license, "MIT");
    assert_eq!(ready.manifest, manifest);
    std::fs::write(target.join("appearance/default.png"), b"broken PNG").unwrap();
    assert!(execute(SceneAction::Import(target.clone())).is_err());
    let broken = root.join("broken-export");
    assert!(
        execute(SceneAction::Export(
            broken.clone(),
            Box::new(manifest),
            Some(target.join("appearance/appearance.toml"))
        ))
        .is_err()
    );
    assert!(!broken.exists());
    let context = egui::Context::default();
    let mut files = SceneFiles::default();
    files.begin(&context, SceneAction::Import(target.clone()));
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(3);
    while files.is_loading() {
        assert!(files.poll(&context).is_none());
        assert!(std::time::Instant::now() < deadline);
        std::thread::sleep(std::time::Duration::from_millis(5));
    }
    assert!(files.feedback.unwrap().contains("失败"));
    for file in [
        "appearance/default.png",
        "appearance/appearance.toml",
        "scene.toml",
    ] {
        std::fs::remove_file(target.join(file)).unwrap();
    }
    std::fs::remove_dir(target.join("appearance")).unwrap();
    std::fs::remove_dir(target).unwrap();
    std::fs::remove_dir(root).unwrap();
}
