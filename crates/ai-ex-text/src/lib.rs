#![forbid(unsafe_code)]

mod preamble;

pub use preamble::{PreambleOutput, ResponsePreamble};

#[derive(Debug, Default)]
pub struct SentenceBuffer
{
    buffer: String,
}

impl SentenceBuffer
{
    pub fn push(&mut self, chunk: &str) -> Vec<String>
    {
        self.buffer.push_str(chunk);
        let mut result = Vec::new();
        let mut start = 0;
        let mut consumed = 0;
        for (index, character) in self.buffer.char_indices()
        {
            if is_sentence_boundary(character)
            {
                let end = index + character.len_utf8();
                let sentence = self.buffer[start..end].trim();
                if !sentence.is_empty()
                {
                    result.push(sentence.to_owned());
                }
                start = end;
                consumed = end;
            }
        }
        if consumed > 0
        {
            self.buffer.drain(..consumed);
        }
        result
    }

    pub fn finish(&mut self) -> Option<String>
    {
        let trailing = self.buffer.trim().to_owned();
        self.buffer.clear();
        if trailing.is_empty()
        {
            None
        }
        else
        {
            Some(trailing)
        }
    }

    pub fn clear(&mut self)
    {
        self.buffer.clear();
    }
}

pub fn clean_for_speech(input: &str) -> String
{
    let mut result = String::with_capacity(input.len());
    let mut inside_code = false;
    for character in input.chars()
    {
        if character == '`'
        {
            inside_code = !inside_code;
            continue;
        }
        if inside_code
        {
            continue;
        }
        if matches!(character, '*' | '_' | '#' | '>' | '~')
        {
            continue;
        }
        if !character.is_control() || matches!(character, '\n' | '\t')
        {
            result.push(character);
        }
    }
    result.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn is_sentence_boundary(character: char) -> bool
{
    matches!(character, '。' | '！' | '？' | '.' | '!' | '?' | '\n')
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn preserves_partial_utf8_and_emits_sentences_once()
    {
        let mut buffer = SentenceBuffer::default();
        assert!(buffer.push("你好").is_empty());
        assert_eq!(buffer.push("。Next!"), vec!["你好。", "Next!"]);
    }

    #[test]
    fn removes_markdown_and_inline_code()
    {
        assert_eq!(clean_for_speech("**Hello** `ignored()` world"), "Hello world");
    }
}
