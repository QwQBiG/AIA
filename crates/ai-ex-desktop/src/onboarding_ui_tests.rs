use super::*;

use crate::headless_snapshot as snapshot;

pub(crate) fn render(
    context: &egui::Context,
    size: [u32; 2],
    events: Vec<egui::Event>,
    draw: impl FnMut(&mut egui::Ui),
) -> egui::FullOutput {
    context.run_ui(
        egui::RawInput {
            screen_rect: Some(egui::Rect::from_min_size(
                egui::Pos2::ZERO,
                egui::vec2(size[0] as f32, size[1] as f32),
            )),
            events,
            ..Default::default()
        },
        draw,
    )
}

pub(crate) fn position(output: &egui::FullOutput, label: &str) -> egui::Pos2 {
    output
        .shapes
        .iter()
        .find_map(|shape| match &shape.shape {
            egui::Shape::Text(text) if text.galley.job.text == label => {
                let center = text.pos + text.galley.size() * 0.5;
                shape.clip_rect.contains(center).then_some(center)
            }
            _ => None,
        })
        .unwrap_or_else(|| panic!("visible control: {label}"))
}

pub(crate) fn pointer(position: egui::Pos2, pressed: bool) -> Vec<egui::Event> {
    vec![
        egui::Event::PointerMoved(position),
        egui::Event::PointerButton {
            pos: position,
            button: egui::PointerButton::Primary,
            pressed,
            modifiers: egui::Modifiers::NONE,
        },
    ]
}

pub(crate) fn export(label: &str, size: [u32; 2], mut draw: impl FnMut(&mut egui::Ui)) {
    let context = egui::Context::default();
    crate::app::configure_appearance(&context);
    let mut output = render(&context, size, Vec::new(), &mut draw);
    output.append(render(&context, size, Vec::new(), &mut draw));
    let directory = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../target")
        .join(format!("onboarding-review-{}", uuid::Uuid::new_v4()));
    std::fs::create_dir(&directory).unwrap();
    let path = directory.join(format!("{label}-{}x{}.png", size[0], size[1]));
    snapshot::save(&context, output, size, &path).unwrap();
    println!("{}", path.display());
}

#[test]
fn narrow_welcome_keeps_the_first_steps_visible_and_selectable() {
    let context = egui::Context::default();
    crate::app::configure_appearance(&context);
    let mut app = Welcome {
        configured: false,
        error: None,
        choice: Arc::new(Mutex::new(None)),
        appearance: AppearancePanel::default(),
    };
    let size = [640, 520];
    let mut draw = |ui: &mut egui::Ui| app.contents(ui);
    render(&context, size, Vec::new(), &mut draw);
    let output = render(&context, size, Vec::new(), &mut draw);
    position(&output, "先体验外形");
    let target = position(&output, "连接模型并开始对话");
    for pressed in [true, false] {
        render(&context, size, pointer(target, pressed), &mut draw);
    }
    assert_eq!(*app.choice.lock().unwrap(), Some(Choice::Setup));
}

#[test]
#[ignore = "exports onboarding screenshots without opening a native window"]
fn export_welcome_review() {
    for size in [[640, 520], [860, 580]] {
        let mut app = Welcome {
            configured: false,
            error: None,
            choice: Arc::new(Mutex::new(None)),
            appearance: AppearancePanel::default(),
        };
        export("welcome", size, |ui| app.contents(ui));
    }
}
