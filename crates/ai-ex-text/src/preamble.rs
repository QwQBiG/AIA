use ai_ex_domain::Emotion;

#[derive(Debug, Default, PartialEq, Eq)]
pub struct PreambleOutput
{
    pub emotion: Option<Emotion>,
    pub text: String,
}

#[derive(Debug, Default)]
pub struct ResponsePreamble
{
    buffer: String,
    resolved: bool,
}

impl ResponsePreamble
{
    pub fn push(&mut self, chunk: &str) -> PreambleOutput
    {
        if self.resolved
        {
            return PreambleOutput {
                emotion: None,
                text: chunk.to_owned(),
            };
        }
        self.buffer.push_str(chunk);
        let trimmed = self.buffer.trim_start();
        if trimmed.is_empty()
        {
            return PreambleOutput::default();
        }
        if !trimmed.starts_with('[')
        {
            return self.resolve_raw();
        }
        if let Some(end) = trimmed.find(']')
        {
            let emotion = Emotion::parse(&trimmed[1..end]);
            if let Some(emotion) = emotion
            {
                let text = trimmed[end + 1..].trim_start().to_owned();
                self.buffer.clear();
                self.resolved = true;
                return PreambleOutput {
                    emotion: Some(emotion),
                    text,
                };
            }
            return self.resolve_raw();
        }
        if trimmed.chars().count() > 24
        {
            return self.resolve_raw();
        }
        PreambleOutput::default()
    }

    pub fn finish(&mut self) -> String
    {
        if self.resolved
        {
            return String::new();
        }
        self.resolved = true;
        std::mem::take(&mut self.buffer)
    }

    fn resolve_raw(&mut self) -> PreambleOutput
    {
        self.resolved = true;
        PreambleOutput {
            emotion: None,
            text: std::mem::take(&mut self.buffer),
        }
    }
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn extracts_tag_split_across_chunks()
    {
        let mut parser = ResponsePreamble::default();
        assert_eq!(parser.push(" [hap"), PreambleOutput::default());
        assert_eq!(
            parser.push("py] hello"),
            PreambleOutput {
                emotion: Some(Emotion::Happy),
                text: "hello".to_owned(),
            },
        );
        assert_eq!(parser.push(" world").text, " world");
    }

    #[test]
    fn preserves_invalid_or_unfinished_tags()
    {
        let mut invalid = ResponsePreamble::default();
        assert_eq!(invalid.push("[excited] hello").text, "[excited] hello");

        let mut unfinished = ResponsePreamble::default();
        assert!(unfinished.push("[happy").text.is_empty());
        assert_eq!(unfinished.finish(), "[happy");
    }
}
