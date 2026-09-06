use super::*;

#[derive(Default)]
struct Storage(std::collections::HashMap<String, String>);

impl eframe::Storage for Storage
{
    fn get_string(&self, key: &str) -> Option<String> { self.0.get(key).cloned() }
    fn set_string(&mut self, key: &str, value: String) { self.0.insert(key.to_owned(), value); }
    fn remove_string(&mut self, key: &str) { self.0.remove(key); }
    fn flush(&mut self) {}
}

fn snapshot() -> ResumeSnapshot
{
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/scenes/quiet");
    ResumeSnapshot { scene: ai_ex_config::scene::SceneBundle::load(&path).unwrap().manifest, source: None }
}

#[test]
fn startup_snapshot_is_scoped_validated_and_preserved_until_explicitly_replaced()
{
    let mut storage = Storage::default();
    let mut resume = SceneResume::load(Some(&storage), ResumeLaunch { scope: "one".to_owned(), automatic: true });
    resume.snapshot = Some(snapshot());
    resume.dirty = true;
    resume.save(&mut storage).unwrap();
    let restored = SceneResume::load(Some(&storage), ResumeLaunch { scope: "one".to_owned(), automatic: true });
    assert!(restored.phase == ResumePhase::Queued);
    assert_eq!(restored.snapshot.unwrap().scene, snapshot().scene);
    assert!(SceneResume::load(Some(&storage), ResumeLaunch { scope: "two".to_owned(), automatic: true }).snapshot.is_none());
    storage.0.insert("one.manifest".to_owned(), "broken TOML".to_owned());
    let mut failed = SceneResume::load(Some(&storage), ResumeLaunch { scope: "one".to_owned(), automatic: true });
    assert!(failed.snapshot.is_none());
    assert!(failed.feedback.is_some());
    failed.save(&mut storage).unwrap();
    assert_eq!(storage.0["one.manifest"], "broken TOML");
    failed.dirty = true;
    failed.save(&mut storage).unwrap();
    assert!(storage.0.is_empty());
}

#[test]
fn startup_scope_uses_the_resolved_configuration_and_service_address()
{
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/characters");
    let first = ResumeLaunch::new(&root.join("companion.toml"), "127.0.0.1:8000", true).unwrap();
    let alias = ResumeLaunch::new(&root.join("./companion.toml"), "127.0.0.1:8000", false).unwrap();
    assert_eq!(first.scope, alias.scope);
    assert!(first.automatic && !alias.automatic);
    assert_ne!(first.scope, ResumeLaunch::new(&root.join("host.toml"), "127.0.0.1:8000", true).unwrap().scope);
    assert_ne!(first.scope, ResumeLaunch::new(&root.join("companion.toml"), "127.0.0.1:9000", true).unwrap().scope);
    let mut image = snapshot();
    image.scene.appearance.body = SceneBody::Images;
    image.scene.appearance.package = Some("appearance/appearance.toml".to_owned());
    assert!(image.validate().is_err());
    image.source = Some(PathBuf::from("relative/appearance.toml"));
    assert!(image.validate().is_err());
}
