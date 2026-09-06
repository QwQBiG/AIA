use std::path::PathBuf;
use std::sync::mpsc::{self, Receiver, TryRecvError};

use ai_ex_config::character::CharacterManifest;
use ai_ex_domain::AppError;
use eframe::egui;

#[cfg(test)]
#[path = "character_files_tests.rs"]
mod tests;

pub enum FileAction
{
    Import(PathBuf),
    Export(PathBuf, Box<CharacterManifest>),
}

enum FileResult
{
    Imported(CharacterManifest),
    Exported(PathBuf),
}

#[derive(Default)]
pub struct CharacterFiles
{
    pub path: String,
    pub author: String,
    pub license: String,
    pub feedback: Option<String>,
    pending: Option<Receiver<Result<FileResult, AppError>>>,
}

impl CharacterFiles
{
    pub fn show(&mut self, ui: &mut egui::Ui, persona: &ai_ex_domain::PersonaSnapshot)
    {
        ui.collapsing("角色包（导入 / 导出）", |ui|
        {
            ui.weak("保存人格设定以便复用；外形、服务凭据和私人记忆分别管理。");
            ui.add_enabled_ui(!self.is_loading(), |ui|
            {
                ui.add(egui::TextEdit::singleline(&mut self.path).desired_width(f32::INFINITY).hint_text("character.toml 文件或已有文件夹路径"));
                ui.horizontal(|ui|
                {
                    ui.label("作者");
                    ui.text_edit_singleline(&mut self.author);
                });
                ui.horizontal(|ui|
                {
                    ui.label("使用条件");
                    ui.text_edit_singleline(&mut self.license);
                });
                ui.horizontal(|ui|
                {
                    let path = PathBuf::from(self.path.trim().trim_matches('"'));
                    if ui.add_enabled(!self.path.trim().is_empty(), egui::Button::new("导入为草稿")).clicked()
                    {
                        self.begin(ui.ctx(), FileAction::Import(path.clone()));
                    }
                    if ui.add_enabled(!self.is_loading() && !self.path.trim().is_empty(), egui::Button::new("导出当前草稿")).clicked()
                    {
                        let mut manifest = CharacterManifest::from_persona(persona.clone());
                        manifest.author = self.author.clone();
                        manifest.license = self.license.clone();
                        self.begin(ui.ctx(), FileAction::Export(path, Box::new(manifest)));
                    }
                });
                ui.weak("导出写入新文件；已有文件不会被覆盖。再次导出请换一个文件名。");
            });
            if self.is_loading()
            {
                ui.label("正在处理角色包……");
            }
            if let Some(feedback) = &self.feedback
            {
                ui.label(feedback);
            }
        });
    }

    pub fn is_loading(&self) -> bool
    {
        self.pending.is_some()
    }

    pub fn begin(&mut self, context: &egui::Context, action: FileAction)
    {
        if self.is_loading()
        {
            return;
        }
        let (sender, receiver) = mpsc::channel();
        let context = context.clone();
        match std::thread::Builder::new().name("ai-ex-character-files".to_owned()).spawn(move ||
        {
            let result = match action
            {
                FileAction::Import(path) => CharacterManifest::load(&path).map(FileResult::Imported),
                FileAction::Export(path, manifest) => manifest.save_new(&path).map(FileResult::Exported),
            };
            let _ignored = sender.send(result);
            context.request_repaint();
        })
        {
            Ok(_) => { self.pending = Some(receiver); self.feedback = None; }
            Err(error) => self.feedback = Some(format!("无法开始读写：{error}")),
        }
    }

    pub fn poll(&mut self, context: &egui::Context) -> Option<CharacterManifest>
    {
        let pending = self.pending.as_ref()?;
        let result = match pending.try_recv()
        {
            Ok(result) => result,
            Err(TryRecvError::Empty) =>
            {
                context.request_repaint_after(std::time::Duration::from_millis(100));
                return None;
            }
            Err(TryRecvError::Disconnected) => Err(AppError::unavailable("character file worker stopped")),
        };
        self.pending = None;
        match result
        {
            Ok(FileResult::Imported(manifest)) =>
            {
                self.author = manifest.author.clone();
                self.license = manifest.license.clone();
                self.feedback = Some("角色包已载入草稿；预览并应用后才会切换当前角色。".to_owned());
                Some(manifest)
            }
            Ok(FileResult::Exported(path)) =>
            {
                self.feedback = Some(format!("角色草稿已导出：{}", path.display()));
                None
            }
            Err(error) =>
            {
                self.feedback = Some(format!("角色包操作失败，原草稿保留：{error}"));
                None
            }
        }
    }
}
