use std::path::PathBuf;
use std::sync::mpsc::{self, Receiver, TryRecvError};
use ai_ex_config::appearance::LoadedAppearance;
use ai_ex_config::scene::{SceneBundle, SceneManifest};
use ai_ex_domain::AppError;
use eframe::egui;
use crate::image_appearance::DecodedAppearance;

#[cfg(test)]
#[path = "scene_files_tests.rs"]
mod tests;

pub enum SceneAction
{
    Import(PathBuf),
    Export(PathBuf, Box<SceneManifest>, Option<PathBuf>),
}

pub struct ReadyScene
{
    pub manifest: SceneManifest,
    pub appearance: Option<DecodedAppearance>,
}

enum SceneResult
{
    Loaded(Box<ReadyScene>),
    Saved(PathBuf),
}

pub struct SceneFiles
{
    pub path: String,
    pub id: String,
    pub name: String,
    pub feedback: Option<String>,
    pending: Option<Receiver<Result<SceneResult, AppError>>>,
}

impl Default for SceneFiles
{
    fn default() -> Self
    {
        Self { path: String::new(), id: "my-scene".to_owned(), name: "我的场景".to_owned(), feedback: None, pending: None }
    }
}

fn execute(action: SceneAction) -> Result<SceneResult, AppError>
{
    match action
    {
        SceneAction::Import(path) =>
        {
            let bundle = SceneBundle::load(&path)?;
            let appearance = bundle.appearance.map(DecodedAppearance::from_loaded).transpose()?;
            Ok(SceneResult::Loaded(Box::new(ReadyScene { manifest: bundle.manifest, appearance })))
        }
        SceneAction::Export(path, manifest, source) =>
        {
            let appearance = source.map(|path| LoadedAppearance::load(&path)).transpose()?;
            if let Some(loaded) = &appearance { DecodedAppearance::from_loaded(loaded.clone())?; }
            SceneBundle::save_new(&path, &manifest, appearance.as_ref()).map(SceneResult::Saved)
        }
    }
}

impl SceneFiles
{
    pub fn is_loading(&self) -> bool { self.pending.is_some() }

    pub fn begin(&mut self, context: &egui::Context, action: SceneAction)
    {
        if self.is_loading() { return; }
        let (sender, receiver) = mpsc::channel();
        let context = context.clone();
        match std::thread::Builder::new().name("ai-ex-scene-files".to_owned()).spawn(move ||
        {
            let _ignored = sender.send(execute(action));
            context.request_repaint();
        })
        {
            Ok(_) => { self.pending = Some(receiver); self.feedback = None; }
            Err(error) => self.feedback = Some(format!("无法开始读写：{error}")),
        }
    }

    pub fn poll(&mut self, context: &egui::Context) -> Option<ReadyScene>
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
            Err(TryRecvError::Disconnected) => Err(AppError::unavailable("scene file worker stopped")),
        };
        self.pending = None;
        match result
        {
            Ok(SceneResult::Loaded(ready)) => Some(*ready),
            Ok(SceneResult::Saved(path)) =>
            {
                self.feedback = Some(format!("场景已导出：{}", path.display()));
                None
            }
            Err(error) =>
            {
                self.feedback = Some(format!("场景包操作失败，当前组合保留：{error}"));
                None
            }
        }
    }
}
