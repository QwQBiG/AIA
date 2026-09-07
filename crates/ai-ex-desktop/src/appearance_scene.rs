use super::{AppearanceKind, AppearancePanel};
use crate::image_appearance::DecodedAppearance;
use ai_ex_config::scene::{SceneAppearance, SceneBody};
use ai_ex_domain::AppError;
use eframe::egui;
use std::path::PathBuf;

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
        let mut panel = Self {
            kind,
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
