use super::*;
use ai_ex_ui_model::TurnStatus;

pub(super) const COMPOSER_ID: &str = "conversation_input";

impl DesktopApp {
    pub(super) fn show_conversation(&self, ui: &mut egui::Ui) {
        egui::ScrollArea::vertical()
            .id_salt("conversation_history")
            .max_height(ui.available_height())
            .stick_to_bottom(true)
            .auto_shrink([false, false])
            .show(ui, |ui| {
                if self.state.turns.is_empty() {
                    ui.add_space(32.0);
                    ui.vertical_centered(|ui| {
                        ui.heading(format!("和 {} 聊聊", self.active_persona.name));
                        ui.add_space(8.0);
                        ui.weak("今天发生了什么，或是想一起做点什么？");
                        if !self.can_submit() {
                            ui.weak("连接准备好后就能发送，也可以先写下想说的话。");
                        }
                    });
                }
                for turn in &self.state.turns {
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Min), |ui| {
                        egui::Frame::new()
                            .fill(egui::Color32::from_rgb(41, 54, 76))
                            .corner_radius(12)
                            .inner_margin(12)
                            .show(ui, |ui| {
                                ui.set_max_width((ui.available_width() * 0.88).max(120.0));
                                ui.with_layout(egui::Layout::top_down(egui::Align::Min), |ui| {
                                    ui.small("你");
                                    ui.add(egui::Label::new(&turn.user_text).wrap());
                                });
                            });
                    });
                    ui.add_space(4.0);
                    egui::Frame::new()
                        .fill(super::theme::SURFACE)
                        .corner_radius(12)
                        .inner_margin(12)
                        .show(ui, |ui| {
                            ui.set_max_width((ui.available_width() * 0.95).max(120.0));
                            ui.colored_label(super::theme::ACCENT, &self.active_persona.name);
                            if turn.assistant_text.is_empty()
                                && turn.status == TurnStatus::Streaming
                            {
                                ui.weak("正在想怎么回应你……");
                            } else {
                                ui.add(egui::Label::new(&turn.assistant_text).wrap());
                            }
                            match turn.status {
                                TurnStatus::Streaming => {
                                    ui.weak("正在回复……");
                                }
                                TurnStatus::Interrupted => {
                                    ui.weak("这次回复已打断");
                                }
                                TurnStatus::Failed => {
                                    ui.colored_label(
                                        egui::Color32::LIGHT_RED,
                                        "回复未完成，请检查连接后重试",
                                    );
                                }
                                TurnStatus::Completed => {}
                            }
                        });
                    ui.add_space(16.0);
                }
            });
    }

    pub(super) fn show_composer(&mut self, ui: &mut egui::Ui) {
        let ime_event = ui.input(|input| {
            let mut seen = false;
            for event in &input.events {
                if let egui::Event::Ime(event) = event {
                    seen = true;
                    match event {
                        egui::ImeEvent::Preedit { text, .. } => {
                            self.composer_ime_active = !text.is_empty()
                        }
                        egui::ImeEvent::Commit(_) => self.composer_ime_active = false,
                        _ => {}
                    }
                }
            }
            seen
        });
        let id = egui::Id::new(COMPOSER_ID);
        let focused = ui.memory(|memory| memory.has_focus(id));
        let keyboard_submit = focused
            && !ime_event
            && !self.composer_ime_active
            && ui.input_mut(|input| input.consume_key(egui::Modifiers::CTRL, egui::Key::Enter));
        let response = egui::ScrollArea::vertical()
            .id_salt("conversation_draft")
            .max_height(68.0)
            .auto_shrink([false, false])
            .show(ui, |ui| {
                ui.add(
                    egui::TextEdit::multiline(&mut self.input)
                        .id(id)
                        .desired_rows(2)
                        .desired_width(f32::INFINITY)
                        .hint_text("写下想说的话……"),
                )
            })
            .inner;
        if !response.has_focus() {
            self.composer_ime_active = false;
        }
        ui.horizontal(|ui| {
            let enabled = self.can_submit()
                && !self.input.trim().is_empty()
                && !ime_event
                && !self.composer_ime_active;
            let send = ui.add_enabled(
                enabled,
                egui::Button::new("发送").min_size(egui::vec2(76.0, 32.0)),
            );
            if enabled && (send.clicked() || keyboard_submit) {
                self.submit();
                response.request_focus();
            }
            ui.small("Enter 换行 · Ctrl + Enter 发送");
        });
        if !self.can_submit() {
            ui.weak(if self.persona_apply_pending || self.confirm_persona {
                "角色切换确认完成后可以发送；草稿会保留。"
            } else if self.state.connection == ConnectionState::Connected {
                "正在同步角色与对话状态，草稿会保留。"
            } else {
                "等待连接，可以先写草稿；连接设置位于“设置与诊断”。"
            });
        }
    }
}
