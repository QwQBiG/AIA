use ai_ex_ui_model::{PresentationState, UiState};
use eframe::egui;

pub fn show(ui: &mut egui::Ui, state: &UiState)
{
    let Some(text) = PresentationState::subtitle(state) else
    {
        return;
    };
    let playback = &state.runtime.playback;
    ui.group(|ui|
    {
        ui.weak("正在说");
        egui::ScrollArea::vertical().id_salt("playing_sentence").max_height(72.0).show(ui, |ui|
        {
            ui.label(text);
        });
        if playback.duration_ms > 0
        {
            let progress = (playback.position_ms as f64 / playback.duration_ms as f64).clamp(0.0, 1.0) as f32;
            ui.add(egui::ProgressBar::new(progress).desired_width(ui.available_width()).show_percentage());
        }
    });
}

#[cfg(test)]
mod tests
{
    use super::*;
    use ai_ex_domain::{Emotion, SpeechPlaybackSnapshot};
    use ai_ex_ui_model::ConnectionState;

    #[test]
    fn subtitle_panel_renders_playing_sentence_and_disappears_offline()
    {
        let mut state = UiState::new(8).unwrap();
        state.connection = ConnectionState::Connected;
        state.runtime.playback = SpeechPlaybackSnapshot {
            active: true, text: "This sentence is playing.".to_owned(), emotion: Some(Emotion::Happy),
            position_ms: 200, duration_ms: 1000, ..Default::default()
        };
        let context = egui::Context::default();
        for connected in [true, false]
        {
            state.connection = if connected { ConnectionState::Connected } else { ConnectionState::Disconnected };
            let output = context.run_ui(egui::RawInput::default(), |ui| show(ui, &state));
            let mut texts = Vec::new();
            for shape in &output.shapes
            {
                if let egui::epaint::Shape::Text(text) = &shape.shape
                {
                    texts.push(text.galley.job.text.as_str());
                }
            }
            assert_eq!(texts.contains(&"This sentence is playing."), connected);
            for primitive in context.tessellate(output.shapes, output.pixels_per_point)
            {
                if let egui::epaint::Primitive::Mesh(mesh) = primitive.primitive
                {
                    assert!(mesh.is_valid());
                }
            }
        }
    }
}
