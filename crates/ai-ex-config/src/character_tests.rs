use super::*;

#[test]
fn character_round_trip_keeps_identity_and_multiline_personality() {
    let persona = PersonaSnapshot {
        profile_id: "小艾.friend".to_owned(),
        revision: 7,
        name: "小艾".to_owned(),
        system_prompt: "喜欢星空\n记住用户明确确认的偏好，别编造经历。\n\\ \"quoted\"".to_owned(),
        ..Default::default()
    };
    let mut manifest = CharacterManifest::from_persona(persona);
    manifest.author = "AIex example".to_owned();
    manifest.license = "CC0".to_owned();
    assert_eq!(
        CharacterManifest::parse(&manifest.to_toml().unwrap()).unwrap(),
        manifest
    );
    let companion =
        CharacterManifest::parse(include_str!("../../../config/characters/companion.toml"))
            .unwrap();
    let host =
        CharacterManifest::parse(include_str!("../../../config/characters/host.toml")).unwrap();
    assert_ne!(companion.persona.profile_id, host.persona.profile_id);
}

#[test]
fn character_rejects_unknown_fields_versions_and_oversized_prompts() {
    let mut manifest = CharacterManifest::from_persona(PersonaSnapshot::default());
    let text = manifest.to_toml().unwrap();
    assert!(CharacterManifest::parse(&format!("api_key = 'not-allowed'\n{text}")).is_err());
    assert!(CharacterManifest::parse(&format!("{text}\nplugin = 'run-me'\n")).is_err());
    assert!(CharacterManifest::parse(&" ".repeat(MAX_MANIFEST_BYTES + 1)).is_err());
    manifest.schema_version = 2;
    assert!(manifest.to_toml().is_err());
    manifest.schema_version = 1;
    manifest.persona.system_prompt = "a".repeat(16_384);
    assert!(manifest.validate().is_err());
    manifest.persona.system_prompt.clear();
    manifest.persona.taboos = vec!["rule".to_owned(); 65];
    assert!(manifest.validate().is_err());
}

#[test]
fn character_files_reject_overwrite_and_bad_input_without_changing_original() {
    let nonce = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let directory =
        std::env::temp_dir().join(format!("aiex-character-{}-{nonce}", std::process::id()));
    std::fs::create_dir(&directory).unwrap();
    let manifest = CharacterManifest::from_persona(PersonaSnapshot::default());
    let path = manifest.save_new(&directory).unwrap();
    let original = std::fs::read(&path).unwrap();
    assert_eq!(CharacterManifest::load(&directory).unwrap(), manifest);
    assert!(manifest.save_new(&path).is_err());
    assert_eq!(std::fs::read(&path).unwrap(), original);
    assert!(CharacterManifest::load(&directory.join("missing.toml")).is_err());
    let bad = directory.join("bad.toml");
    std::fs::write(&bad, [0xff, 0xfe]).unwrap();
    assert!(CharacterManifest::load(&bad).is_err());
    for file in [path, bad] {
        std::fs::remove_file(file).unwrap();
    }
    std::fs::remove_dir(directory).unwrap();
}
