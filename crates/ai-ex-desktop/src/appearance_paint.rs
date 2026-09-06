use ai_ex_domain::Emotion;
use ai_ex_ui_model::{AnimationFrame, PresentationState};
use eframe::egui::{self, Color32, Painter, Rect, Stroke, pos2, vec2};

use super::AppearanceKind;

pub fn draw(painter: &Painter, rect: Rect, kind: AppearanceKind, state: PresentationState, frame: AnimationFrame, accent: Color32)
{
    let painter = painter.with_clip_rect(rect);
    let scale = (rect.height() / 210.0).min(rect.width() / 240.0).max(0.0);
    let center = rect.center() + vec2(0.0, frame.breath * 2.0 * scale);
    let accent = if state.connected && state.synchronized { accent } else { Color32::GRAY };
    if kind == AppearanceKind::Orb
    {
        for ring in (1..=4).rev()
        {
            let radius = (37.0 + ring as f32 * 8.0 + frame.breath * 2.0) * scale;
            painter.circle_filled(center, radius, accent.gamma_multiply(0.04 * (5 - ring) as f32));
        }
        painter.circle_filled(center, (34.0 + frame.mouth_open * 8.0) * scale, accent);
        painter.circle_stroke(center, 52.0 * scale, Stroke::new(scale, accent));
        return;
    }
    let point = |x: f32, y: f32| center + vec2(x, y) * scale;
    painter.circle_filled(point(0.0, 65.0), 34.0 * scale, accent.gamma_multiply(0.25));
    painter.circle_filled(point(-48.0, -34.0), 19.0 * scale, accent);
    painter.circle_filled(point(48.0, -34.0), 19.0 * scale, accent);
    painter.circle_filled(point(0.0, 0.0), 60.0 * scale, accent);
    painter.circle_filled(point(0.0, 5.0), 49.0 * scale, Color32::from_rgb(241, 237, 230));
    let ink = Color32::from_rgb(40, 48, 65);
    let eye_height = (7.0 * frame.eyes_open).max(0.8);
    for x in [-19.0, 19.0]
    {
        let eye = point(x + frame.gaze_x * 5.0, -4.0);
        painter.line_segment([eye - vec2(0.0, eye_height * scale), eye + vec2(0.0, eye_height * scale)], Stroke::new(5.0 * scale, ink));
        let slope = match state.emotion
        {
            Emotion::Angry => x.signum() * 4.0,
            Emotion::Sad => -x.signum() * 4.0,
            _ => 0.0,
        };
        painter.line_segment([point(x - 7.0, -20.0 - slope), point(x + 7.0, -20.0 + slope)], Stroke::new(2.0 * scale, ink));
    }
    if frame.mouth_open > 0.0 || state.emotion == Emotion::Surprised
    {
        painter.circle_filled(point(0.0, 24.0), (3.0 + frame.mouth_open * 8.0) * scale, ink);
    }
    else
    {
        let bend = match state.emotion
        {
            Emotion::Happy => 7.0,
            Emotion::Sad | Emotion::Angry => -4.0,
            _ => 2.0,
        };
        painter.add(egui::Shape::line(vec![point(-11.0, 23.0), point(0.0, 23.0 + bend), point(11.0, 23.0)], Stroke::new(2.2 * scale, ink)));
    }
    if state.emotion == Emotion::Happy
    {
        for x in [-32.0, 32.0]
        {
            painter.circle_filled(point(x, 16.0), 6.0 * scale, Color32::from_rgb(235, 159, 168));
        }
    }
    let shadow = Rect::from_center_size(pos2(rect.center().x, rect.bottom() - 8.0 * scale), vec2(64.0, 3.0) * scale);
    painter.rect_filled(shadow, 2.0, accent.gamma_multiply(0.25));
}
