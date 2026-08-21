use std::path::Path;

use ai_ex_domain::ComponentHealth;
use ai_ex_ui_model::{ApplyOutcome, ConnectionState, TurnStatus, UiState};
use eframe::egui;

use crate::worker::{WorkerCommand, WorkerEvent, WorkerHandle};

pub struct DesktopApp
{
    state: UiState,
    worker: WorkerHandle,
    input: String,
    last_error: Option<String>,
    confirm_emergency_stop: bool,
    health: Vec<ComponentHealth>,
}

impl DesktopApp
{
    pub fn new(context: &eframe::CreationContext<'_>, worker: WorkerHandle) -> Self
    {
        configure_appearance(&context.egui_ctx);
        Self {
            state: UiState::new(200).expect("valid UI capacity"),
            worker,
            input: String::new(),
            last_error: None,
            confirm_emergency_stop: false,
            health: Vec::new(),
        }
    }

    fn drain_events(&mut self)
    {
        while let Ok(event) = self.worker.events.try_recv()
        {
            match event
            {
                WorkerEvent::Connection(connected) =>
                {
                    self.state.connection = if connected
                    {
                        ConnectionState::Connected
                    }
                    else
                    {
                        ConnectionState::Disconnected
                    };
                }
                WorkerEvent::Snapshot(snapshot) => self.state.apply_snapshot(snapshot),
                WorkerEvent::Health(health) => self.health = health,
                WorkerEvent::Events(events) =>
                {
                    for event in events
                    {
                        if self.state.apply_event(event) == ApplyOutcome::GapDetected
                        {
                            self.last_error = Some(
                                "事件序号出现缺口，正在等待状态重新同步。".to_owned(),
                            );
                            break;
                        }
                    }
                }
                WorkerEvent::Failure(error) => self.last_error = Some(error),
            }
        }
    }

    fn send(&mut self, command: WorkerCommand)
    {
        if self.worker.commands.send(command).is_err()
        {
            self.last_error = Some("桌面网络工作线程已停止。".to_owned());
        }
    }

    fn submit(&mut self)
    {
        let text = self.input.trim();
        if text.is_empty()
        {
            return;
        }
        let text = text.to_owned();
        self.send(WorkerCommand::Submit(text));
        self.input.clear();
    }

    fn show_header(&mut self, ui: &mut egui::Ui)
    {
        ui.horizontal(|ui|
        {
            ui.heading("AIex");
            ui.separator();
            let (label, color) = match self.state.connection
            {
                ConnectionState::Connected => ("已连接", egui::Color32::from_rgb(80, 200, 140)),
                ConnectionState::Connecting => ("连接中", egui::Color32::YELLOW),
                ConnectionState::Disconnected => ("未连接", egui::Color32::LIGHT_RED),
            };
            ui.colored_label(color, label);
            ui.separator();
            ui.label(format!("状态：{:?}", self.state.runtime.state));
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui|
            {
                if ui.button("急停").clicked()
                {
                    self.confirm_emergency_stop = true;
                }
                if ui.button("打断").clicked()
                {
                    self.send(WorkerCommand::Interrupt);
                }
            });
        });
        if let Some(error) = &self.last_error
        {
            ui.colored_label(egui::Color32::LIGHT_RED, error);
        }
        ui.separator();
    }

    fn show_health(&self, ui: &mut egui::Ui)
    {
        ui.collapsing("组件健康状态（启动时快照）", |ui|
        {
            if self.health.is_empty()
            {
                ui.weak("等待服务健康信息……");
                return;
            }
            ui.horizontal_wrapped(|ui|
            {
                for item in &self.health
                {
                    let color = if item.ready
                    {
                        egui::Color32::from_rgb(80, 200, 140)
                    }
                    else
                    {
                        egui::Color32::LIGHT_RED
                    };
                    let label = if item.ready { "就绪" } else { "不可用" };
                    ui.colored_label(color, format!("{}：{}", item.component, label))
                        .on_hover_text(&item.detail);
                }
            });
        });
    }

    fn show_conversation(&self, ui: &mut egui::Ui)
    {
        egui::ScrollArea::vertical()
            .max_height((ui.available_height() - 130.0).max(180.0))
            .stick_to_bottom(true)
            .auto_shrink([false, false])
            .show(ui, |ui|
            {
                for turn in &self.state.turns
                {
                    ui.group(|ui|
                    {
                        ui.strong(format!("你：{}", turn.user_text));
                        ui.add_space(6.0);
                        ui.label(format!("AIex：{}", turn.assistant_text));
                        let (status, color) = turn_status(turn.status);
                        ui.small(egui::RichText::new(status).color(color));
                    });
                    ui.add_space(8.0);
                }
                if self.state.turns.is_empty()
                {
                    ui.centered_and_justified(|ui|
                    {
                        ui.weak("连接服务后，从这里开始对话。");
                    });
                }
            });
    }

    fn show_composer(&mut self, ui: &mut egui::Ui)
    {
        ui.separator();
        let response = ui.add(
            egui::TextEdit::multiline(&mut self.input)
                .desired_rows(3)
                .hint_text("输入消息；Ctrl + Enter 发送"),
        );
        let keyboard_submit = response.has_focus()
            && ui.input(|input| {
                input.key_pressed(egui::Key::Enter) && input.modifiers.ctrl
            });
        ui.horizontal(|ui|
        {
            let enabled = self.state.connection == ConnectionState::Connected;
            if ui.add_enabled(enabled, egui::Button::new("发送")).clicked()
                || (enabled && keyboard_submit)
            {
                self.submit();
            }
            ui.weak(format!(
                "完成 {} · 打断 {} · 故障 {} · 事件 #{}",
                self.state.runtime.turns_completed,
                self.state.runtime.turns_interrupted,
                self.state.runtime.faults,
                self.state.runtime.last_sequence,
            ));
        });
    }

    fn show_emergency_confirmation(&mut self, context: &egui::Context)
    {
        if !self.confirm_emergency_stop
        {
            return;
        }
        let mut confirm = false;
        let mut cancel = false;
        egui::Window::new("确认急停")
            .collapsible(false)
            .resizable(false)
            .anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0])
            .show(context, |ui|
            {
                ui.label("急停会撤销全部自动化许可，并尝试立即打断当前输出。");
                ui.label("本次服务运行期间不能从桌面界面恢复。");
                ui.horizontal(|ui|
                {
                    if ui.button("取消").clicked()
                    {
                        cancel = true;
                    }
                    if ui
                        .add(egui::Button::new("确认急停").fill(egui::Color32::DARK_RED))
                        .clicked()
                    {
                        confirm = true;
                    }
                });
            });
        if confirm
        {
            self.send(WorkerCommand::EmergencyStop);
            self.confirm_emergency_stop = false;
        }
        else if cancel
        {
            self.confirm_emergency_stop = false;
        }
    }
}

impl eframe::App for DesktopApp
{
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame)
    {
        self.drain_events();
        self.show_header(ui);
        self.show_health(ui);
        self.show_conversation(ui);
        self.show_composer(ui);
        self.show_emergency_confirmation(ui.ctx());
        ui.ctx().request_repaint_after(std::time::Duration::from_millis(100));
    }
}

fn turn_status(status: TurnStatus) -> (&'static str, egui::Color32)
{
    match status
    {
        TurnStatus::Streaming => ("生成中", egui::Color32::LIGHT_BLUE),
        TurnStatus::Completed => ("完成", egui::Color32::GRAY),
        TurnStatus::Interrupted => ("已打断", egui::Color32::YELLOW),
        TurnStatus::Failed => ("失败", egui::Color32::LIGHT_RED),
    }
}

fn configure_appearance(context: &egui::Context)
{
    context.set_visuals(egui::Visuals::dark());
    let mut style = (*context.style_of(egui::Theme::Dark)).clone();
    style.spacing.item_spacing = egui::vec2(10.0, 8.0);
    style.spacing.button_padding = egui::vec2(14.0, 7.0);
    context.set_style_of(egui::Theme::Dark, style);

    let font_paths = [
        Path::new("C:/Windows/Fonts/msyh.ttc"),
        Path::new("C:/Windows/Fonts/simhei.ttf"),
    ];
    let Some(bytes) = font_paths.iter().find_map(|path| std::fs::read(path).ok()) else
    {
        return;
    };
    let mut fonts = egui::FontDefinitions::default();
    fonts.font_data.insert(
        "ai-ex-cjk".to_owned(),
        egui::FontData::from_owned(bytes).into(),
    );
    for family in [egui::FontFamily::Proportional, egui::FontFamily::Monospace]
    {
        fonts
            .families
            .entry(family)
            .or_default()
            .insert(0, "ai-ex-cjk".to_owned());
    }
    context.set_fonts(fonts);
}
