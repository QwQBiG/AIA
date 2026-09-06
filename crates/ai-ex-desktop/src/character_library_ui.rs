use super::*;
use ai_ex_domain::PersonaSnapshot;
use eframe::egui;

pub struct LibraryDraft
{
    pub character: CharacterManifest,
    pub source: String,
}

impl LibraryEntry
{
    pub fn draft(&self, independent: bool) -> LibraryDraft
    {
        let mut character = self.character.clone();
        if independent
        {
            character.persona.profile_id = format!("character.{}", Uuid::new_v4());
            character.persona.revision = 1;
            character.persona.name = format!("{} 的副本", character.persona.name.chars().take(100).collect::<String>());
        }
        LibraryDraft { source: format!("{}角色收藏：{} · v{}", if independent { "独立副本，基于" } else { "" }, self.character.persona.name, self.character.persona.revision), character }
    }
}

impl CharacterLibrary
{
    pub fn show(&mut self, ui: &mut egui::Ui, active: &PersonaSnapshot, draft: &CharacterManifest, source: &str) -> Option<LibraryDraft>
    {
        let mut selected = None;
        let mut remove = None;
        egui::CollapsingHeader::new("角色收藏（选择 / 新建）").default_open(true).show(ui, |ui|
        {
            ui.weak("收藏设定副本，选择后进入草稿；预览并确认才切换角色。相同档案 ID 继续使用同一份记忆。");
            ui.small(format!("{} / 32 份收藏；同一档案 ID 修改后，可增加版本号再收藏。", self.entries.len()));
            ui.horizontal_wrapped(|ui|
            {
                if ui.button("新建角色").clicked()
                {
                    selected = Some(LibraryDraft {
                        character: CharacterManifest::from_persona(PersonaSnapshot { profile_id: format!("character.{}", Uuid::new_v4()), revision: 1, name: "新伙伴".to_owned(), ..Default::default() }),
                        source: "新建草稿".to_owned(),
                    });
                }
                if ui.add_enabled(self.available, egui::Button::new("收藏当前草稿")).clicked()
                {
                    self.feedback = Some(match self.remember(draft.clone(), source.to_owned())
                    {
                        Ok(()) => "草稿已加入收藏；已有的相同设定会复用。".to_owned(),
                        Err(error) => format!("无法收藏：{error}"),
                    });
                }
                if ui.add_enabled(self.can_undo(), egui::Button::new("撤销移出")).clicked()
                {
                    self.feedback = Some(match self.undo_remove()
                    {
                        Ok(()) => "已恢复移出的收藏。".to_owned(),
                        Err(error) => error.to_string(),
                    });
                }
            });
            ui.add(egui::TextEdit::singleline(&mut self.filter).hint_text("搜索名称、档案 ID 或作者"));
            let filter = self.filter.to_lowercase();
            let mut shown = 0;
            egui::ScrollArea::vertical().id_salt("character_library").max_height(220.0).show(ui, |ui|
            {
                for (index, entry) in self.entries.iter().enumerate()
                {
                    let profile = &entry.character.persona;
                    if !format!("{} {} {}", profile.name, profile.profile_id, entry.character.author).to_lowercase().contains(&filter) { continue; }
                    shown += 1;
                    ui.push_id(entry.id, |ui|
                    {
                        ui.group(|ui|
                        {
                            ui.horizontal_wrapped(|ui|
                            {
                                ui.strong(format!("{} · v{}", profile.name, profile.revision));
                                if profile == active { ui.label("正在使用"); }
                                else if profile.profile_id == active.profile_id { ui.weak("同一角色的其他设定"); }
                                if ui.button("载入草稿").clicked() { selected = Some(entry.draft(false)); }
                                if ui.button("复制为独立角色").clicked() { selected = Some(entry.draft(true)); }
                                if ui.button("移出收藏").clicked() { remove = Some(index); }
                            });
                            ui.small(format!("{} · 作者：{}", profile.profile_id, entry.character.author));
                            ui.weak(format!("来源：{}", entry.source));
                        });
                    });
                }
            });
            if shown == 0 { ui.weak("没有匹配的角色。可以新建角色，或从角色包导入后收藏。"); }
            if !self.available { ui.weak("当前环境不能持久保存收藏，仍可载入内置示例。"); }
            if let Some(index) = remove
            {
                self.feedback = Some(match self.remove(index)
                {
                    Ok(()) => "已移出收藏；可以撤销，当前角色和记忆保持不变。".to_owned(),
                    Err(error) => error.to_string(),
                });
            }
            if let Some(feedback) = &self.feedback { ui.label(feedback); }
        });
        selected
    }
}
