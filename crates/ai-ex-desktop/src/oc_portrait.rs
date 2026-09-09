use std::collections::BTreeMap;

use ai_ex_config::scene::BuiltinFraming;
use ai_ex_domain::ConversationState;
use ai_ex_ui_model::{AnimationFrame, PresentationState};
use eframe::egui::{self, Color32, Rect, TextureHandle};

#[path = "oc_portrait_assets.rs"]
mod assets;
#[path = "oc_portrait_patches.rs"]
mod patches;
#[cfg(test)]
#[path = "oc_portrait_tests.rs"]
mod tests;
use assets::Frame;

pub(super) struct Options {
    pub framing: BuiltinFraming,
    pub reduced_motion: bool,
    pub accent: Color32,
}

#[derive(Default)]
pub(super) struct OcPortrait {
    textures: BTreeMap<Frame, TextureHandle>,
    #[cfg(test)]
    pub(super) visible_layers: [bool; 2],
}

impl OcPortrait {
    pub(super) fn draw(
        &mut self,
        painter: &egui::Painter,
        rect: Rect,
        state: PresentationState,
        frame: AnimationFrame,
        options: Options,
    ) -> Result<(), String> {
        let layers = selected_layers(state, frame, options.reduced_motion);
        let base = self.texture(painter.ctx(), Frame::Portrait)?;
        let eyes = layers[0]
            .then(|| self.texture(painter.ctx(), Frame::Blink))
            .transpose()?;
        let mouth = layers[1]
            .then(|| self.texture(painter.ctx(), Frame::Speaking))
            .transpose()?;
        let uv = framing_uv(
            options.framing,
            motion_allowed(state, options.reduced_motion).then_some(frame.breath),
        );
        let Some(target) = fitted_rect(rect, base.size_vec2() * uv.size()) else {
            return Ok(());
        };
        let painter = painter.with_clip_rect(rect);
        painter.add(
            egui::epaint::RectShape::filled(target, 18, Color32::WHITE).with_texture(base.id(), uv),
        );
        if let Some(eyes) = eyes {
            patches::draw(&painter, eyes.id(), target, uv, patches::LEFT_EYE);
            patches::draw(&painter, eyes.id(), target, uv, patches::RIGHT_EYE);
        }
        if let Some(mouth) = mouth {
            patches::draw(&painter, mouth.id(), target, uv, patches::MOUTH);
        }
        painter.rect_stroke(
            target,
            18,
            egui::Stroke::new(1.0, options.accent.gamma_multiply(0.22)),
            egui::StrokeKind::Inside,
        );
        #[cfg(test)]
        {
            self.visible_layers = layers;
        }
        Ok(())
    }

    fn texture(&mut self, context: &egui::Context, frame: Frame) -> Result<TextureHandle, String> {
        if let Some(texture) = self.textures.get(&frame) {
            return Ok(texture.clone());
        }
        let pixels = assets::decoded(frame).as_ref().map_err(Clone::clone)?;
        let texture = context.load_texture(
            format!("builtin:oc-01:{frame:?}"),
            egui::ImageData::Color(std::sync::Arc::clone(pixels)),
            egui::TextureOptions::LINEAR,
        );
        self.textures.insert(frame, texture.clone());
        Ok(texture)
    }
}

fn selected_layers(state: PresentationState, frame: AnimationFrame, reduced: bool) -> [bool; 2] {
    let active = motion_allowed(state, reduced);
    [
        active && frame.eyes_open < 0.35,
        active
            && state.activity == ConversationState::Speaking
            && state.mouth_level != Some(0)
            && frame.mouth_open > 0.15,
    ]
}

pub(super) fn motion_allowed(state: PresentationState, reduced: bool) -> bool {
    !reduced
        && state.connected
        && state.synchronized
        && !(state.activity == ConversationState::Speaking && state.mouth_level == Some(0))
        && !matches!(
            state.activity,
            ConversationState::Interrupted | ConversationState::Stopped | ConversationState::Failed
        )
}

fn framing_uv(framing: BuiltinFraming, breath: Option<f32>) -> Rect {
    match framing {
        BuiltinFraming::FullBody => Rect::from_min_max(egui::Pos2::ZERO, egui::pos2(1.0, 1.0)),
        BuiltinFraming::Portrait => {
            let shift = breath
                .filter(|value| value.is_finite())
                .map_or(0.0, |value| (value.clamp(-1.0, 1.0) + 1.0) * 0.0006);
            Rect::from_min_max(egui::pos2(0.22, shift), egui::pos2(0.78, 0.45 + shift))
        }
    }
}

fn fitted_rect(rect: Rect, size: egui::Vec2) -> Option<Rect> {
    if !rect.is_finite() || !size.is_finite() || size.min_elem() <= 0.0 {
        return None;
    }
    let inset = rect.shrink(4.0);
    let fit = (inset.width() / size.x).min(inset.height() / size.y);
    (fit.is_finite() && fit > 0.0).then(|| Rect::from_center_size(inset.center(), size * fit))
}
