use crate::character::CharacterManifest;
use ai_ex_domain::AppError;
use serde::{Deserialize, Serialize};

#[path = "scene_files.rs"]
mod files;
pub use files::SceneBundle;

#[cfg(test)]
#[path = "scene_tests.rs"]
mod tests;

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SceneBody {
    #[default]
    #[serde(alias = "orb")]
    Companion,
    Images,
    Hidden,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SceneAppearance {
    pub body: SceneBody,
    pub accent: [u8; 3],
    pub reduced_motion: bool,
    pub scale: f32,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub package: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SceneManifest {
    pub schema_version: u16,
    pub id: String,
    pub name: String,
    pub character: CharacterManifest,
    pub appearance: SceneAppearance,
}

impl SceneManifest {
    pub fn validate(&self) -> Result<(), AppError> {
        if self.schema_version != 1
            || self.id.is_empty()
            || self.id.len() > 128
            || !self
                .id
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || b"._-".contains(&byte))
            || self.name.trim().is_empty()
            || self.name.chars().count() > 128
        {
            return Err(AppError::configuration(
                "invalid scene identity or unsupported schema_version; expected 1",
            ));
        }
        self.character.to_toml()?;
        if !self.appearance.scale.is_finite() || !(0.25..=1.0).contains(&self.appearance.scale) {
            return Err(AppError::configuration(
                "scene appearance scale must be between 0.25 and 1",
            ));
        }
        match (&self.appearance.body, &self.appearance.package) {
            (SceneBody::Images, Some(path)) if valid_relative(path) => {}
            (SceneBody::Images, _) => {
                return Err(AppError::configuration(
                    "image scenes require a relative appearance package",
                ));
            }
            (_, Some(_)) => {
                return Err(AppError::configuration(
                    "only image scenes may reference an appearance package",
                ));
            }
            _ => {}
        }
        Ok(())
    }

    pub fn parse(text: &str) -> Result<Self, AppError> {
        if text.len() > 131_072 {
            return Err(AppError::configuration("scene manifest exceeds 128 KiB"));
        }
        let value: toml::Value = toml::from_str(text).map_err(failure)?;
        if let Some(character) = value.get("character") {
            CharacterManifest::parse(&toml::to_string(character).map_err(failure)?)?;
        }
        let manifest: Self = value.try_into().map_err(failure)?;
        manifest.validate()?;
        Ok(manifest)
    }

    pub fn to_toml(&self) -> Result<String, AppError> {
        self.validate()?;
        let text = toml::to_string_pretty(self).map_err(failure)?;
        if text.len() > 131_072 {
            return Err(AppError::configuration("scene manifest exceeds 128 KiB"));
        }
        Ok(text)
    }
}

fn valid_relative(path: &str) -> bool {
    !path.is_empty()
        && path.len() <= 512
        && !path.contains(['\\', ':', '\0'])
        && !path
            .split('/')
            .any(|part| part.is_empty() || part == "." || part == "..")
        && path.ends_with(".toml")
}

fn failure(error: impl std::fmt::Display) -> AppError {
    AppError::configuration(format!("scene package: {error}"))
}
