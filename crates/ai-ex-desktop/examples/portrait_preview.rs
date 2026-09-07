#![forbid(unsafe_code)]

use ai_ex_domain::{ConversationState, Emotion};
use ai_ex_ui_model::PresentationState;
use eframe::egui::{self, Color32, Pos2, Rect, pos2, vec2};

#[path = "../src/appearance_paint.rs"]
mod portrait;

#[path = "../src/headless_snapshot.rs"]
mod headless_snapshot;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args_os()
        .nth(1)
        .ok_or("provide a new output PNG path")?;
    let width = 1200;
    let height = 1000;
    let context = egui::Context::default();
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
            for (index, emotion) in [
                Emotion::Neutral,
                Emotion::Happy,
                Emotion::Sad,
                Emotion::Angry,
                Emotion::Surprised,
                Emotion::Neutral,
            ]
            .into_iter()
            .enumerate()
            {
                let state = PresentationState {
                    connected: true,
                    synchronized: true,
                    activity: if index == 1 {
                        ConversationState::Speaking
                    } else {
                        ConversationState::Idle
                    },
                    emotion,
                    mouth_level: None,
                };
                let rect = Rect::from_min_size(
                    pos2(
                        (index % 3) as f32 * 400.0 + 20.0,
                        (index / 3) as f32 * 500.0 + 15.0,
                    ),
                    vec2(360.0, 470.0),
                );
                portrait::draw(
                    ui.painter(),
                    rect,
                    state.animate(1.0, index == 5),
                    if index == 5 {
                        Color32::from_rgb(209, 142, 158)
                    } else {
                        Color32::from_rgb(129, 178, 247)
                    },
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
        "Portrait preview saved: {}",
        std::path::Path::new(&path).display()
    );
    println!(
        "Rows: neutral / happy speaking / sad; angry / surprised / reduced motion with another accent."
    );
    Ok(())
}
