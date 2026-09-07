use super::{SceneBody, SceneManifest, failure};
use crate::appearance::LoadedAppearance;
use ai_ex_domain::AppError;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

pub struct SceneBundle {
    pub source: PathBuf,
    pub manifest: SceneManifest,
    pub appearance: Option<LoadedAppearance>,
}

impl SceneBundle {
    pub fn load(path: &Path) -> Result<Self, AppError> {
        let path = if path.is_dir() {
            path.join("scene.toml")
        } else {
            path.to_owned()
        };
        let source = path.canonicalize().map_err(failure)?;
        let file = File::open(&source).map_err(failure)?;
        if !file.metadata().map_err(failure)?.is_file() {
            return Err(failure("scene manifest must be a regular file"));
        }
        let mut text = String::new();
        file.take(131_073)
            .read_to_string(&mut text)
            .map_err(failure)?;
        let manifest = SceneManifest::parse(&text)?;
        let root = source
            .parent()
            .ok_or_else(|| failure("scene needs a directory"))?;
        let appearance = match &manifest.appearance.package {
            Some(relative) => {
                let path = root.join(relative).canonicalize().map_err(failure)?;
                if !path.starts_with(root) {
                    return Err(failure(
                        "appearance package resolves outside the scene directory",
                    ));
                }
                Some(LoadedAppearance::load(&path)?)
            }
            None => None,
        };
        Ok(Self {
            source,
            manifest,
            appearance,
        })
    }

    pub fn save_new(
        path: &Path,
        manifest: &SceneManifest,
        appearance: Option<&LoadedAppearance>,
    ) -> Result<PathBuf, AppError> {
        manifest.validate()?;
        if (manifest.appearance.body == SceneBody::Images) != appearance.is_some() {
            return Err(failure("scene image resources do not match its body"));
        }
        let mut manifest = manifest.clone();
        let mut resources = Vec::new();
        if let Some(loaded) = appearance {
            loaded.manifest.validate()?;
            let mut image_manifest = loaded.manifest.clone();
            let mut total = 0;
            for (key, relative) in &mut image_manifest.images {
                let bytes = loaded
                    .images
                    .get(key)
                    .ok_or_else(|| failure("missing image bytes"))?;
                total += bytes.len();
                if bytes.len() > 4 * 1024 * 1024 || total > 32 * 1024 * 1024 {
                    return Err(failure("scene image resources exceed supported bounds"));
                }
                let extension = relative
                    .rsplit('.')
                    .next()
                    .ok_or_else(|| failure("image needs an extension"))?;
                *relative = format!("{key}.{extension}");
                resources.push((format!("appearance/{relative}"), bytes.as_slice()));
            }
            manifest.appearance.package = Some("appearance/appearance.toml".to_owned());
            let image_text = toml::to_string_pretty(&image_manifest).map_err(failure)?;
            let scene_text = manifest.to_toml()?;
            let mut writer = BundleWriter::new(path)?;
            writer.directory("appearance")?;
            for (relative, bytes) in resources {
                writer.write(&relative, bytes)?;
            }
            writer.write("appearance/appearance.toml", image_text.as_bytes())?;
            writer.write("scene.toml", scene_text.as_bytes())?;
            writer.committed = true;
        } else {
            let text = manifest.to_toml()?;
            let mut writer = BundleWriter::new(path)?;
            writer.write("scene.toml", text.as_bytes())?;
            writer.committed = true;
        }
        Ok(path.join("scene.toml"))
    }
}

struct BundleWriter {
    root: PathBuf,
    files: Vec<PathBuf>,
    directories: Vec<PathBuf>,
    committed: bool,
}

impl BundleWriter {
    fn new(path: &Path) -> Result<Self, AppError> {
        let root = std::path::absolute(path).map_err(failure)?;
        fs::create_dir(&root).map_err(failure)?;
        Ok(Self {
            directories: vec![root.clone()],
            root,
            files: Vec::new(),
            committed: false,
        })
    }

    fn directory(&mut self, relative: &str) -> Result<(), AppError> {
        let path = self.root.join(relative);
        fs::create_dir(&path).map_err(failure)?;
        self.directories.push(path);
        Ok(())
    }

    fn write(&mut self, relative: &str, bytes: &[u8]) -> Result<(), AppError> {
        let path = self.root.join(relative);
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&path)
            .map_err(failure)?;
        self.files.push(path);
        file.write_all(bytes)
            .and_then(|()| file.sync_all())
            .map_err(failure)
    }
}

impl Drop for BundleWriter {
    fn drop(&mut self) {
        if !self.committed {
            for path in self.files.iter().rev() {
                let _ignored = fs::remove_file(path);
            }
            for path in self.directories.iter().rev() {
                let _ignored = fs::remove_dir(path);
            }
        }
    }
}
