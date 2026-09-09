#![forbid(unsafe_code)]

use ai_ex_config::scene::BuiltinFraming;
use ai_ex_domain::{ConversationState, Emotion};
use ai_ex_ui_model::PresentationState;
use eframe::egui::{self, Color32, Pos2, Rect, pos2, vec2};

#[path = "../src/headless_snapshot.rs"]
mod headless_snapshot;
#[path = "../src/oc_portrait.rs"]
mod portrait;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args_os()
        .nth(1)
        .ok_or("provide a new output PNG path")?;
    let width = 1600;
    let height = 1080;
    let context = egui::Context::default();
    let mut portraits: [_; 6] = std::array::from_fn(|_| portrait::OcPortrait::default());
    let output = context.run_ui(
        egui::RawInput {
            screen_rect: Some(Rect::from_min_size(
                Pos2::ZERO,
                vec2(width as f32, height as f32),
            )),
            time: Some(1.0),
            ..Default::default()
        },
        |ui| {
            ui.painter()
                .rect_filled(ui.max_rect(), 0, Color32::from_rgb(248, 247, 252));
            for (index, (framing, blink, talking, reduced, label)) in
                cases().into_iter().enumerate()
            {
                let state = PresentationState {
                    connected: true,
                    synchronized: true,
                    activity: if talking {
                        ConversationState::Speaking
                    } else {
                        ConversationState::Idle
                    },
                    emotion: Emotion::Neutral,
                    mouth_level: Some(if talking { 900 } else { 0 }),
                };
                let mut frame = state.animate(1.0, false);
                frame.eyes_open = if blink { 0.0 } else { 1.0 };
                let rect = Rect::from_min_size(
                    pos2(
                        (index % 3) as f32 * 530.0 + 22.0,
                        (index / 3) as f32 * 535.0 + 12.0,
                    ),
                    vec2(495.0, 480.0),
                );
                portraits[index]
                    .draw(
                        ui.painter(),
                        rect,
                        state,
                        frame,
                        portrait::Options {
                            framing,
                            reduced_motion: reduced,
                            accent: Color32::from_rgb(154, 133, 184),
                        },
                    )
                    .expect("embedded OC images are valid");
                ui.painter().text(
                    rect.center_bottom() + vec2(0.0, 18.0),
                    egui::Align2::CENTER_CENTER,
                    label,
                    egui::FontId::proportional(18.0),
                    Color32::from_rgb(75, 64, 88),
                );
            }
        },
    );
    headless_snapshot::save(
        &context,
        output,
        [width, height],
        std::path::Path::new(&path),
    )?;
    println!(
        "OC preview saved: {}",
        std::path::Path::new(&path).display()
    );
    Ok(())
}

fn cases() -> [(BuiltinFraming, bool, bool, bool, &'static str); 6] {
    use BuiltinFraming::{FullBody, Portrait};
    [
        (Portrait, false, false, false, "Portrait"),
        (Portrait, true, false, false, "Blink"),
        (Portrait, false, true, false, "Speaking"),
        (Portrait, true, true, false, "Blink + speaking"),
        (Portrait, true, true, true, "Reduced motion (closed mouth)"),
        (FullBody, false, false, false, "Full body"),
    ]
}
