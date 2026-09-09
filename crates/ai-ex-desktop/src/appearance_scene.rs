use super::{AppearanceKind, AppearancePanel};
use crate::builtin_character::BuiltinCharacter;
use crate::image_appearance::DecodedAppearance;
use ai_ex_config::scene::{BuiltinFraming, SceneAppearance, SceneBody};
use ai_ex_domain::AppError;
use eframe::egui;
use std::path::PathBuf;

#[cfg(test)]
#[path = "appearance_scene_tests.rs"]
mod tests;

impl AppearancePanel {
    pub fn is_loading(&self) -> bool {
        self.images.is_loading()
    }

    pub fn scene_snapshot(&self) -> Result<(SceneAppearance, Option<PathBuf>), AppError> {
        if self.is_loading() {
            return Err(AppError::configuration(
                "wait for the appearance import to finish",
            ));
        }
        let body = match self.kind {
            AppearanceKind::Companion => SceneBody::Companion,
            AppearanceKind::Images => SceneBody::Images,
            AppearanceKind::Hidden => SceneBody::Hidden,
        };
        let source = if body == SceneBody::Images {
            Some(
                self.images
                    .current
                    .as_ref()
                    .ok_or_else(|| {
                        AppError::configuration(
                            "import an image package before exporting this scene",
                        )
                    })?
                    .source
                    .clone(),
            )
        } else {
            None
        };
        Ok((
            SceneAppearance {
                body,
                accent: self.accent,
                reduced_motion: self.reduced_motion,
                scale: self.image_scale,
                package: source
                    .as_ref()
                    .map(|_| "appearance/appearance.toml".to_owned()),
                builtin_id: (body == SceneBody::Companion
                    && self.builtin != BuiltinCharacter::Original)
                    .then(|| self.builtin.id().to_owned()),
                framing: if body == SceneBody::Companion
                    && self.builtin != BuiltinCharacter::Original
                {
                    self.framing
                } else {
                    BuiltinFraming::Portrait
                },
            },
            source,
        ))
    }

    pub fn from_scene(
        context: &egui::Context,
        preset: &SceneAppearance,
        decoded: Option<DecodedAppearance>,
    ) -> Result<Self, AppError> {
        if (preset.body == SceneBody::Images) != decoded.is_some() {
            return Err(AppError::configuration("scene appearance is incomplete"));
        }
        let kind = match preset.body {
            SceneBody::Companion => AppearanceKind::Companion,
            SceneBody::Images => AppearanceKind::Images,
            SceneBody::Hidden => AppearanceKind::Hidden,
        };
        let builtin = match preset.builtin_id.as_deref() {
            None => BuiltinCharacter::Original,
            Some(id) => BuiltinCharacter::from_id(id).ok_or_else(|| {
                AppError::configuration(format!("unknown built-in scene character: {id}"))
            })?,
        };
        let mut panel = Self {
            kind,
            builtin,
            framing: preset.framing,
            accent: preset.accent,
            reduced_motion: preset.reduced_motion,
            image_scale: preset.scale,
            ..Default::default()
        };
        if let Some(decoded) = decoded {
            panel.use_images(context, decoded);
        }
        Ok(panel)
    }
}
