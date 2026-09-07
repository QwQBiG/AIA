use ai_ex_ui_model::{AnimationFrame, PresentationState};
use eframe::egui::{self, Color32, Painter, Pos2, Rect, Shape, Stroke, vec2};

#[path = "portrait_body.rs"]
mod body;
#[path = "portrait_face.rs"]
mod face;

pub fn draw(
    painter: &Painter,
    rect: Rect,
    state: PresentationState,
    frame: AnimationFrame,
    accent: Color32,
) {
    let scale = (rect.height() / 300.0).min(rect.width() / 260.0);
    if !scale.is_finite() || scale <= 0.0 {
        return;
    }
    let painter = painter.with_clip_rect(rect);
    let portrait = Portrait {
        painter: &painter,
        origin: rect.center() - vec2(0.0, 147.0 * scale) + vec2(0.0, frame.breath * 1.4 * scale),
        scale,
        accent,
    };
    body::draw(&portrait);
    face::draw(&portrait, state.emotion, frame);
}

struct Portrait<'a> {
    painter: &'a Painter,
    origin: Pos2,
    scale: f32,
    accent: Color32,
}

impl Portrait<'_> {
    fn point(&self, x: f32, y: f32) -> Pos2 {
        self.origin + vec2(x, y) * self.scale
    }

    fn polygon(&self, points: &[(f32, f32)], color: Color32) {
        debug_assert!(convex(points), "portrait fills must be convex");
        self.painter.add(Shape::convex_polygon(
            points.iter().map(|&(x, y)| self.point(x, y)).collect(),
            color,
            Stroke::NONE,
        ));
    }

    fn line(&self, points: &[(f32, f32)], width: f32, color: Color32) {
        self.painter.add(Shape::line(
            points.iter().map(|&(x, y)| self.point(x, y)).collect(),
            Stroke::new(width * self.scale, color),
        ));
    }

    fn ellipse(&self, x: f32, y: f32, rx: f32, ry: f32, color: Color32) {
        let points: Vec<_> = (0..40)
            .map(|step| {
                let angle = step as f32 * std::f32::consts::TAU / 40.0;
                (x + rx * angle.cos(), y + ry * angle.sin())
            })
            .collect();
        self.polygon(&points, color);
    }

    fn rounded_rect(&self, min: (f32, f32), max: (f32, f32), radius: f32, color: Color32) {
        self.painter.rect_filled(
            Rect::from_min_max(self.point(min.0, min.1), self.point(max.0, max.1)),
            egui::CornerRadius::same((radius * self.scale).round().clamp(0.0, 255.0) as u8),
            color,
        );
    }

    fn tint(&self, base: Color32, amount: f32) -> Color32 {
        let mix = |a, b| (a as f32 * (1.0 - amount) + b as f32 * amount).round() as u8;
        Color32::from_rgb(
            mix(base.r(), self.accent.r()),
            mix(base.g(), self.accent.g()),
            mix(base.b(), self.accent.b()),
        )
    }
}

fn convex(points: &[(f32, f32)]) -> bool {
    let mut positive = false;
    let mut negative = false;
    for index in 0..points.len() {
        let (a, b, c) = (
            points[index],
            points[(index + 1) % points.len()],
            points[(index + 2) % points.len()],
        );
        let cross = (b.0 - a.0) * (c.1 - b.1) - (b.1 - a.1) * (c.0 - b.0);
        positive |= cross > 0.001;
        negative |= cross < -0.001;
    }
    points.len() >= 3 && !(positive && negative)
}
