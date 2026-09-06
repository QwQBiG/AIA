use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

use ai_ex_domain::{AppError, PersonaSnapshot};
use serde::{Deserialize, Serialize};

#[cfg(test)]
#[path = "character_tests.rs"]
mod tests;

const MAX_MANIFEST_BYTES: usize = 65_536;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CharacterManifest
{
    pub schema_version: u16,
    #[serde(default)]
    pub author: String,
    #[serde(default)]
    pub license: String,
    pub persona: PersonaSnapshot,
}

impl CharacterManifest
{
    pub fn from_persona(persona: PersonaSnapshot) -> Self
    {
        Self { schema_version: 1, author: String::new(), license: String::new(), persona }
    }

    pub fn validate(&self) -> Result<(), AppError>
    {
        if self.schema_version != 1
        {
            return Err(AppError::configuration("unsupported character schema_version; expected 1"));
        }
        self.persona.validate()?;
        if self.author.chars().count() > 512 || self.license.chars().count() > 1024
            || self.persona.taboos.len() > 64 || self.persona.compiled_system_prompt().chars().count() > 16_384
        {
            return Err(AppError::configuration("character metadata or compiled prompt exceeds supported bounds"));
        }
        Ok(())
    }

    pub fn parse(text: &str) -> Result<Self, AppError>
    {
        if text.len() > MAX_MANIFEST_BYTES
        {
            return Err(AppError::configuration("character manifest exceeds 64 KiB"));
        }
        let value: toml::Value = toml::from_str(text).map_err(failure)?;
        if let Some(persona) = value.get("persona").and_then(toml::Value::as_table)
        {
            for key in persona.keys()
            {
                if !["profile_id", "revision", "name", "system_prompt", "tone", "taboos", "live_mode"].contains(&key.as_str())
                {
                    return Err(AppError::configuration(format!("unsupported character persona field: {key}")));
                }
            }
        }
        let manifest: Self = value.try_into().map_err(failure)?;
        manifest.validate()?;
        Ok(manifest)
    }

    pub fn to_toml(&self) -> Result<String, AppError>
    {
        self.validate()?;
        let text = toml::to_string_pretty(self).map_err(failure)?;
        if text.len() > MAX_MANIFEST_BYTES
        {
            return Err(AppError::configuration("character manifest exceeds 64 KiB"));
        }
        Ok(text)
    }

    pub fn load(path: &Path) -> Result<Self, AppError>
    {
        let path = manifest_path(path);
        let file = File::open(&path).map_err(failure)?;
        if !file.metadata().map_err(failure)?.is_file()
        {
            return Err(AppError::configuration("character manifest must be a regular file"));
        }
        let mut text = String::new();
        file.take((MAX_MANIFEST_BYTES + 1) as u64).read_to_string(&mut text).map_err(failure)?;
        Self::parse(&text)
    }

    pub fn save_new(&self, path: &Path) -> Result<PathBuf, AppError>
    {
        let text = self.to_toml()?;
        let path = manifest_path(path);
        let mut file = OpenOptions::new().write(true).create_new(true).open(&path).map_err(failure)?;
        let result = file.write_all(text.as_bytes()).and_then(|()| file.sync_all());
        drop(file);
        if let Err(error) = result
        {
            let _ignored = std::fs::remove_file(&path);
            return Err(failure(error));
        }
        Ok(path)
    }
}

fn manifest_path(path: &Path) -> PathBuf
{
    if path.is_dir() { path.join("character.toml") } else { path.to_owned() }
}

fn failure(error: impl std::fmt::Display) -> AppError
{
    AppError::configuration(format!("character package: {error}"))
}
