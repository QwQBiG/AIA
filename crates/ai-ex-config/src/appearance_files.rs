use std::collections::BTreeMap;
use std::fs::File;
use std::io::Read;
use std::path::{Path, PathBuf};

use ai_ex_domain::AppError;

use super::AppearanceManifest;

pub struct LoadedAppearance
{
    pub source: PathBuf,
    pub manifest: AppearanceManifest,
    pub images: BTreeMap<String, Vec<u8>>,
}

impl LoadedAppearance
{
    pub fn load(path: &Path) -> Result<Self, AppError>
    {
        let path = if path.is_dir() { path.join("appearance.toml") } else { path.to_path_buf() };
        let source = path.canonicalize().map_err(|error| failure(&path, error))?;
        let bytes = read_limited(&source, 65_536)?;
        let text = std::str::from_utf8(&bytes)
            .map_err(|_| AppError::configuration("appearance manifest must be UTF-8"))?;
        let manifest = AppearanceManifest::parse(text)?;
        let root = source.parent().ok_or_else(|| AppError::configuration("appearance manifest needs a directory"))?;
        let mut images = BTreeMap::new();
        let mut total = 0;
        for (key, relative) in &manifest.images
        {
            let candidate = root.join(relative);
            let path = candidate.canonicalize().map_err(|error| failure(&candidate, error))?;
            if !path.starts_with(root)
            {
                return Err(AppError::configuration(format!("image {key} resolves outside its appearance directory")));
            }
            let bytes = read_limited(&path, 4 * 1024 * 1024)?;
            total += bytes.len();
            if total > 32 * 1024 * 1024
            {
                return Err(AppError::configuration("appearance images exceed the 32 MiB package limit"));
            }
            images.insert(key.clone(), bytes);
        }
        Ok(Self { source, manifest, images })
    }
}

fn read_limited(path: &Path, limit: usize) -> Result<Vec<u8>, AppError>
{
    let file = File::open(path).map_err(|error| failure(path, error))?;
    if !file.metadata().map_err(|error| failure(path, error))?.is_file()
    {
        return Err(AppError::configuration(format!("appearance resource is not a file: {}", path.display())));
    }
    let mut bytes = Vec::new();
    file.take(limit as u64 + 1).read_to_end(&mut bytes).map_err(|error| failure(path, error))?;
    if bytes.len() > limit
    {
        return Err(AppError::configuration(format!("appearance resource exceeds {limit} bytes: {}", path.display())));
    }
    Ok(bytes)
}

fn failure(path: &Path, error: std::io::Error) -> AppError
{
    AppError::configuration(format!("cannot read appearance resource {}: {error}", path.display()))
}
