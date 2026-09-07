use super::*;
use ai_ex_domain::ConversationState;
use ai_ex_ui_model::PresentationState;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Page {
    Conversation,
    Character,
    Scenes,
    Memory,
    Settings,
}

impl DesktopApp {
    pub(super) fn show_contents(&mut self, ui: &mut egui::Ui) {
        self.drain_events();
        if let Some(error) = self
            .owned_service
            .as_mut()
            .and_then(|service| service.take_failure())
        {
            self.push_log(&error);
            self.last_error = Some(error);
        }
        self.poll_character(ui.ctx());
        self.poll_scene(ui.ctx());
        self.appearance.poll(ui.ctx());
        egui::Panel::top("app_header")
            .resizable(false)
            .show(ui, |ui| self.show_header(ui));
        match self.page {
            Page::Conversation => self.show_chat_page(ui),
            page => {
                egui::CentralPanel::default().show(ui, |ui| {
                    egui::ScrollArea::vertical()
                        .id_salt(("app_page", page as u8))
                        .auto_shrink([false, false])
                        .show(ui, |ui| match page {
                            Page::Character => {
                                ui.heading("角色与外形");
                                ui.weak(
                                    "角色决定怎样相处，外形决定如何陪在你身边。两者可以自由组合。",
                                );
                                let state = PresentationState::from_ui(&self.state);
                                ui.add_enabled_ui(!self.scene_busy(), |ui| {
                                    self.appearance.show(
                                        ui,
                                        state,
                                        &self.active_persona.name,
                                        220.0,
                                    );
                                    ui.separator();
                                    self.show_persona_panel(ui);
                                });
                            }
                            Page::Scenes => {
                                ui.heading("场景组合");
                                ui.weak("保存喜爱的角色与外形，下次一起恢复，也可以分享给别人。");
                                self.show_scene_panel(ui);
                            }
                            Page::Settings => self.show_settings_page(ui),
                            Page::Memory => self.show_memory_page(ui),
                            Page::Conversation => unreachable!(),
                        });
                });
            }
        }
        self.show_persona_confirmation(ui.ctx());
        self.show_emergency_confirmation(ui.ctx());
        self.show_navigation_confirmation(ui.ctx());
        self.show_retained_messages(ui.ctx());
    }

    fn show_header(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            ui.heading("AIex");
            ui.separator();
            ui.colored_label(super::theme::ACCENT, self.activity_label());
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                if ui
                    .button("急停")
                    .on_hover_text("撤销自动化许可并停止当前输出")
                    .clicked()
                {
                    self.confirm_emergency_stop = true;
                }
                let active =
                    self.state.runtime.active_turn.is_some() || self.state.runtime.playback.active;
                if ui
                    .add_enabled(
                        active && self.state.connection == ConnectionState::Connected,
                        egui::Button::new("打断回复"),
                    )
                    .clicked()
                {
                    self.send(WorkerCommand::Interrupt);
                }
            });
        });
        ui.horizontal_wrapped(|ui| {
            for (page, label) in [
                (Page::Conversation, "聊天"),
                (Page::Character, "角色与外形"),
                (Page::Scenes, "场景组合"),
                (Page::Memory, "记忆"),
                (Page::Settings, "设置与诊断"),
            ] {
                ui.selectable_value(&mut self.page, page, label);
            }
        });
        if let Some(error) = self.last_error.clone() {
            ui.horizontal(|ui| {
                if ui.small_button("收起错误").clicked() {
                    self.last_error = None;
                }
                ui.add(
                    egui::Label::new(egui::RichText::new(&error).color(egui::Color32::LIGHT_RED))
                        .truncate(),
                )
                .on_hover_text(error);
            });
        }
        if let Some(notice) = self.notice.clone() {
            ui.horizontal_wrapped(|ui| {
                ui.weak(notice);
                if !self.retained_messages.is_empty() && ui.small_button("查看保留的消息").clicked()
                {
                    self.show_retained = true;
                }
                if ui.small_button("收起提示").clicked() {
                    self.notice = None;
                }
            });
        }
    }

    fn activity_label(&self) -> &'static str {
        if self.memory.mutation_pending() {
            return "正在更新记忆";
        }
        if self.state.connection != ConnectionState::Connected {
            return "正在连接，草稿可以先写";
        }
        if self.state.needs_resync || !self.persona_synced {
            return "正在同步角色与对话";
        }
        match self.state.runtime.state {
            ConversationState::Idle => "在这里，随时可以聊聊",
            ConversationState::Listening => "正在听你说",
            ConversationState::Thinking => "正在思考",
            ConversationState::Speaking => "正在回应你",
            ConversationState::Interrupted => "已停下，可以继续聊",
            ConversationState::Failed => "回复遇到问题",
            ConversationState::Stopped => "对话已停止",
        }
    }

    fn show_chat_page(&mut self, ui: &mut egui::Ui) {
        egui::Panel::bottom("conversation_composer")
            .exact_size(168.0)
            .resizable(false)
            .frame(
                egui::Frame::new()
                    .fill(super::theme::SURFACE)
                    .inner_margin(12),
            )
            .show(ui, |ui| self.show_composer(ui));
        let wide = ui.available_width() >= 860.0;
        if wide {
            let width = (ui.available_width() * 0.29).clamp(250.0, 340.0);
            egui::Panel::right("conversation_character")
                .exact_size(width)
                .resizable(false)
                .show(ui, |ui| {
                    ui.add_space(12.0);
                    let state = PresentationState::from_ui(&self.state);
                    self.appearance.show_portrait(
                        ui,
                        state,
                        &self.active_persona.name,
                        (ui.available_height() - 112.0).max(100.0),
                    );
                    ui.add_space(8.0);
                    if ui.button("自定义角色与外形").clicked() {
                        self.page = Page::Character;
                    }
                });
        }
        egui::CentralPanel::default().show(ui, |ui| {
            if !wide {
                egui::CollapsingHeader::new("查看伙伴")
                    .default_open(false)
                    .show(ui, |ui| {
                        let state = PresentationState::from_ui(&self.state);
                        self.appearance
                            .show_portrait(ui, state, &self.active_persona.name, 100.0);
                    });
            }
            crate::speech_panel::show(ui, &self.state);
            self.show_conversation(ui);
        });
    }

    fn show_settings_page(&mut self, ui: &mut egui::Ui) {
        use crate::navigation::Destination;
        ui.heading("设置与诊断");
        ui.weak("调整连接、查看运行情况，或回到首页体验人物。");
        ui.horizontal_wrapped(|ui| {
            if ui.button("连接设置").clicked() {
                self.request_navigation(ui.ctx(), Destination::Setup);
            }
            if ui.button("首页").clicked() {
                self.request_navigation(ui.ctx(), Destination::Home);
            }
            if !self.retained_messages.is_empty() && ui.button("保留的消息").clicked() {
                self.show_retained = true;
            }
        });
        if let Some(error) = self.last_error.clone() {
            ui.colored_label(egui::Color32::LIGHT_RED, &error);
            if ui.button("复制错误信息").clicked() {
                ui.ctx().copy_text(error);
            }
        }
        ui.separator();
        self.show_health(ui);
        self.show_model_panel(ui);
        self.show_policy_panel(ui);
        self.show_automation_panel(ui);
        ui.separator();
        ui.checkbox(&mut self.show_developer, "显示详细诊断");
        if self.show_developer {
            ui.weak(format!(
                "完成 {} · 打断 {} · 故障 {} · 事件 #{}",
                self.state.runtime.turns_completed,
                self.state.runtime.turns_interrupted,
                self.state.runtime.faults,
                self.state.runtime.last_sequence
            ));
            self.show_developer_panel(ui);
            self.show_stage_panel(ui);
        }
        ui.add_space(12.0);
        ui.weak(format!("版本 {}", env!("CARGO_PKG_VERSION")));
    }

    fn show_memory_page(&mut self, ui: &mut egui::Ui) {
        self.memory.set_profile(&self.active_persona.profile_id);
        let connected = self.state.connection == ConnectionState::Connected
            && self.persona_synced
            && !self.state.needs_resync;
        let idle = self.state.runtime.active_turn.is_none()
            && !self.state.runtime.playback.active
            && !self.persona_apply_pending
            && !self.confirm_persona
            && !self.scene_busy();
        if let Some(request) = self
            .memory
            .show(ui, &self.active_persona.name, connected, idle)
            && let Some(command) = self.memory.begin(request)
            && let Err(error) = self.worker.commands.send(command)
            && let WorkerCommand::Memory { request_id, .. } = error.0
        {
            self.memory.receive(
                request_id,
                Err(ai_ex_domain::AppError::unavailable(
                    "桌面网络工作线程已停止。",
                )),
            );
        }
    }
}
