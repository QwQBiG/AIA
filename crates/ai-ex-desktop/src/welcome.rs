use std::sync::{Arc, Mutex};

use ai_ex_domain::AppError;
use eframe::egui;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Choice {
    Preview,
    Connect,
    Setup,
}

pub fn run(configured: bool) -> Result<Option<Choice>, AppError> {
    window(configured, None)
}

pub fn show_error(message: String) -> Result<(), AppError> {
    window(false, Some(message)).map(|_| ())
}

pub fn recover(message: String) -> Result<Option<Choice>, AppError> {
    window(false, Some(message))
}

fn window(configured: bool, error: Option<String>) -> Result<Option<Choice>, AppError> {
    let choice = Arc::new(Mutex::new(None));
    let result = choice.clone();
    eframe::run_native(
        "AIex 数字伙伴",
        eframe::NativeOptions {
            viewport: egui::ViewportBuilder::default()
                .with_inner_size([680.0, 460.0])
                .with_min_inner_size([520.0, 380.0]),
            ..Default::default()
        },
        Box::new(move |context| {
            crate::app::configure_appearance(&context.egui_ctx);
            Ok(Box::new(Welcome {
                configured,
                error,
                choice,
            }))
        }),
    )
    .map_err(|error| AppError::unavailable(error.to_string()))?;
    let selected = *result
        .lock()
        .map_err(|_| AppError::unavailable("welcome result lock poisoned"))?;
    Ok(selected)
}

struct Welcome {
    configured: bool,
    error: Option<String>,
    choice: Arc<Mutex<Option<Choice>>>,
}

impl Welcome {
    fn contents(&mut self, ui: &mut egui::Ui) {
        ui.add_space(16.0);
        ui.heading("欢迎，先让伙伴来到身边");
        ui.add_space(8.0);
        if let Some(error) = &self.error {
            ui.colored_label(egui::Color32::LIGHT_RED, "暂时无法启动");
            ui.label(error);
            ui.label("连接信息有误时可修改设置再试，也可以先离线体验人物。若提示文件缺失或损坏，请按错误说明修复，或在新目录完整解压程序包。");
            if ui.button("复制错误信息").clicked() {
                ui.ctx().copy_text(error.clone());
            }
            self.button(ui, "连接设置", Choice::Setup);
            self.button(ui, "先体验外形", Choice::Preview);
            if ui.button("关闭").clicked() {
                ui.ctx().send_viewport_cmd(egui::ViewportCommand::Close);
            }
            return;
        }
        ui.label("先认识你的伙伴，再按自己的节奏连接模型、组装角色。");
        ui.add_space(18.0);
        self.button(ui, "先体验外形", Choice::Preview);
        ui.label("无需账号或模型，立即体验人物表情、配色和自定义图片外形。");
        ui.add_space(12.0);
        self.button(
            ui,
            if self.configured {
                "开始对话"
            } else {
                "连接模型并开始对话"
            },
            if self.configured {
                Choice::Connect
            } else {
                Choice::Setup
            },
        );
        ui.label("连接你选择的模型服务，使用角色、记忆和场景组合。");
        ui.add_space(12.0);
        if self.configured {
            self.button(ui, "连接设置", Choice::Setup);
        }
        ui.add_space(16.0);
        ui.weak("真实对话需要模型服务；语音和麦克风可以稍后配置。");
        ui.weak(format!("版本 {}", env!("CARGO_PKG_VERSION")));
    }

    fn button(&self, ui: &mut egui::Ui, label: &str, choice: Choice) {
        if ui
            .add_sized([240.0, 42.0], egui::Button::new(label))
            .clicked()
        {
            if let Ok(mut selected) = self.choice.lock() {
                *selected = Some(choice);
            }
            ui.ctx().send_viewport_cmd(egui::ViewportCommand::Close);
        }
    }
}

impl eframe::App for Welcome {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        egui::ScrollArea::vertical().show(ui, |ui| self.contents(ui));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn welcome_buttons_select_preview_setup_or_conversation_without_opening_windows() {
        for (configured, label, expected) in [
            (false, "先体验外形", Choice::Preview),
            (false, "连接模型并开始对话", Choice::Setup),
            (true, "开始对话", Choice::Connect),
            (true, "连接设置", Choice::Setup),
        ] {
            let context = egui::Context::default();
            let choice = Arc::new(Mutex::new(None));
            let mut app = Welcome {
                configured,
                error: None,
                choice: choice.clone(),
            };
            let output = context.run_ui(egui::RawInput::default(), |ui| app.contents(ui));
            let position = output
                .shapes
                .iter()
                .find_map(|shape| match &shape.shape {
                    egui::epaint::Shape::Text(text) if text.galley.job.text == label => {
                        Some(text.pos + text.galley.size() * 0.5)
                    }
                    _ => None,
                })
                .expect("welcome action is visible");
            for pressed in [true, false] {
                let _output = context.run_ui(
                    egui::RawInput {
                        events: vec![
                            egui::Event::PointerMoved(position),
                            egui::Event::PointerButton {
                                pos: position,
                                button: egui::PointerButton::Primary,
                                pressed,
                                modifiers: egui::Modifiers::NONE,
                            },
                        ],
                        ..Default::default()
                    },
                    |ui| app.contents(ui),
                );
            }
            assert_eq!(*choice.lock().unwrap(), Some(expected));
        }
    }

    #[test]
    fn welcome_and_startup_errors_are_readable_without_a_console() {
        for configured in [false, true] {
            let context = egui::Context::default();
            let mut app = Welcome {
                configured,
                error: None,
                choice: Arc::new(Mutex::new(None)),
            };
            let output = context.run_ui(egui::RawInput::default(), |ui| app.contents(ui));
            let texts: Vec<_> = output
                .shapes
                .iter()
                .filter_map(|shape| match &shape.shape {
                    egui::epaint::Shape::Text(text) => Some(text.galley.job.text.as_str()),
                    _ => None,
                })
                .collect();
            assert!(texts.contains(&"先体验外形"));
            assert!(texts.contains(&if configured {
                "开始对话"
            } else {
                "连接模型并开始对话"
            }));
            app.error = Some("service package is incomplete".to_owned());
            let output = context.run_ui(egui::RawInput::default(), |ui| app.contents(ui));
            assert!(output.shapes.iter().any(|shape| matches!(&shape.shape, egui::epaint::Shape::Text(text) if text.galley.job.text == "service package is incomplete")));
        }
    }
}
