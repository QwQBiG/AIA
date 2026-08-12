use ai_ex_domain::AppError;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ImageMediaType
{
    Png,
    Jpeg,
    WebP,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VisualFrame
{
    pub media_type: ImageMediaType,
    pub bytes: Vec<u8>,
}

impl VisualFrame
{
    pub fn detect(bytes: Vec<u8>) -> Result<Self, AppError>
    {
        let media_type = if bytes.starts_with(b"\x89PNG\r\n\x1a\n")
        {
            ImageMediaType::Png
        }
        else if bytes.starts_with(&[0xff, 0xd8, 0xff])
        {
            ImageMediaType::Jpeg
        }
        else if bytes.starts_with(b"RIFF") && bytes.get(8..12) == Some(b"WEBP")
        {
            ImageMediaType::WebP
        }
        else
        {
            return Err(AppError::protocol("unsupported vision image signature"));
        };
        Self::new(media_type, bytes)
    }

    pub fn new(media_type: ImageMediaType, bytes: Vec<u8>) -> Result<Self, AppError>
    {
        if bytes.is_empty() || bytes.len() > 32 * 1024 * 1024
        {
            return Err(AppError::configuration("vision image size is invalid"));
        }
        let signature_valid = match media_type
        {
            ImageMediaType::Png => bytes.starts_with(b"\x89PNG\r\n\x1a\n"),
            ImageMediaType::Jpeg => bytes.starts_with(&[0xff, 0xd8, 0xff]),
            ImageMediaType::WebP =>
            {
                bytes.starts_with(b"RIFF") && bytes.get(8..12) == Some(b"WEBP")
            }
        };
        if !signature_valid
        {
            return Err(AppError::protocol("vision image signature does not match media type"));
        }
        Ok(Self { media_type, bytes })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VisionRequest
{
    pub prompt: String,
    pub frame: VisualFrame,
}

impl VisionRequest
{
    pub fn new(prompt: impl Into<String>, frame: VisualFrame) -> Result<Self, AppError>
    {
        let prompt = prompt.into();
        if prompt.trim().is_empty() || prompt.chars().count() > 8_192
        {
            return Err(AppError::configuration("vision prompt length is invalid"));
        }
        Ok(Self { prompt, frame })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VisionObservation
{
    pub model: String,
    pub text: String,
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn validates_image_signature()
    {
        assert!(VisualFrame::new(
            ImageMediaType::Png,
            b"\x89PNG\r\n\x1a\ncontent".to_vec(),
        )
        .is_ok());
        assert!(VisualFrame::new(ImageMediaType::Png, b"not-png".to_vec()).is_err());
    }

    #[test]
    fn detects_supported_media_without_trusting_extension()
    {
        let frame = VisualFrame::detect(b"RIFFsizeWEBPcontent".to_vec())
            .expect("WebP frame");

        assert_eq!(frame.media_type, ImageMediaType::WebP);
        assert!(VisualFrame::detect(b"GIF89a".to_vec()).is_err());
    }

    #[test]
    fn rejects_empty_prompt()
    {
        let frame = VisualFrame::new(
            ImageMediaType::Jpeg,
            vec![0xff, 0xd8, 0xff, 0x00],
        )
        .expect("JPEG frame");

        assert!(VisionRequest::new(" ", frame).is_err());
    }
}
