use ai_ex_config::scene::SceneManifest;
use ai_ex_config::character::CharacterManifest;
use crate::scene_files::{ReadyScene, SceneAction};
use super::*;

pub(super) struct PendingScene
{
    manifest: SceneManifest,
    appearance: AppearancePanel,
}

impl DesktopApp
{
    pub(super) fn poll_scene(&mut self, context: &egui::Context)
    {
        self.begin_resume(context);
        let restoring = self.resume.phase == crate::scene_resume::ResumePhase::Loading;
        if let Some(ready) = self.scene_files.poll(context)
        {
            self.prepare_scene(context, ready);
            if restoring
            {
                self.resume.phase = if self.pending_scene.is_some() { crate::scene_resume::ResumePhase::Prepared } else { crate::scene_resume::ResumePhase::Idle };
            }
        }
        else if restoring && !self.scene_files.is_loading()
        {
            self.resume.phase = crate::scene_resume::ResumePhase::Idle;
        }
        self.apply_resume_if_ready();
    }

    pub(super) fn show_scene_panel(&mut self, ui: &mut egui::Ui)
    {
        ui.collapsing("场景组合（保存 / 载入）", |ui|
        {
            ui.weak("把当前已应用的角色、外形和显示偏好保存为一个可移动的文件夹。图片资源随包保存。");
            let enabled = !self.scene_busy() && !self.persona_apply_pending && !self.confirm_persona
                && !self.character_files.is_loading() && !self.appearance.is_loading();
            ui.add_enabled_ui(enabled, |ui|
            {
                ui.add(egui::TextEdit::singleline(&mut self.scene_files.path).desired_width(f32::INFINITY).hint_text("载入：场景文件夹或 scene.toml；保存：尚不存在的新文件夹"));
                ui.horizontal(|ui|
                {
                    ui.label("场景 ID");
                    ui.text_edit_singleline(&mut self.scene_files.id);
                });
                ui.horizontal(|ui|
                {
                    ui.label("场景名称");
                    ui.text_edit_singleline(&mut self.scene_files.name);
                });
                ui.horizontal(|ui|
                {
                    let path = std::path::PathBuf::from(self.scene_files.path.trim().trim_matches('"'));
                    if ui.add_enabled(!self.scene_files.path.trim().is_empty(), egui::Button::new("载入并预览")).clicked()
                    {
                        self.scene_files.begin(ui.ctx(), SceneAction::Import(path.clone()));
                    }
                    if ui.add_enabled(!self.scene_files.is_loading() && !self.scene_files.path.trim().is_empty(), egui::Button::new("保存当前组合")).clicked()
                    {
                        match self.appearance.scene_snapshot()
                        {
                            Ok((appearance, source)) =>
                            {
                                let manifest = SceneManifest {
                                    schema_version: 1, id: self.scene_files.id.trim().to_owned(), name: self.scene_files.name.trim().to_owned(),
                                    character: self.active_character.clone(), appearance,
                                };
                                self.scene_files.begin(ui.ctx(), SceneAction::Export(path, Box::new(manifest), source));
                            }
                            Err(error) => self.scene_files.feedback = Some(error.to_string()),
                        }
                    }
                });
                ui.weak("未应用的角色草稿不会导出；私人记忆与服务凭据不包含在场景内。保存目录的上级文件夹必须已存在。");
            });
            if self.scene_files.is_loading() { ui.label("正在处理场景与图片资源……"); }
            if let Some(feedback) = &self.scene_files.feedback { ui.label(feedback); }
            self.show_resume_controls(ui);
        });
    }

    pub(super) fn scene_busy(&self) -> bool
    {
        self.scene_files.is_loading() || self.pending_scene.is_some() || self.applying_scene.is_some()
    }

    pub(super) fn prepare_scene(&mut self, context: &egui::Context, ready: ReadyScene)
    {
        let prepared = ready.manifest.validate().and_then(|()| AppearancePanel::from_scene(context, &ready.manifest.appearance, ready.appearance));
        match prepared
        {
            Ok(appearance) =>
            {
                self.pending_persona = Some(ready.manifest.character.persona.clone());
                self.scene_files.feedback = Some(format!("已准备场景“{}”，确认后切换角色与外形。", ready.manifest.name));
                self.pending_scene = Some(PendingScene { manifest: ready.manifest, appearance });
                self.confirm_persona = true;
            }
            Err(error) => self.scene_files.feedback = Some(format!("无法准备场景，当前组合保留：{error}")),
        }
    }

    pub(super) fn finish_scene(&mut self, profile: &PersonaSnapshot)
    {
        if let Some(scene) = self.applying_scene.take()
        {
            if scene.manifest.character.persona == *profile
            {
                self.appearance = scene.appearance;
                self.active_character = scene.manifest.character;
                self.character_files.author = self.active_character.author.clone();
                self.character_files.license = self.active_character.license.clone();
                self.scene_files.id = scene.manifest.id;
                self.scene_files.name = scene.manifest.name;
                self.scene_files.feedback = Some("场景已应用：角色、外形与显示偏好已切换。".to_owned());
            }
            else
            {
                self.active_character = CharacterManifest::from_persona(profile.clone());
                self.scene_files.feedback = Some("服务返回的角色与场景不一致，保留原外形；请重新载入场景。".to_owned());
            }
        }
        else
        {
            self.active_character = CharacterManifest::from_persona(profile.clone());
            self.active_character.author = self.character_files.author.clone();
            self.active_character.license = self.character_files.license.clone();
        }
    }

    pub(super) fn show_scene_confirmation(&self, ui: &mut egui::Ui)
    {
        if let Some(scene) = &self.pending_scene
        {
            if self.resume.phase == crate::scene_resume::ResumePhase::Prepared
            {
                ui.label(if self.resume.automatic { "正在等待服务连接与角色同步，以恢复启动组合；可以取消。" } else { "这是已记住的启动组合，确认后恢复到当前服务。" });
            }
            ui.label(format!("同时应用场景：{}", scene.manifest.name));
            let body = match scene.manifest.appearance.body
            {
                ai_ex_config::scene::SceneBody::Companion => "2D 伙伴",
                ai_ex_config::scene::SceneBody::Orb => "光球",
                ai_ex_config::scene::SceneBody::Images => "图片角色",
                ai_ex_config::scene::SceneBody::Hidden => "隐藏外形",
            };
            let preset = &scene.manifest.appearance;
            ui.colored_label(egui::Color32::from_rgb(preset.accent[0], preset.accent[1], preset.accent[2]), format!("外形：{body} · 图片大小 {:.0}% · 减少动态：{}", preset.scale * 100.0, if preset.reduced_motion { "是" } else { "否" }));
            ui.label("外形、配色、大小和动态偏好会随角色一起切换。取消会保留当前组合与编辑草稿。");
        }
    }
}
