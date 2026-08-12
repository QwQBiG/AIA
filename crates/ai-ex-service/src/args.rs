use std::path::PathBuf;

use ai_ex_domain::AppError;

#[derive(Debug, PartialEq, Eq)]
pub struct Args
{
    pub config: PathBuf,
    pub check: bool,
    pub prompt: Option<String>,
    pub vision_image: Option<PathBuf>,
    pub vision_prompt: Option<String>,
}

impl Args
{
    pub fn parse(values: impl IntoIterator<Item = String>) -> Result<Self, AppError>
    {
        let mut config = PathBuf::from("config/ai-ex.example.toml");
        let mut check = false;
        let mut prompt = None;
        let mut vision_image = None;
        let mut vision_prompt = None;
        let mut values = values.into_iter();
        while let Some(value) = values.next()
        {
            match value.as_str()
            {
                "--config" =>
                {
                    let path = values.next().ok_or_else(|| {
                        AppError::configuration("--config requires a path")
                    })?;
                    config = PathBuf::from(path);
                }
                "--check" => check = true,
                "--prompt" =>
                {
                    prompt = Some(values.next().ok_or_else(|| {
                        AppError::configuration("--prompt requires text")
                    })?);
                }
                "--vision-image" =>
                {
                    let path = values.next().ok_or_else(|| {
                        AppError::configuration("--vision-image requires a path")
                    })?;
                    vision_image = Some(PathBuf::from(path));
                }
                "--vision-prompt" =>
                {
                    vision_prompt = Some(values.next().ok_or_else(|| {
                        AppError::configuration("--vision-prompt requires text")
                    })?);
                }
                "--help" | "-h" =>
                {
                    return Err(AppError::configuration(
                        "usage: ai-ex-service [--config PATH] [--check | --prompt TEXT | \
                         --vision-image PATH --vision-prompt TEXT]",
                    ));
                }
                _ =>
                {
                    return Err(AppError::configuration(format!(
                        "unknown argument: {value}"
                    )));
                }
            }
        }
        if vision_image.is_some() != vision_prompt.is_some()
        {
            return Err(AppError::configuration(
                "--vision-image and --vision-prompt must be used together",
            ));
        }
        let selected_modes = usize::from(check)
            + usize::from(prompt.is_some())
            + usize::from(vision_image.is_some());
        if selected_modes > 1
        {
            return Err(AppError::configuration(
                "--check, --prompt, and vision analysis modes are mutually exclusive",
            ));
        }
        Ok(Self {
            config,
            check,
            prompt,
            vision_image,
            vision_prompt,
        })
    }
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn rejects_missing_prompt_value()
    {
        assert!(Args::parse(["--prompt".to_owned()]).is_err());
    }

    #[test]
    fn accepts_config_and_check()
    {
        let args = Args::parse([
            "--config".to_owned(),
            "custom.toml".to_owned(),
            "--check".to_owned(),
        ])
        .expect("arguments parse");
        assert_eq!(args.config, PathBuf::from("custom.toml"));
        assert!(args.check);
    }

    #[test]
    fn accepts_complete_vision_mode()
    {
        let args = Args::parse([
            "--vision-image".to_owned(),
            "screen.png".to_owned(),
            "--vision-prompt".to_owned(),
            "Describe the UI".to_owned(),
        ])
        .expect("vision arguments parse");

        assert_eq!(args.vision_image, Some(PathBuf::from("screen.png")));
        assert_eq!(args.vision_prompt.as_deref(), Some("Describe the UI"));
    }

    #[test]
    fn rejects_partial_or_conflicting_modes()
    {
        assert!(Args::parse([
            "--vision-image".to_owned(),
            "screen.png".to_owned(),
        ])
        .is_err());
        assert!(Args::parse([
            "--check".to_owned(),
            "--prompt".to_owned(),
            "hello".to_owned(),
        ])
        .is_err());
    }
}
