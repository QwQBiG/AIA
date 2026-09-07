use super::*;
use crate::character_library::LibraryDraft;
use ai_ex_config::character::CharacterManifest;

impl DesktopApp {
    pub(super) fn character_draft(&self) -> CharacterManifest {
        let mut draft = CharacterManifest::from_persona(self.persona.clone());
        draft.author = self.character_files.author.clone();
        draft.license = self.character_files.license.clone();
        draft
    }

    pub(super) fn apply_library_draft(&mut self, selected: LibraryDraft) {
        self.character_files.author = selected.character.author.clone();
        self.character_files.license = selected.character.license.clone();
        self.character_files.draft_source = selected.source;
        self.character_files.baseline = Some(selected.character.clone());
        self.persona = selected.character.persona;
        self.taboos_editor = self.persona.taboos.join("\n");
        self.persona_dirty = true;
        self.pending_persona = None;
        self.confirm_persona = false;
    }

    pub(super) fn show_character_library(&mut self, ui: &mut egui::Ui) {
        let draft = self.character_draft();
        ui.label(format!(
            "当前角色：{} · v{}",
            self.active_persona.name, self.active_persona.revision
        ));
        ui.weak(format!(
            "当前来源：{}",
            if self.active_source.is_empty() {
                "等待服务同步"
            } else {
                &self.active_source
            }
        ));
        let modified = self
            .character_files
            .baseline
            .as_ref()
            .is_some_and(|baseline| baseline != &draft);
        ui.weak(format!(
            "草稿来源：{}{}",
            if self.character_files.draft_source.is_empty() {
                "手动角色设置"
            } else {
                &self.character_files.draft_source
            },
            if modified { "（已修改）" } else { "" }
        ));
        ui.add_enabled_ui(
            !self.persona_apply_pending
                && !self.confirm_persona
                && !self.character_files.is_loading(),
            |ui| {
                if let Some(selected) = self.character_library.show(
                    ui,
                    &self.active_persona,
                    &draft,
                    &self.character_files.draft_source,
                ) {
                    self.apply_library_draft(selected);
                }
            },
        );
    }

    pub(super) fn sync_character_draft_metadata(&mut self) {
        self.character_files.author = self.active_character.author.clone();
        self.character_files.license = self.active_character.license.clone();
        self.character_files.baseline = Some(self.active_character.clone());
        self.character_files.draft_source = self.active_source.clone();
    }

    pub(super) fn save_library(&mut self, storage: &mut dyn eframe::Storage) {
        if let Err(error) = self.character_library.save(storage) {
            self.character_library.feedback = Some(format!("收藏保存失败：{error}"));
        }
    }
}
