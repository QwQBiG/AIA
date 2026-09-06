use ai_ex_config::character::CharacterManifest;
use ai_ex_domain::AppError;
use uuid::Uuid;

#[path = "character_library_storage.rs"]
mod storage;

#[path = "character_library_ui.rs"]
mod view;
pub use view::LibraryDraft;

#[cfg(test)]
#[path = "character_library_tests.rs"]
mod tests;

const MAX_ENTRIES: usize = 32;
const MAX_BYTES: usize = 2 * 1024 * 1024;
const STORAGE_KEY: &str = "character.library.v1";

#[derive(Clone)]
pub struct LibraryEntry
{
    pub id: Uuid,
    pub character: CharacterManifest,
    pub source: String,
}

pub struct CharacterLibrary
{
    pub entries: Vec<LibraryEntry>,
    pub filter: String,
    pub feedback: Option<String>,
    pub dirty: bool,
    pub available: bool,
    removed: Option<(usize, LibraryEntry)>,
    original: Option<String>,
}

impl CharacterLibrary
{
    pub fn remember(&mut self, character: CharacterManifest, source: String) -> Result<(), AppError>
    {
        character.to_toml()?;
        if let Some(existing) = self.entries.iter().find(|entry| same_version(&entry.character, &character))
        {
            if existing.character == character { return Ok(()); }
            return Err(failure("this identity and revision already contain different settings; increase the revision before saving"));
        }
        let mut entries = self.entries.clone();
        entries.push(LibraryEntry { id: Uuid::new_v4(), character, source });
        self.commit(entries)
    }

    pub fn remove(&mut self, index: usize) -> Result<(), AppError>
    {
        if index >= self.entries.len() { return Err(failure("selection is no longer available")); }
        let mut entries = self.entries.clone();
        let removed = entries.remove(index);
        self.commit(entries)?;
        self.removed = Some((index, removed));
        Ok(())
    }

    pub fn undo_remove(&mut self) -> Result<(), AppError>
    {
        let Some((index, entry)) = self.removed.clone() else { return Ok(()); };
        let mut entries = self.entries.clone();
        entries.insert(index.min(entries.len()), entry);
        self.commit(entries)?;
        self.removed = None;
        Ok(())
    }

    pub fn can_undo(&self) -> bool { self.removed.is_some() }

    fn commit(&mut self, entries: Vec<LibraryEntry>) -> Result<(), AppError>
    {
        storage::encode(&entries)?;
        self.entries = entries;
        self.dirty = true;
        Ok(())
    }
}

fn same_version(first: &CharacterManifest, second: &CharacterManifest) -> bool
{
    first.persona.profile_id == second.persona.profile_id && first.persona.revision == second.persona.revision
}

fn failure(error: impl std::fmt::Display) -> AppError
{
    AppError::configuration(format!("character library: {error}"))
}
