use super::*;
use crate::scene_resume::{ResumePhase, ResumeSnapshot};
use ai_ex_config::scene::SceneManifest;

impl DesktopApp {
    pub(super) fn pin_startup_scene(&mut self) {
        if self.scene_busy()
            || self.persona_apply_pending
            || self.confirm_persona
            || self.character_files.is_loading()
        {
            self.resume.feedback = Some("请先完成或取消当前切换，再设置启动组合。".to_owned());
            return;
        }
        if !self.resume.available
            || !self.persona_synced
            || self.state.connection != ConnectionState::Connected
        {
            self.resume.feedback = Some("连接服务并同步角色后，才能记住当前组合。".to_owned());
            return;
        }
        let snapshot = self
            .appearance
            .scene_snapshot()
            .and_then(|(appearance, source)| {
                let snapshot = ResumeSnapshot {
                    scene: SceneManifest {
                        schema_version: 1,
                        id: self.scene_files.id.trim().to_owned(),
                        name: self.scene_files.name.trim().to_owned(),
                        character: self.active_character.clone(),
                        appearance,
                    },
                    source,
                };
                snapshot.validate()?;
                Ok(snapshot)
            });
        match snapshot {
            Ok(snapshot) => {
                self.resume.feedback = Some(format!(
                    "已设为启动组合：{}。以后修改当前角色或外形，需要再次设置才会更新启动组合。",
                    snapshot.scene.name
                ));
                self.resume.snapshot = Some(snapshot);
                self.resume.phase = ResumePhase::Idle;
                self.resume.dirty = true;
            }
            Err(error) => self.resume.feedback = Some(format!("无法设置启动组合：{error}")),
        }
    }

    pub(super) fn show_resume_controls(&mut self, ui: &mut egui::Ui) {
        ui.separator();
        ui.strong("启动时的组合");
        if let Some(snapshot) = &self.resume.snapshot {
            ui.label(format!(
                "已记住：{} · {}",
                snapshot.scene.name, snapshot.scene.character.persona.name
            ));
        } else {
            ui.weak("尚未设置；启动时沿用服务配置中的角色。");
        }
        let enabled = !self.scene_busy()
            && !self.persona_apply_pending
            && !self.confirm_persona
            && !self.character_files.is_loading();
        ui.add_enabled_ui(enabled && self.resume.available, |ui| {
            ui.horizontal_wrapped(|ui| {
                let known = self.persona_synced
                    && self.state.connection == ConnectionState::Connected
                    && !self.appearance.is_loading();
                if ui
                    .add_enabled(known, egui::Button::new("将当前组合设为启动组合"))
                    .clicked()
                {
                    self.pin_startup_scene();
                }
                if ui
                    .add_enabled(
                        self.resume.snapshot.is_some(),
                        egui::Button::new("重新载入启动组合"),
                    )
                    .clicked()
                {
                    self.resume.automatic = false;
                    self.resume.phase = ResumePhase::Queued;
                }
                if ui.button("关闭启动恢复").clicked() {
                    self.resume.snapshot = None;
                    self.resume.phase = ResumePhase::Idle;
                    self.resume.dirty = true;
                    self.resume.feedback = Some("已关闭下次启动恢复。".to_owned());
                }
            });
        });
        ui.weak("仅为这份服务配置保存。桌面新启动服务时自动恢复；连接已有服务时先预览确认。图片素材需要保留在本机。");
        if !self.resume.available {
            ui.label("当前运行环境没有可用的本机设置存储。");
        }
        if let Some(feedback) = &self.resume.feedback {
            ui.label(feedback);
        }
    }

    pub(super) fn begin_resume(&mut self, context: &egui::Context) {
        if self.resume.phase != ResumePhase::Queued
            || self.scene_busy()
            || self.character_files.is_loading()
            || self.persona_apply_pending
            || self.confirm_persona
        {
            return;
        }
        self.resume.phase = ResumePhase::Idle;
        if let Some(snapshot) = self.resume.snapshot.clone() {
            self.scene_files.begin(
                context,
                crate::scene_files::SceneAction::Restore(Box::new(snapshot)),
            );
            if self.scene_files.is_loading() {
                self.resume.phase = ResumePhase::Loading;
            }
        }
    }

    pub(super) fn apply_resume_if_ready(&mut self) {
        if self.resume.phase == ResumePhase::Prepared
            && self.resume.automatic
            && self.persona_synced
            && self.state.connection == ConnectionState::Connected
            && let Some(profile) = self.pending_persona.clone()
        {
            self.apply_pending_persona(profile);
        }
    }

    pub(super) fn save_resume(&mut self, storage: &mut dyn eframe::Storage) {
        if let Err(error) = self.resume.save(storage) {
            self.resume.feedback = Some(format!("无法保存启动组合：{error}"));
        }
    }
}
