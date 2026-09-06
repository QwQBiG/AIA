use super::*;
use ai_ex_domain::PersonaSnapshot;

fn finish(files: &mut CharacterFiles, context: &egui::Context) -> Option<CharacterManifest>
{
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(3);
    while files.is_loading()
    {
        let result = files.poll(context);
        if result.is_some() || !files.is_loading()
        {
            return result;
        }
        assert!(std::time::Instant::now() < deadline);
        std::thread::sleep(std::time::Duration::from_millis(5));
    }
    None
}

#[test]
fn background_character_files_preserve_metadata_on_failure_and_refuse_overwrite()
{
    let directory = std::env::temp_dir().join(format!("aiex-character-files-{}", uuid::Uuid::new_v4()));
    std::fs::create_dir(&directory).unwrap();
    let context = egui::Context::default();
    let mut files = CharacterFiles::default();
    let mut manifest = CharacterManifest::from_persona(PersonaSnapshot::default());
    manifest.author = "author".to_owned();
    let path = directory.join("character.toml");
    files.begin(&context, FileAction::Export(path.clone(), Box::new(manifest.clone())));
    assert!(finish(&mut files, &context).is_none());
    assert_eq!(CharacterManifest::load(&path).unwrap(), manifest);
    files.begin(&context, FileAction::Import(path.clone()));
    assert_eq!(finish(&mut files, &context).unwrap(), manifest);
    let source = files.draft_source.clone();
    assert!(source.contains("character.toml"));
    assert_eq!(files.baseline.as_ref().unwrap(), &manifest);
    files.begin(&context, FileAction::Import(directory.join("missing.toml")));
    assert!(finish(&mut files, &context).is_none());
    assert_eq!(files.author, "author");
    assert_eq!(files.draft_source, source);
    assert_eq!(files.baseline.as_ref().unwrap(), &manifest);
    assert!(files.feedback.as_deref().unwrap().contains("失败"));
    manifest.persona.name = "must not overwrite".to_owned();
    files.begin(&context, FileAction::Export(path.clone(), Box::new(manifest)));
    assert!(finish(&mut files, &context).is_none());
    assert_eq!(CharacterManifest::load(&path).unwrap().persona.name, "AIex");
    std::fs::remove_file(path).unwrap();
    std::fs::remove_dir(directory).unwrap();
}
