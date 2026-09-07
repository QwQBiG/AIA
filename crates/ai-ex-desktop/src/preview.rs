use ai_ex_domain::{AppError, ConversationState, Emotion};
use ai_ex_ui_model::PresentationState;
use eframe::egui;

use crate::appearance::AppearancePanel;
use crate::navigation::{Destination, Navigation};

pub fn run(package: Option<std::path::PathBuf>) -> Result<Option<Destination>, AppError> {
    let decoded = package
        .as_deref()
        .map(crate::image_appearance::DecodedAppearance::load)
        .transpose()?;
    let options = crate::navigation::companion_window([820.0, 760.0], [480.0, 480.0]);
    let navigation = Navigation::default();
    let result = navigation.clone();
    eframe::run_native(
        "AIex 外形工作室",
        options,
        Box::new(move |context| {
            crate::app::configure_appearance(&context.egui_ctx);
            let mut appearance = AppearancePanel::load(context.storage);
            if let Some(decoded) = decoded {
                appearance.use_images(&context.egui_ctx, decoded);
            }
            Ok(Box::new(PreviewApp {
                navigation,
                appearance,
                name: "AIex".to_owned(),
                state: PresentationState {
                    connected: true,
                    synchronized: true,
                    activity: ConversationState::Idle,
                    emotion: Emotion::Neutral,
                    mouth_level: None,
                },
            }))
        }),
    )
    .map_err(|error| AppError::unavailable(error.to_string()))?;
    Ok(result.take())
}

struct PreviewApp {
    navigation: Navigation,
    appearance: AppearancePanel,
    name: String,
    state: PresentationState,
}

impl PreviewApp {
    fn show_contents(&mut self, ui: &mut egui::Ui) {
        ui.heading("外形工作室");
        ui.label("同一个角色，不同的表达方式。");
        ui.weak("离线外形预览 · 状态由你选择，不连接模型、不执行角色动作。");
        ui.add_space(12.0);
        ui.horizontal(|ui| {
            ui.label("角色称呼");
            ui.text_edit_singleline(&mut self.name);
        });
        ui.horizontal_wrapped(|ui| {
            for (activity, label) in [
                (ConversationState::Idle, "陪伴"),
                (ConversationState::Listening, "倾听"),
                (ConversationState::Thinking, "思考"),
                (ConversationState::Speaking, "表达"),
                (ConversationState::Interrupted, "打断"),
                (ConversationState::Stopped, "停止"),
            ] {
                ui.selectable_value(&mut self.state.activity, activity, label);
            }
        });
        ui.horizontal_wrapped(|ui| {
            for (emotion, label) in [
                (Emotion::Neutral, "平静"),
                (Emotion::Happy, "开心"),
                (Emotion::Sad, "低落"),
                (Emotion::Angry, "生气"),
                (Emotion::Surprised, "惊讶"),
            ] {
                ui.selectable_value(&mut self.state.emotion, emotion, label);
            }
        });
        ui.separator();
        let reserved = if self.appearance.kind == crate::appearance::AppearanceKind::Images {
            440.0
        } else {
            360.0
        };
        let body_height = (ui.ctx().content_rect().height() - reserved).clamp(140.0, 360.0);
        self.appearance
            .show(ui, self.state, &self.name, body_height);
        ui.weak("这里的口型是预览动画；正式对话中随实际播放的声音变化。");
        ui.weak("外形和配色会自动保存；角色称呼与预览状态不会修改正式人格。");
    }

    fn show_navigation(&self, ui: &mut egui::Ui) {
        ui.horizontal_wrapped(|ui| {
            if ui.button("返回首页").clicked() {
                self.navigation.request(ui.ctx(), Destination::Home);
            }
            if ui.button("开始对话").clicked() {
                self.navigation.request(ui.ctx(), Destination::Connect);
            }
            ui.weak("外形会沿用到对话中；尚未连接模型时会打开设置。");
        });
    }
}

impl eframe::App for PreviewApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        egui::Panel::bottom("preview_navigation")
            .resizable(false)
            .show(ui, |ui| {
                self.show_navigation(ui);
            });
        egui::Frame::new().inner_margin(20.0).show(ui, |ui| {
            egui::ScrollArea::vertical().show(ui, |ui| self.show_contents(ui));
        });
    }

    fn save(&mut self, storage: &mut dyn eframe::Storage) {
        self.appearance.save(storage);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn preview_actions_navigate_without_starting_services() {
        for (label, expected) in [
            ("返回首页", Destination::Home),
            ("开始对话", Destination::Connect),
        ] {
            let context = egui::Context::default();
            let app = PreviewApp {
                navigation: Navigation::default(),
                appearance: AppearancePanel::default(),
                name: "伙伴".to_owned(),
                state: PresentationState {
                    connected: true,
                    synchronized: true,
                    activity: ConversationState::Idle,
                    emotion: Emotion::Neutral,
                    mouth_level: None,
                },
            };
            let input = || egui::RawInput {
                screen_rect: Some(egui::Rect::from_min_size(
                    egui::Pos2::ZERO,
                    egui::vec2(480.0, 480.0),
                )),
                ..Default::default()
            };
            let output = context.run_ui(input(), |ui| app.show_navigation(ui));
            let position = output
                .shapes
                .iter()
                .find_map(|shape| match &shape.shape {
                    egui::Shape::Text(text) if text.galley.job.text == label => {
                        Some(text.pos + text.galley.size() * 0.5)
                    }
                    _ => None,
                })
                .expect("navigation button is visible");
            for pressed in [true, false] {
                let mut input = input();
                input.events = vec![
                    egui::Event::PointerMoved(position),
                    egui::Event::PointerButton {
                        pos: position,
                        button: egui::PointerButton::Primary,
                        pressed,
                        modifiers: egui::Modifiers::NONE,
                    },
                ];
                let _output = context.run_ui(input, |ui| app.show_navigation(ui));
            }
            assert_eq!(app.navigation.take(), Some(expected));
        }
    }
}
