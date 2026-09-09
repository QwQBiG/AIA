#![forbid(unsafe_code)]

use ai_ex_domain::{ConversationState, Emotion};
use ai_ex_ui_model::PresentationState;
use eframe::egui::{self, Color32, Pos2, Rect, pos2, vec2};

#[path = "../src/anime_portrait.rs"]
mod portrait;

#[path = "../src/headless_snapshot.rs"]
mod headless_snapshot;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args_os()
        .nth(1)
        .ok_or("provide a new output PNG path")?;
    let width = 1600;
    let height = 1000;
    let context = egui::Context::default();
    let mut portraits: [_; 8] = std::array::from_fn(|_| portrait::AnimePortrait::default());
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
            for (index, (emotion, activity, time, label)) in cases().into_iter().enumerate() {
                let state = PresentationState {
                    connected: true,
                    synchronized: true,
                    activity,
                    emotion,
                    mouth_level: Some(if activity == ConversationState::Speaking {
                        850
                    } else {
                        0
                    }),
                };
                let rect = Rect::from_min_size(
                    pos2(
                        (index % 4) as f32 * 400.0 + 20.0,
                        (index / 4) as f32 * 500.0 + 15.0,
                    ),
                    vec2(360.0, 440.0),
                );
                portraits[index]
                    .draw(
                        ui.painter(),
                        rect,
                        state,
                        state.animate(time, false),
                        false,
                        Color32::from_rgb(154, 133, 184),
                    )
                    .expect("embedded portrait images are valid");
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
        "Portrait preview saved: {}",
        std::path::Path::new(&path).display()
    );
    println!("Rows: companion / blink / speaking / thinking; happy / sad / angry / surprised.");
    Ok(())
}

fn cases() -> [(Emotion, ConversationState, f64, &'static str); 8] {
    use ConversationState::{Idle, Speaking, Thinking};
    use Emotion::{Angry, Happy, Neutral, Sad, Surprised};
    [
        (Neutral, Idle, 1.0, "Companion"),
        (Neutral, Idle, 0.08, "Blink"),
        (Neutral, Speaking, 1.0, "Speaking"),
        (Neutral, Thinking, 1.0, "Thinking"),
        (Happy, Idle, 1.0, "Happy"),
        (Sad, Idle, 1.0, "Sad"),
        (Angry, Idle, 1.0, "Angry"),
        (Surprised, Idle, 1.0, "Surprised"),
    ]
}
