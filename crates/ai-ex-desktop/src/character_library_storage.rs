use super::*;
use serde_json::{Value, json};

pub(super) fn encode(entries: &[LibraryEntry]) -> Result<String, AppError>
{
    if entries.len() > MAX_ENTRIES { return Err(failure("the library supports at most 32 saved versions")); }
    let mut values = Vec::new();
    for (index, entry) in entries.iter().enumerate()
    {
        if entry.source.chars().count() > 2048 || entries[..index].iter().any(|other| other.id == entry.id || same_version(&other.character, &entry.character))
        {
            return Err(failure("duplicate identity/revision or invalid source description"));
        }
        values.push(json!({"id": entry.id.to_string(), "character": entry.character.to_toml()?, "source": entry.source}));
    }
    let text = json!({"schema_version": 1, "entries": values}).to_string();
    if text.len() > MAX_BYTES { return Err(failure("the library exceeds 2 MiB")); }
    Ok(text)
}

fn decode(text: &str) -> Result<Vec<LibraryEntry>, AppError>
{
    if text.len() > MAX_BYTES { return Err(failure("the library exceeds 2 MiB")); }
    let value: Value = serde_json::from_str(text).map_err(failure)?;
    if value["schema_version"].as_u64() != Some(1) || value.as_object().is_none_or(|object| object.len() != 2)
    {
        return Err(failure("unsupported library schema"));
    }
    let values = value["entries"].as_array().ok_or_else(|| failure("missing library entries"))?;
    if values.len() > MAX_ENTRIES { return Err(failure("too many library entries")); }
    let mut entries = Vec::new();
    for value in values
    {
        if value.as_object().is_none_or(|object| object.len() != 3) { return Err(failure("invalid library entry fields")); }
        let id = value["id"].as_str().ok_or_else(|| failure("missing entry ID"))?;
        let character = value["character"].as_str().ok_or_else(|| failure("missing character snapshot"))?;
        let source = value["source"].as_str().ok_or_else(|| failure("missing source description"))?;
        entries.push(LibraryEntry { id: Uuid::parse_str(id).map_err(failure)?, character: CharacterManifest::parse(character)?, source: source.to_owned() });
    }
    encode(&entries)?;
    Ok(entries)
}

impl CharacterLibrary
{
    pub fn load(storage: Option<&dyn eframe::Storage>) -> Self
    {
        let original = storage.and_then(|storage| storage.get_string(STORAGE_KEY));
        let parsed = match original.as_deref()
        {
            Some(text) => decode(text),
            None => examples(),
        };
        let (entries, feedback, original) = match parsed
        {
            Ok(entries) => (entries, None, None),
            Err(error) => (Vec::new(), Some(format!("收藏读取失败；原数据保留，重新收藏时会先备份：{error}")), original),
        };
        Self { entries, filter: String::new(), feedback, dirty: false, available: storage.is_some(), removed: None, original }
    }

    pub fn save(&mut self, storage: &mut dyn eframe::Storage) -> Result<(), AppError>
    {
        if !self.dirty { return Ok(()); }
        let text = encode(&self.entries)?;
        if let Some(original) = self.original.take()
        {
            storage.set_string(&format!("character.library.recovery.{}", Uuid::new_v4()), original);
        }
        storage.set_string(STORAGE_KEY, text);
        self.dirty = false;
        Ok(())
    }
}

fn examples() -> Result<Vec<LibraryEntry>, AppError>
{
    [include_str!("../../../config/characters/companion.toml"), include_str!("../../../config/characters/host.toml")]
        .into_iter().enumerate().map(|(index, text)|
        {
            Ok(LibraryEntry { id: Uuid::from_u128(index as u128 + 1), character: CharacterManifest::parse(text)?, source: "AIex 内置示例".to_owned() })
        }).collect()
}
