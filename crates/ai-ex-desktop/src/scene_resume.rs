use ai_ex_config::scene::{SceneBody, SceneManifest};
use ai_ex_domain::AppError;
use std::path::{Path, PathBuf};

#[cfg(test)]
#[path = "scene_resume_tests.rs"]
mod tests;

pub struct ResumeLaunch {
    pub scope: String,
    pub automatic: bool,
}

impl ResumeLaunch {
    pub fn new(config: &Path, address: &str, automatic: bool) -> Result<Self, AppError> {
        let path = config.canonicalize().map_err(|error| {
            AppError::configuration(format!("cannot identify desktop configuration: {error}"))
        })?;
        let path = path
            .to_str()
            .ok_or_else(|| AppError::configuration("configuration path must be UTF-8"))?;
        Ok(Self {
            scope: format!("scene.startup.v1.{}:{path}:{address}", path.len()),
            automatic,
        })
    }
}

#[derive(Clone)]
pub struct ResumeSnapshot {
    pub scene: SceneManifest,
    pub source: Option<PathBuf>,
}

impl ResumeSnapshot {
    pub fn validate(&self) -> Result<(), AppError> {
        self.scene.validate()?;
        if (self.scene.appearance.body == SceneBody::Images) != self.source.is_some() {
            return Err(AppError::configuration(
                "startup scene image source is incomplete",
            ));
        }
        if let Some(path) = &self.source
            && (!path.is_absolute() || path.to_str().is_none_or(|path| path.len() > 32_768))
        {
            return Err(AppError::configuration(
                "startup image source must be an absolute UTF-8 path",
            ));
        }
        Ok(())
    }
}

#[derive(Default, PartialEq, Eq)]
pub enum ResumePhase {
    #[default]
    Idle,
    Queued,
    Loading,
    Prepared,
}

#[derive(Default)]
pub struct SceneResume {
    pub snapshot: Option<ResumeSnapshot>,
    pub phase: ResumePhase,
    pub automatic: bool,
    pub feedback: Option<String>,
    pub dirty: bool,
    pub available: bool,
    scope: String,
}

impl SceneResume {
    pub fn load(storage: Option<&dyn eframe::Storage>, launch: ResumeLaunch) -> Self {
        let mut result = Self {
            scope: launch.scope,
            automatic: launch.automatic,
            available: storage.is_some(),
            ..Default::default()
        };
        if let Some(storage) = storage
            && let Some(text) = storage.get_string(&format!("{}.manifest", result.scope))
        {
            let source = storage
                .get_string(&format!("{}.source", result.scope))
                .filter(|value| !value.is_empty())
                .map(PathBuf::from);
            let parsed = SceneManifest::parse(&text).and_then(|scene| {
                let snapshot = ResumeSnapshot { scene, source };
                snapshot.validate()?;
                Ok(snapshot)
            });
            match parsed {
                Ok(snapshot) => {
                    result.snapshot = Some(snapshot);
                    result.phase = ResumePhase::Queued;
                }
                Err(error) => {
                    result.feedback = Some(format!("启动组合不可用，保留原设置：{error}"))
                }
            }
        }
        result
    }

    pub fn save(&mut self, storage: &mut dyn eframe::Storage) -> Result<(), AppError> {
        if !self.dirty {
            return Ok(());
        }
        let manifest_key = format!("{}.manifest", self.scope);
        let source_key = format!("{}.source", self.scope);
        if let Some(snapshot) = &self.snapshot {
            snapshot.validate()?;
            let text = snapshot.scene.to_toml()?;
            storage.set_string(
                &source_key,
                snapshot
                    .source
                    .as_ref()
                    .and_then(|path| path.to_str())
                    .unwrap_or_default()
                    .to_owned(),
            );
            storage.set_string(&manifest_key, text);
        } else {
            storage.remove_string(&manifest_key);
            storage.remove_string(&source_key);
        }
        self.dirty = false;
        Ok(())
    }
}
