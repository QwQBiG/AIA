use std::collections::BTreeMap;
use std::io::Cursor;
use std::path::{Path, PathBuf};

use ai_ex_config::appearance::{AppearanceManifest, LoadedAppearance};
use ai_ex_domain::AppError;
use ai_ex_ui_model::{AnimationFrame, PresentationState};
use eframe::egui::{self, Color32, ColorImage, Rect, TextureHandle};

#[cfg(test)]
#[path = "image_appearance_tests.rs"]
mod tests;

pub struct DecodedAppearance {
    pub source: PathBuf,
    pub manifest: AppearanceManifest,
    pub images: BTreeMap<String, ColorImage>,
}

impl DecodedAppearance {
    pub fn load(path: &Path) -> Result<Self, AppError> {
        Self::from_loaded(LoadedAppearance::load(path)?)
    }

    pub fn from_loaded(loaded: LoadedAppearance) -> Result<Self, AppError> {
        let mut images = BTreeMap::new();
        let mut total_pixels = 0_u64;
        for (key, bytes) in loaded.images {
            let format = image::guess_format(&bytes).map_err(|error| invalid(&key, error))?;
            if !matches!(format, image::ImageFormat::Png | image::ImageFormat::Jpeg) {
                return Err(AppError::configuration(format!(
                    "image {key} must contain PNG or JPEG data"
                )));
            }
            let (width, height) = image::ImageReader::with_format(Cursor::new(&bytes), format)
                .into_dimensions()
                .map_err(|error| invalid(&key, error))?;
            total_pixels += u64::from(width) * u64::from(height);
            if width == 0
                || height == 0
                || width > 2048
                || height > 2048
                || total_pixels > 16 * 1024 * 1024
            {
                return Err(AppError::configuration(format!(
                    "image {key} exceeds 2048x2048 or the package exceeds 16 million pixels"
                )));
            }
            let mut reader = image::ImageReader::with_format(Cursor::new(bytes), format);
            let mut limits = image::Limits::default();
            limits.max_image_width = Some(2048);
            limits.max_image_height = Some(2048);
            limits.max_alloc = Some(64 * 1024 * 1024);
            reader.limits(limits);
            let rgba = reader
                .decode()
                .map_err(|error| invalid(&key, error))?
                .into_rgba8();
            images.insert(
                key,
                ColorImage::from_rgba_unmultiplied(
                    [width as usize, height as usize],
                    rgba.as_raw(),
                ),
            );
        }
        Ok(Self {
            source: loaded.source,
            manifest: loaded.manifest,
            images,
        })
    }
}

pub struct ImageAppearance {
    pub source: PathBuf,
    pub manifest: AppearanceManifest,
    textures: BTreeMap<String, TextureHandle>,
}

impl ImageAppearance {
    pub fn upload(context: &egui::Context, decoded: DecodedAppearance) -> Self {
        let textures = decoded
            .images
            .into_iter()
            .map(|(key, image)| {
                let texture = context.load_texture(
                    format!("appearance:{}:{key}", decoded.manifest.id),
                    image,
                    egui::TextureOptions::LINEAR,
                );
                (key, texture)
            })
            .collect();
        Self {
            source: decoded.source,
            manifest: decoded.manifest,
            textures,
        }
    }

    pub fn draw(
        &self,
        painter: &egui::Painter,
        rect: Rect,
        state: PresentationState,
        frame: AnimationFrame,
        scale: f32,
    ) {
        let expressive = state.connected && state.synchronized;
        let key = if expressive {
            self.manifest.frame_key(
                state.activity,
                state.emotion,
                frame.mouth_open > 0.15,
                frame.eyes_open < 0.35,
            )
        } else {
            "default"
        };
        if let Some(texture) = self.textures.get(key) {
            let size = texture.size_vec2();
            let fit = (rect.width() / size.x).min(rect.height() / size.y) * scale;
            let center = rect.center() + egui::vec2(0.0, frame.breath * 2.0);
            painter.with_clip_rect(rect).image(
                texture.id(),
                Rect::from_center_size(center, size * fit),
                Rect::from_min_max(egui::Pos2::ZERO, egui::pos2(1.0, 1.0)),
                if expressive {
                    Color32::WHITE
                } else {
                    Color32::from_gray(160)
                },
            );
        }
    }
}

fn invalid(key: &str, error: image::ImageError) -> AppError {
    AppError::configuration(format!("cannot decode appearance image {key}: {error}"))
}
