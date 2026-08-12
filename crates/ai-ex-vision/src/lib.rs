#![forbid(unsafe_code)]

mod ollama;
mod types;

use ai_ex_domain::AppError;
use async_trait::async_trait;

pub use ollama::{OllamaVisionClient, OllamaVisionSettings};
pub use types::{ImageMediaType, VisionObservation, VisionRequest, VisualFrame};

#[async_trait]
pub trait VisionAnalyzerPort: Send
{
    async fn analyze(&mut self, request: VisionRequest) -> Result<VisionObservation, AppError>;
}
