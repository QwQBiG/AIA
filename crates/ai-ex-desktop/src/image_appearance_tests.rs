use super::*;
use ai_ex_domain::{ConversationState, Emotion};

struct Fixture(PathBuf);

impl Fixture
{
    fn new() -> Self
    {
        let root = std::env::temp_dir().join(format!("aiex-image-pack-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();
        for (name, rgba) in [("default.png", [20, 80, 160, 255]), ("speaking.png", [120, 200, 20, 255])]
        {
            image::RgbaImage::from_pixel(8, 8, image::Rgba(rgba)).save(root.join(name)).unwrap();
        }
        std::fs::write(root.join("appearance.toml"), "schema_version = 1\nid = 'image.test'\nname = 'Test friend'\n[images]\ndefault = 'default.png'\nspeaking = 'speaking.png'\n").unwrap();
        Self(root)
    }
}

impl Drop for Fixture
{
    fn drop(&mut self)
    {
        for name in ["appearance.toml", "default.png", "speaking.png", "photo.jpg"]
        {
            let _ignored = std::fs::remove_file(self.0.join(name));
        }
        let _ignored = std::fs::remove_dir(&self.0);
    }
}

#[test]
fn decodes_png_and_jpeg_and_rejects_corrupt_or_oversized_images()
{
    let fixture = Fixture::new();
    let decoded = DecodedAppearance::load(&fixture.0).unwrap();
    assert_eq!(decoded.images["default"].size, [8, 8]);
    image::RgbImage::from_pixel(4, 4, image::Rgb([100, 90, 80])).save(fixture.0.join("photo.jpg")).unwrap();
    let manifest = std::fs::read_to_string(fixture.0.join("appearance.toml")).unwrap();
    std::fs::write(fixture.0.join("appearance.toml"), manifest.replace("default.png", "photo.jpg")).unwrap();
    assert_eq!(DecodedAppearance::load(&fixture.0).unwrap().images["default"].size, [4, 4]);
    std::fs::write(fixture.0.join("appearance.toml"), manifest).unwrap();
    image::RgbaImage::new(2049, 1).save(fixture.0.join("default.png")).unwrap();
    assert!(DecodedAppearance::load(&fixture.0).err().unwrap().to_string().contains("2048"));
    std::fs::write(fixture.0.join("default.png"), b"not an image").unwrap();
    assert!(DecodedAppearance::load(&fixture.0).is_err());
}

#[test]
fn renderer_changes_texture_with_audio_and_stops_on_disconnect_or_interrupt()
{
    let fixture = Fixture::new();
    let context = egui::Context::default();
    let pack = ImageAppearance::upload(&context, DecodedAppearance::load(&fixture.0).unwrap());
    for (connected, activity, level, expected) in [
        (true, ConversationState::Speaking, 800, "speaking"),
        (true, ConversationState::Speaking, 0, "default"),
        (false, ConversationState::Speaking, 800, "default"),
        (true, ConversationState::Interrupted, 800, "default"),
    ]
    {
        let state = PresentationState { connected, synchronized: connected, activity, emotion: Emotion::Neutral, mouth_level: Some(level) };
        let output = context.run_ui(egui::RawInput::default(), |ui|
        {
            pack.draw(ui.painter(), Rect::from_min_size(egui::pos2(0.0, 0.0), egui::vec2(200.0, 180.0)), state, state.animate(1.0, false), 0.95);
        });
        let primitives = context.tessellate(output.shapes, output.pixels_per_point);
        assert!(primitives.iter().any(|primitive| matches!(&primitive.primitive,
            egui::epaint::Primitive::Mesh(mesh) if mesh.texture_id == pack.textures[expected].id() && mesh.is_valid())));
    }
}

#[test]
fn failed_background_import_preserves_current_appearance()
{
    let fixture = Fixture::new();
    let context = egui::Context::default();
    let mut importer = crate::appearance_import::AppearanceImport::default();
    importer.install(&context, DecodedAppearance::load(&fixture.0).unwrap());
    let source = importer.current.as_ref().unwrap().source.clone();
    importer.begin(&context, fixture.0.join("missing.toml"));
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
    while importer.error.is_none()
    {
        assert!(!importer.poll(&context));
        assert!(std::time::Instant::now() < deadline, "background import should finish");
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
    assert_eq!(importer.current.as_ref().unwrap().source, source);
    assert_eq!(importer.current.as_ref().unwrap().manifest.id, "image.test");
    importer.begin(&context, fixture.0.clone());
    importer.keep_selection();
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
    while importer.is_loading()
    {
        assert!(!importer.poll(&context), "finishing import must not override a newer body selection");
        assert!(std::time::Instant::now() < deadline);
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
    assert!(importer.error.is_none());
}
