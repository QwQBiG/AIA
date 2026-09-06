use super::*;

fn manifest(images: &str) -> String
{
    format!("schema_version = 1\nid = 'test.friend'\nname = '小伙伴'\n[images]\n{images}\n")
}

#[test]
fn validates_version_paths_and_required_default()
{
    assert!(AppearanceManifest::parse(&manifest("default = 'face.png'")).is_ok());
    assert!(AppearanceManifest::parse(&manifest("happy = 'face.png'")).is_err());
    assert!(AppearanceManifest::parse(&manifest("default = 'face.png'\nunknown = 'x.png'")).is_err());
    assert!(AppearanceManifest::parse(&manifest("default = 'face.png'").replace("version = 1", "version = 2")).is_err());
    for path in ["../face.png", "/face.png", "C:/face.png", "a/../../face.png", "face.png:secret", "https://site/face.png", "a\\face.png"]
    {
        assert!(AppearanceManifest::parse(&manifest(&format!("default = '{path}'"))).is_err(), "{path}");
    }
}

#[test]
fn selects_measured_mouth_and_emotion_with_optional_frame_fallbacks()
{
    let pack = AppearanceManifest::parse(&manifest("default = 'face.png'\nspeaking = 'talk.png'\nhappy = 'happy.png'\nhappy_speaking = 'happy-talk.png'\nlistening = 'listen.png'\nblink = 'blink.png'")).unwrap();
    assert_eq!(pack.frame_key(ConversationState::Speaking, Emotion::Happy, true, false), "happy_speaking");
    assert_eq!(pack.frame_key(ConversationState::Speaking, Emotion::Happy, false, false), "happy");
    assert_eq!(pack.frame_key(ConversationState::Speaking, Emotion::Sad, true, false), "speaking");
    assert_eq!(pack.frame_key(ConversationState::Idle, Emotion::Neutral, false, true), "blink");
    assert_eq!(pack.frame_key(ConversationState::Listening, Emotion::Happy, false, false), "listening");
    for state in [ConversationState::Interrupted, ConversationState::Stopped, ConversationState::Failed]
    {
        assert_eq!(pack.frame_key(state, Emotion::Happy, true, true), "default");
    }
    let minimal = AppearanceManifest::parse(&manifest("default = 'face.png'")).unwrap();
    assert_eq!(minimal.frame_key(ConversationState::Speaking, Emotion::Happy, true, false), "default");
}

#[test]
fn loads_directory_and_rejects_missing_or_oversized_assets()
{
    use std::fs;
    let nonce = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos();
    let root = std::env::temp_dir().join(format!("aiex-pack-{}-{nonce}", std::process::id()));
    fs::create_dir(&root).unwrap();
    fs::write(root.join("appearance.toml"), manifest("default = 'face.png'")).unwrap();
    assert!(LoadedAppearance::load(&root).is_err());
    fs::write(root.join("face.png"), b"fixture; decoder validation belongs to the renderer").unwrap();
    let loaded = LoadedAppearance::load(&root).unwrap();
    assert_eq!(loaded.manifest.name, "小伙伴");
    assert!(loaded.source.is_absolute());
    fs::File::create(root.join("face.png")).unwrap().set_len(4 * 1024 * 1024 + 1).unwrap();
    assert!(LoadedAppearance::load(&root).err().expect("oversized asset").to_string().contains("exceeds"));
    fs::remove_file(root.join("face.png")).unwrap();
    fs::remove_file(root.join("appearance.toml")).unwrap();
    fs::remove_dir(root).unwrap();
}
