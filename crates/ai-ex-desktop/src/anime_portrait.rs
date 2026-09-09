use std::collections::BTreeMap;
use std::sync::{Arc, OnceLock};

use ai_ex_domain::{ConversationState, Emotion};
use ai_ex_ui_model::{AnimationFrame, PresentationState};
use eframe::egui::{self, Color32, ColorImage, Rect, TextureHandle};

#[path = "anime_portrait_blend.rs"]
mod blend;
#[path = "anime_portrait_patches.rs"]
mod patches;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub(super) enum PortraitFrame {
    Idle,
    Blink,
    Speaking,
    Thinking,
    Happy,
    Sad,
    Angry,
    Surprised,
}

const BUILTIN_ASSETS: [&[u8]; 8] = [
    include_bytes!("../assets/companion/idle.png"),
    include_bytes!("../assets/companion/blink.png"),
    include_bytes!("../assets/companion/speaking.png"),
    include_bytes!("../assets/companion/thinking.png"),
    include_bytes!("../assets/companion/happy.png"),
    include_bytes!("../assets/companion/sad.png"),
    include_bytes!("../assets/companion/angry.png"),
    include_bytes!("../assets/companion/surprised.png"),
];

type DecodedImage = Result<Arc<ColorImage>, String>;
static DECODED: [OnceLock<DecodedImage>; 8] = [const { OnceLock::new() }; 8];

#[derive(Default)]
pub(super) struct AnimePortrait {
    textures: BTreeMap<PortraitFrame, TextureHandle>,
    face_blend: blend::FaceBlend,
    #[cfg(test)]
    pub(super) selected: Option<PortraitFrame>,
}

impl AnimePortrait {
    pub(super) fn draw(
        &mut self,
        painter: &egui::Painter,
        rect: Rect,
        state: PresentationState,
        frame: AnimationFrame,
        reduced_motion: bool,
        accent: Color32,
    ) -> Result<(), String> {
        let layers = select_layers(state, frame, reduced_motion);
        let texture = self.texture(painter.ctx(), PortraitFrame::Idle)?;
        let weights = self.face_blend.sample(
            layers.face,
            painter.ctx().input(|input| input.time),
            !motion_allowed(state, reduced_motion),
        );
        let mut covered = weights[PortraitFrame::Idle as usize];
        let mut faces = Vec::with_capacity(2);
        for face in blend::FACES.into_iter().skip(1) {
            let weight = weights[face as usize];
            if weight > 0.0 {
                let opacity = weight / (covered + weight);
                faces.push((self.texture(painter.ctx(), face)?, opacity));
                covered += weight;
            }
        }
        let eyes = layers
            .blinking
            .then(|| self.texture(painter.ctx(), PortraitFrame::Blink))
            .transpose()?;
        let mouth = layers
            .speaking
            .then(|| self.texture(painter.ctx(), PortraitFrame::Speaking))
            .transpose()?;
        let Some(target) = portrait_rect(rect, texture.size_vec2()) else {
            return Ok(());
        };
        let breath = if motion_allowed(state, reduced_motion) {
            frame.breath
        } else {
            0.0
        };
        let painter = painter.with_clip_rect(rect);
        let uv = portrait_uv(breath);
        painter.add(
            egui::epaint::RectShape::filled(target, 18, Color32::WHITE)
                .with_texture(texture.id(), uv),
        );
        for (texture, opacity) in faces {
            patches::draw(&painter, &texture, target, uv, patches::FACE, opacity);
        }
        if let Some(texture) = eyes {
            patches::draw(&painter, &texture, target, uv, patches::LEFT_EYE, 1.0);
            patches::draw(&painter, &texture, target, uv, patches::RIGHT_EYE, 1.0);
        }
        if let Some(texture) = mouth {
            patches::draw(&painter, &texture, target, uv, patches::MOUTH, 1.0);
        }
        painter.rect_stroke(
            target,
            18,
            egui::Stroke::new(1.0, accent.gamma_multiply(0.22)),
            egui::StrokeKind::Inside,
        );
        #[cfg(test)]
        {
            self.selected = Some(layers.dominant());
        }
        Ok(())
    }

    fn texture(
        &mut self,
        context: &egui::Context,
        frame: PortraitFrame,
    ) -> Result<TextureHandle, String> {
        if let Some(texture) = self.textures.get(&frame) {
            return Ok(texture.clone());
        }
        let pixels = decoded(frame).as_ref().map_err(Clone::clone)?;
        let texture = context.load_texture(
            format!("companion:{frame:?}"),
            egui::ImageData::Color(Arc::clone(pixels)),
            egui::TextureOptions::LINEAR,
        );
        self.textures.insert(frame, texture.clone());
        Ok(texture)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct LayerSelection {
    face: PortraitFrame,
    blinking: bool,
    speaking: bool,
}

fn select_layers(
    state: PresentationState,
    frame: AnimationFrame,
    reduced_motion: bool,
) -> LayerSelection {
    let active = expressive(state);
    let motion = active && !reduced_motion;
    let face = if !active {
        PortraitFrame::Idle
    } else if motion
        && state.activity == ConversationState::Thinking
        && state.emotion == Emotion::Neutral
    {
        PortraitFrame::Thinking
    } else {
        emotion_frame(state.emotion)
    };
    // Mouth and eye layers are independent of emotion. An obsolete syllable
    // disappears immediately, while its closed-mouth facial expression stays.
    let speaking = motion
        && state.activity == ConversationState::Speaking
        && state.mouth_level != Some(0)
        && frame.mouth_open > 0.15;
    LayerSelection {
        face,
        blinking: motion && frame.eyes_open < 0.35,
        speaking,
    }
}

#[cfg(test)]
impl LayerSelection {
    fn dominant(self) -> PortraitFrame {
        if self.speaking {
            PortraitFrame::Speaking
        } else if self.blinking {
            PortraitFrame::Blink
        } else {
            self.face
        }
    }
}

#[cfg(test)]
fn select_frame(
    state: PresentationState,
    frame: AnimationFrame,
    reduced_motion: bool,
) -> PortraitFrame {
    select_layers(state, frame, reduced_motion).dominant()
}

pub(super) fn motion_allowed(state: PresentationState, reduced_motion: bool) -> bool {
    !reduced_motion && expressive(state)
}

fn expressive(state: PresentationState) -> bool {
    state.connected
        && state.synchronized
        && !matches!(
            state.activity,
            ConversationState::Interrupted | ConversationState::Stopped | ConversationState::Failed
        )
}

fn emotion_frame(emotion: Emotion) -> PortraitFrame {
    match emotion {
        Emotion::Neutral => PortraitFrame::Idle,
        Emotion::Happy => PortraitFrame::Happy,
        Emotion::Sad => PortraitFrame::Sad,
        Emotion::Angry => PortraitFrame::Angry,
        Emotion::Surprised => PortraitFrame::Surprised,
    }
}

fn portrait_rect(rect: Rect, size: egui::Vec2) -> Option<Rect> {
    if !rect.is_finite() || !size.is_finite() || size.min_elem() <= 0.0 {
        return None;
    }
    let inset = rect.shrink(4.0);
    let fit = (inset.width() / size.x).min(inset.height() / size.y);
    if !fit.is_finite() || fit <= 0.0 {
        return None;
    }
    Some(Rect::from_center_size(inset.center(), size * fit))
}

fn portrait_uv(breath: f32) -> Rect {
    let breath = if breath.is_finite() {
        breath.clamp(-1.0, 1.0)
    } else {
        0.0
    };
    // Keep the art card still. A tiny overscan lets its contents breathe without
    // exposing a moving rectangular edge or stretching the character.
    Rect::from_min_max(
        egui::pos2(0.001, 0.001 + breath * 0.0008),
        egui::pos2(0.999, 0.999 + breath * 0.0008),
    )
}

fn decoded(frame: PortraitFrame) -> &'static DecodedImage {
    DECODED[frame as usize].get_or_init(|| decode(BUILTIN_ASSETS[frame as usize]).map(Arc::new))
}

fn decode(bytes: &[u8]) -> Result<ColorImage, String> {
    let mut reader =
        image::ImageReader::with_format(std::io::Cursor::new(bytes), image::ImageFormat::Png);
    let mut limits = image::Limits::default();
    limits.max_image_width = Some(4096);
    limits.max_image_height = Some(4096);
    limits.max_alloc = Some(64 * 1024 * 1024);
    reader.limits(limits);
    let pixels = reader
        .decode()
        .map_err(|error| error.to_string())?
        .into_rgba8();
    Ok(ColorImage::from_rgba_unmultiplied(
        [pixels.width() as usize, pixels.height() as usize],
        pixels.as_raw(),
    ))
}

#[cfg(test)]
#[path = "anime_portrait_tests.rs"]
mod tests;
