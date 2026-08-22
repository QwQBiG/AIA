use std::collections::VecDeque;
use std::path::Path;

use ai_ex_domain::{ComponentHealth, PersonaSnapshot, StageSnapshot, SystemEvent};
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
    show_developer: bool,
    logs: VecDeque<String>,
    log_filter: String,
    export_feedback: Option<String>,
    persona: PersonaSnapshot,
    persona_dirty: bool,
    pending_persona: Option<PersonaSnapshot>,
    confirm_persona: bool,
    persona_apply_pending: bool,
    taboos_editor: String,
    stage: StageSnapshot,
}

impl DesktopApp
{
    pub fn new(context: &eframe::CreationContext<'_>, worker: WorkerHandle, developer_mode: bool) -> Self
    {
        configure_appearance(&context.egui_ctx);
        Self {
            state: UiState::new(200).expect("valid UI capacity"),
            worker,
            input: String::new(),
            last_error: None,
            confirm_emergency_stop: false,
            health: Vec::new(),
            show_developer: developer_mode,
            logs: VecDeque::with_capacity(200),
            log_filter: String::new(),
            export_feedback: None,
            persona: PersonaSnapshot::default(),
            persona_dirty: false,
            pending_persona: None,
            confirm_persona: false,
            persona_apply_pending: false,
            taboos_editor: String::new(),
            stage: StageSnapshot::default(),
        }
    }

    fn push_log(&mut self, message: impl Into<String>)
    {
        if self.logs.len() >= 200
        {
            self.logs.pop_front();
        }
        self.logs.push_back(message.into());
    }

    fn export_diagnostics(&mut self)
    {
        let path = std::env::current_dir()
            .unwrap_or_else(|_| std::env::temp_dir())
            .join("aiex-desktop-diagnostics.log");
        let content = self.logs.iter().cloned().collect::<Vec<_>>().join("\n");
        match std::fs::write(&path, content)
        {
            Ok(()) =>
            {
                let message = format!("诊断日志已导出：{}", path.display());
                self.export_feedback = Some(message.clone());
                self.push_log(message);
            }
            Err(error) =>
            {
                let message = format!("诊断日志导出失败：{error}");
                self.export_feedback = Some(message.clone());
                self.push_log(message);
            }
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
                    self.push_log(if connected { "control connected" } else { "control disconnected" });
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
                WorkerEvent::Persona(profile) =>
                {
                    if self.persona_apply_pending || (!self.persona_dirty && self.pending_persona.is_none())
                    {
                        self.taboos_editor = profile.taboos.join("\n");
                        self.persona = profile;
                        self.persona_dirty = false;
                        self.persona_apply_pending = false;
                    }
                    else
                    {
                        self.push_log(format!("persona update received while editing: {}@{}", profile.profile_id, profile.revision));
                    }
                }
                WorkerEvent::Stage(snapshot) =>
                {
                    self.push_log(format!("stage snapshot received: {} action(s)", snapshot.actions.len()));
                    self.stage = snapshot;
                }
                WorkerEvent::Health(health) =>
                {
                    let details = health
                        .iter()
                        .map(|item| {
                            format!("health {} ready={} {}", item.component, item.ready, item.detail)
                        })
                        .collect::<Vec<_>>();
                    self.push_log(format!("health snapshot received: {} component(s)", health.len()));
                    self.health = health;
                    for detail in details
                    {
                        self.push_log(detail);
                    }
                }
                WorkerEvent::Events(events) =>
                {
                    for event in events
                    {
                        match &event.event
                        {
                            ai_ex_domain::SystemEvent::LiveEventReceived {
                                event_type,
                                summary,
                                ..
                            } => self.push_log(format!("live event {event_type}: {summary}")),
                            ai_ex_domain::SystemEvent::LiveResponseSuggested {
                                automatic, ..
                            } => self.push_log(format!(
                                "live reaction suggested (automatic={automatic})",
                            )),
                            ai_ex_domain::SystemEvent::SentenceReady { text, .. } =>
                            {
                                let preview = text.replace("\r", " ").replace("\n", " ");
                                self.push_log(format!(
                                    "stage speech queued: {}",
                                    preview.chars().take(120).collect::<String>(),
                                ));
                            }
                            ai_ex_domain::SystemEvent::EmotionChanged { emotion, .. } =>
                            {
                                self.push_log(format!("stage expression: {emotion:?}"));
                            }
                            SystemEvent::PersonaChanged { profile_id, revision } =>
                            {
                                self.push_log(format!("persona changed: {profile_id}@{revision}"));
                            }
                            SystemEvent::ComponentHealthChanged { component, ready, detail } =>
                            {
                                let state = if *ready { "ready" } else { "unavailable" };
                                self.push_log(format!("health transition {component}={state}: {detail}"));
                            }
                            _ =>
                            {
                            }
                        }
                        if self.state.apply_event(event) == ApplyOutcome::GapDetected
                        {
                            self.last_error = Some(
                                "事件序号出现缺口，正在等待状态重新同步。".to_owned(),
                            );
                            break;
                        }
                    }
                }
                WorkerEvent::Failure(error) =>
                {
                    if self.persona_apply_pending
                    {
                        self.persona_apply_pending = false;
                    }
                    self.push_log(format!("failure: {error}"));
                    self.last_error = Some(error);
                }
                WorkerEvent::Log(message) => self.push_log(message),
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
                if ui.button(if self.show_developer { "隐藏开发者诊断" } else { "开发者诊断" }).clicked()
                {
                    self.show_developer = !self.show_developer;
                }
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

    fn show_beginner_panel(&self, ui: &mut egui::Ui)
    {
        ui.group(|ui|
        {
            ui.heading("新手控制台");
            ui.label("这里可以完成日常使用；需要排查问题时，点击右上角“开发者诊断”。");
            ui.horizontal_wrapped(|ui|
            {
                let (label, color) = match self.state.connection
                {
                    ConnectionState::Connected => ("服务已连接，可以开始对话", egui::Color32::from_rgb(80, 200, 140)),
                    ConnectionState::Connecting => ("正在连接服务，请稍候", egui::Color32::YELLOW),
                    ConnectionState::Disconnected => ("服务未连接，请确认服务已启动", egui::Color32::LIGHT_RED),
                };
                ui.colored_label(color, label);
                ui.separator();
                ui.label(format!("运行状态：{:?}", self.state.runtime.state));
            });
            let guidance = match self.state.connection
            {
                ConnectionState::Connected =>
                {
                    if let Some(item) = self.health.iter().find(|item| !item.ready)
                    {
                        format!("建议：检查 {} —— {}", item.component, item.detail)
                    }
                    else
                    {
                        "建议：可以直接输入消息开始对话。".to_owned()
                    }
                }
                ConnectionState::Connecting => "建议：等待服务完成连接；不要重复启动多个服务进程。".to_owned(),
                ConnectionState::Disconnected => "建议：重新双击 AIex-Desktop.cmd；首次设置时勾选“保存后自动启动服务”，再打开“开发者诊断”查看原因。".to_owned(),
            };
            ui.small(guidance);
            let ready = self.health.iter().filter(|item| item.ready).count();
            let total = self.health.len();
            if total == 0
            {
                ui.weak("正在读取模型、插件和安全状态……");
            }
            else
            {
                ui.label(format!("组件状态：{ready}/{total} 项就绪"));
            }
            ui.small("使用下方输入框发送消息；“打断”停止当前回复；“急停”会撤销自动化许可。AIex 默认不会执行未经授权的外部动作。");
        });
    }

    fn show_persona_panel(&mut self, ui: &mut egui::Ui)
    {
        let mut changed = false;
        let mut request_confirm = false;
        ui.collapsing("角色设置（新手）", |ui|
        {
            ui.label("修改角色后必须预览并确认；活动回复期间服务会拒绝切换。开发者可同时观察事件日志。");
            ui.horizontal(|ui|
            {
                ui.label("档案 ID");
                if ui.text_edit_singleline(&mut self.persona.profile_id).changed()
                {
                    changed = true;
                }
                ui.label(format!("版本 {}", self.persona.revision));
                if ui.button("版本 +1").clicked()
                {
                    self.persona.revision = self.persona.revision.saturating_add(1);
                    changed = true;
                }
            });
            ui.horizontal(|ui|
            {
                ui.label("名称");
                if ui.text_edit_singleline(&mut self.persona.name).changed()
                {
                    changed = true;
                }
                ui.label("语气");
                if ui.text_edit_singleline(&mut self.persona.tone).changed()
                {
                    changed = true;
                }
            });
            ui.label("系统提示词");
            if ui.text_edit_multiline(&mut self.persona.system_prompt).changed()
            {
                changed = true;
            }
            ui.label("禁忌（每行一项）");
            if ui.text_edit_multiline(&mut self.taboos_editor).changed()
            {
                changed = true;
            }
            ui.horizontal(|ui|
            {
                ui.label("直播模式");
                if ui.text_edit_singleline(&mut self.persona.live_mode).changed()
                {
                    changed = true;
                }
                if ui.button("预览并请求确认").clicked()
                {
                    request_confirm = true;
                }
            });
            if self.persona_dirty
            {
                ui.colored_label(egui::Color32::YELLOW, "有未确认的角色修改");
            }
            if self.persona_apply_pending
            {
                ui.weak("正在等待服务确认角色切换……");
            }
        });
        if changed
        {
            self.persona_dirty = true;
            self.persona.taboos = self
                .taboos_editor
                .lines()
                .map(str::trim)
                .filter(|item| !item.is_empty())
                .map(str::to_owned)
                .collect();
        }
        if request_confirm
        {
            self.persona.taboos = self
                .taboos_editor
                .lines()
                .map(str::trim)
                .filter(|item| !item.is_empty())
                .map(str::to_owned)
                .collect();
            match self.persona.validate()
            {
                Ok(()) =>
                {
                    self.pending_persona = Some(self.persona.clone());
                    self.confirm_persona = true;
                    self.push_log("persona draft is ready for confirmation");
                }
                Err(error) => self.last_error = Some(error.to_string()),
            }
        }
    }

    fn show_health(&self, ui: &mut egui::Ui)
    {
        ui.collapsing("组件健康状态（实时刷新）", |ui|
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

    fn show_automation_panel(&self, ui: &mut egui::Ui)
    {
        ui.collapsing("视觉与游戏安全状态", |ui|
        {
            ui.horizontal(|ui|
            {
                ui.label("执行模式：");
                ui.colored_label(egui::Color32::from_rgb(80, 200, 140), "dry-run（无副作用）");
            });
            ui.small("真实鼠标、键盘和进程启动不会从桌面界面直接触发。动作必须经过独立插件、白名单、审计和急停。");
            let relevant = self
                .health
                .iter()
                .filter(|item| {
                    let component = item.component.to_ascii_lowercase();
                    component.contains("automation")
                        || component.contains("vision")
                        || component.contains("plugin")
                        || component.contains("stage")
                        || component.contains("obs")
                })
                .collect::<Vec<_>>();
            if relevant.is_empty()
            {
                ui.weak("等待自动化/插件健康信息……");
                return;
            }
            for item in relevant
            {
                let color = if item.ready
                {
                    egui::Color32::from_rgb(80, 200, 140)
                }
                else
                {
                    egui::Color32::LIGHT_RED
                };
                let state = if item.ready { "就绪" } else { "不可用" };
                ui.horizontal(|ui|
                {
                    ui.colored_label(color, format!("{}：{}", item.component, state));
                    if !item.detail.is_empty()
                    {
                        ui.small(&item.detail);
                    }
                });
            }
        });
    }
    fn show_stage_panel(&self, ui: &mut egui::Ui)
    {
        if !self.show_developer
        {
            return;
        }
        ui.collapsing("舞台/OBS 动作遥测", |ui|
        {
            ui.small(format!("schema={}，最近 {} 个动作", self.stage.schema_version, self.stage.actions.len()));
            if self.stage.actions.is_empty()
            {
                ui.weak("尚未收到舞台动作；可发送一条对话或运行 dry-run 回放后刷新。");
                return;
            }
            for action in self.stage.actions.iter().rev().take(24)
            {
                ui.monospace(format!("#{} [{}] {}", action.sequence, action.kind, action.detail));
            }
        });
    }

    fn show_developer_panel(&mut self, ui: &mut egui::Ui)
    {
        if !self.show_developer
        {
            return;
        }
        ui.collapsing("开发者诊断日志", |ui|
        {
            ui.horizontal_wrapped(|ui|
            {
                ui.small("桌面控制协议与事件流日志；服务端原始日志继续输出到启动终端。");
                if ui.button("导出日志").clicked()
                {
                    self.export_diagnostics();
                }
                if ui.button("清空").clicked()
                {
                    self.logs.clear();
                    self.export_feedback = None;
                }
            });
            ui.horizontal(|ui|
            {
                ui.label("筛选");
                ui.text_edit_singleline(&mut self.log_filter);
                if ui.button("清除筛选").clicked()
                {
                    self.log_filter.clear();
                }
            });
            let filtered = self
                .logs
                .iter()
                .filter(|line| self.log_filter.is_empty() || line.contains(&self.log_filter))
                .collect::<Vec<_>>();
            ui.small(format!("显示 {} / {} 条；日志最多保留 200 条。", filtered.len(), self.logs.len()));
            if let Some(feedback) = &self.export_feedback
            {
                ui.weak(feedback);
            }
            egui::ScrollArea::vertical()
                .max_height(180.0)
                .stick_to_bottom(true)
                .show(ui, |ui|
                {
                    for line in filtered
                    {
                        ui.monospace(line);
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

    fn show_persona_confirmation(&mut self, context: &egui::Context)
    {
        if !self.confirm_persona
        {
            return;
        }
        let Some(profile) = self.pending_persona.clone() else
        {
            self.confirm_persona = false;
            return;
        };
        let mut apply = false;
        let mut cancel = false;
        egui::Window::new("确认角色切换")
            .collapsible(false)
            .resizable(false)
            .anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0])
            .show(context, |ui|
            {
                ui.heading(format!("{} @ revision {}", profile.name, profile.revision));
                ui.label(format!("档案：{}", profile.profile_id));
                ui.label("确认后会替换后续回合的人格提示词；当前活动回合仍保持原人格。");
                ui.horizontal(|ui|
                {
                    if ui.button("取消").clicked()
                    {
                        cancel = true;
                    }
                    if ui.button("确认应用").clicked()
                    {
                        apply = true;
                    }
                });
            });
        if apply
        {
            if self.state.connection != ConnectionState::Connected
            {
                self.last_error = Some("服务未连接，无法应用角色。".to_owned());
            }
            else
            {
                self.persona_apply_pending = true;
                self.send(WorkerCommand::SetPersona(profile));
                self.push_log("persona apply requested");
                self.confirm_persona = false;
                self.pending_persona = None;
            }
        }
        else if cancel
        {
            self.confirm_persona = false;
            self.pending_persona = None;
            self.push_log("persona draft discarded");
        }
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
        self.show_beginner_panel(ui);
        self.show_persona_panel(ui);
        self.show_health(ui);
        self.show_automation_panel(ui);
        self.show_developer_panel(ui);
        self.show_stage_panel(ui);
        self.show_conversation(ui);
        self.show_composer(ui);
        self.show_persona_confirmation(ui.ctx());
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
