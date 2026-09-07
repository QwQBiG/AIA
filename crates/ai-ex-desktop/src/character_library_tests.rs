use super::*;

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

#[test]
fn library_preserves_versions_round_trips_snapshots_and_undoes_removal() {
    let mut storage = Storage::default();
    let mut library = CharacterLibrary::load(Some(&storage));
    assert_eq!(library.entries.len(), 2);
    let original = library.entries[0].character.clone();
    library
        .remember(original.clone(), "moved/file.toml".to_owned())
        .unwrap();
    assert_eq!(library.entries.len(), 2);
    let mut edited = original.clone();
    edited.persona.name = "Edited".to_owned();
    assert!(
        library
            .remember(edited.clone(), "draft".to_owned())
            .is_err()
    );
    assert_eq!(library.entries[0].character, original);
    edited.persona.revision += 1;
    library
        .remember(edited.clone(), "missing/file.toml".to_owned())
        .unwrap();
    library.save(&mut storage).unwrap();
    let mut restored = CharacterLibrary::load(Some(&storage));
    assert_eq!(restored.entries[2].character, edited);
    restored.remove(0).unwrap();
    assert_eq!(restored.entries.len(), 2);
    restored.undo_remove().unwrap();
    assert_eq!(restored.entries[0].character, original);
    restored.remove(0).unwrap();
    restored.save(&mut storage).unwrap();
    assert_eq!(CharacterLibrary::load(Some(&storage)).entries.len(), 2);
}

#[test]
fn corrupt_library_is_retained_and_backed_up_before_explicit_edits() {
    let mut storage = Storage::default();
    storage
        .0
        .insert(STORAGE_KEY.to_owned(), "broken JSON".to_owned());
    let mut library = CharacterLibrary::load(Some(&storage));
    assert!(library.feedback.is_some());
    library.save(&mut storage).unwrap();
    assert_eq!(storage.0[STORAGE_KEY], "broken JSON");
    library
        .remember(
            CharacterManifest::from_persona(Default::default()),
            "draft".to_owned(),
        )
        .unwrap();
    library.save(&mut storage).unwrap();
    assert!(storage.0.iter().any(
        |(key, value)| key.starts_with("character.library.recovery.") && value == "broken JSON"
    ));
    assert_eq!(CharacterLibrary::load(Some(&storage)).entries.len(), 1);
}

#[test]
fn library_rejects_capacity_overflow_duplicate_records_and_oversized_sources() {
    let mut library = CharacterLibrary::load(None);
    for revision in 2..=31 {
        let mut character = library.entries[0].character.clone();
        character.persona.revision = revision;
        library.remember(character, "draft".to_owned()).unwrap();
    }
    assert_eq!(library.entries.len(), 32);
    let character = CharacterManifest::from_persona(Default::default());
    assert!(
        library
            .remember(character.clone(), "draft".to_owned())
            .is_err()
    );
    assert_eq!(library.entries.len(), 32);
    library.remove(0).unwrap();
    assert!(
        library
            .remember(character.clone(), "x".repeat(2049))
            .is_err()
    );
    library.remember(character, "draft".to_owned()).unwrap();
    assert!(library.undo_remove().is_err());
    assert!(library.can_undo());
    let mut storage = Storage::default();
    let text = storage::encode(&library.entries).unwrap();
    let mut value: serde_json::Value = serde_json::from_str(&text).unwrap();
    value["entries"][1] = value["entries"][0].clone();
    storage.0.insert(STORAGE_KEY.to_owned(), value.to_string());
    assert!(CharacterLibrary::load(Some(&storage)).feedback.is_some());
    storage
        .0
        .insert(STORAGE_KEY.to_owned(), " ".repeat(MAX_BYTES + 1));
    assert!(CharacterLibrary::load(Some(&storage)).feedback.is_some());
}
