use std::collections::BTreeSet;

pub use ai_ex_domain::MemoryEntry as MemoryRecord;

pub fn default_profile() -> String {
    "default".to_owned()
}

pub fn searchable_text(record: &MemoryRecord) -> String {
    format!("{} {}", record.user_text, record.assistant_text)
}

pub fn relevance(record: &MemoryRecord, query: &str) -> usize {
    let query_terms = terms(query);
    let document_terms = terms(&searchable_text(record));
    query_terms.intersection(&document_terms).count()
}

fn terms(text: &str) -> BTreeSet<String> {
    let lowercase = text.to_lowercase();
    let mut result: BTreeSet<String> = lowercase
        .split(|character: char| !character.is_alphanumeric())
        .filter(|term| !term.is_empty())
        .map(str::to_owned)
        .collect();
    for character in lowercase
        .chars()
        .filter(|character| !character.is_whitespace())
    {
        if !character.is_ascii_punctuation() {
            result.insert(character.to_string());
        }
    }
    result
}
