use ai_ex_domain::{AppError, ConversationState, Emotion};
use ai_ex_ui_model::PresentationState;
use eframe::egui;

use crate::appearance::AppearancePanel;

pub fn run(package: Option<std::path::PathBuf>) -> Result<(), AppError>
{
    let decoded = package.as_deref().map(crate::image_appearance::DecodedAppearance::load).transpose()?;
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([820.0, 760.0])
            .with_min_inner_size([480.0, 480.0]),
        ..Default::default()
    };
    eframe::run_native("AIex 外形工作室", options, Box::new(move |context|
    {
        crate::app::configure_appearance(&context.egui_ctx);
        let mut appearance = AppearancePanel::load(context.storage);
        if let Some(decoded) = decoded
        {
            appearance.use_images(&context.egui_ctx, decoded);
        }
        Ok(Box::new(PreviewApp {
            appearance,
            name: "AIex".to_owned(),
            state: PresentationState {
                connected: true, synchronized: true,
                activity: ConversationState::Idle, emotion: Emotion::Neutral,
                mouth_level: None,
            },
        }))
    }))
    .map_err(|error| AppError::unavailable(error.to_string()))
}

struct PreviewApp
{
    appearance: AppearancePanel,
    name: String,
    state: PresentationState,
}

impl PreviewApp
{
    fn show_contents(&mut self, ui: &mut egui::Ui)
    {
        ui.heading("外形工作室");
        ui.label("同一个角色，不同的表达方式。");
        ui.weak("离线外形预览 · 状态由你选择，不连接模型、不执行角色动作。");
        ui.add_space(12.0);
        ui.horizontal(|ui|
        {
            ui.label("角色称呼");
            ui.text_edit_singleline(&mut self.name);
        });
        ui.horizontal_wrapped(|ui|
        {
            for (activity, label) in [
                (ConversationState::Idle, "陪伴"), (ConversationState::Listening, "倾听"),
                (ConversationState::Thinking, "思考"), (ConversationState::Speaking, "表达"),
                (ConversationState::Interrupted, "打断"), (ConversationState::Stopped, "停止"),
            ]
            {
                ui.selectable_value(&mut self.state.activity, activity, label);
            }
        });
        ui.horizontal_wrapped(|ui|
        {
            for (emotion, label) in [
                (Emotion::Neutral, "平静"), (Emotion::Happy, "开心"),
                (Emotion::Sad, "低落"), (Emotion::Angry, "生气"), (Emotion::Surprised, "惊讶"),
            ]
            {
                ui.selectable_value(&mut self.state.emotion, emotion, label);
            }
        });
        ui.separator();
        let reserved = if self.appearance.kind == crate::appearance::AppearanceKind::Images { 440.0 } else { 360.0 };
        let body_height = (ui.ctx().content_rect().height() - reserved).clamp(140.0, 360.0);
        self.appearance.show(ui, self.state, &self.name, body_height);
        ui.weak("口型是表达状态的示意动画，尚未与实际音频振幅同步。");
        ui.weak("外形和配色会自动保存；角色称呼与预览状态不会修改正式人格。");
    }

}

impl eframe::App for PreviewApp
{
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame)
    {
        egui::Frame::new().inner_margin(20.0).show(ui, |ui|
        {
            egui::ScrollArea::vertical().show(ui, |ui| self.show_contents(ui));
        });
    }

    fn save(&mut self, storage: &mut dyn eframe::Storage)
    {
        self.appearance.save(storage);
    }
}
