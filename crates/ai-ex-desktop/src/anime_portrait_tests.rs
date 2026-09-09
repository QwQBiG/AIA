use super::*;
use ai_ex_domain::Emotion;
use egui::vec2;

fn speaking() -> PresentationState {
    PresentationState {
        connected: true,
        synchronized: true,
        activity: ConversationState::Speaking,
        emotion: Emotion::Happy,
        mouth_level: Some(850),
    }
}

#[test]
fn silence_and_every_stop_choose_a_closed_mouth_even_with_a_stale_frame() {
    let state = speaking();
    let stale = state.animate(1.0, false);
    assert_eq!(select_frame(state, stale, false), PortraitFrame::Speaking);
    for stop in 0..9 {
        let mut state = state;
        match stop {
            0 => state.mouth_level = Some(0),
            1 => state.connected = false,
            2 => state.synchronized = false,
            3 => state.activity = ConversationState::Interrupted,
            4 => state.activity = ConversationState::Stopped,
            5 => state.activity = ConversationState::Listening,
            6 => state.activity = ConversationState::Failed,
            7 => state.activity = ConversationState::Idle,
            8 => state.activity = ConversationState::Thinking,
            _ => unreachable!(),
        }
        assert_ne!(select_frame(state, stale, false), PortraitFrame::Speaking);
    }
    assert_eq!(select_frame(state, stale, true), PortraitFrame::Happy);
}

#[test]
fn blink_and_thinking_are_closed_mouth_poses_and_speech_has_priority() {
    let mut state = speaking();
    let mut frame = state.animate(1.0, false);
    frame.eyes_open = 0.0;
    assert_eq!(select_frame(state, frame, false), PortraitFrame::Speaking);
    state.mouth_level = Some(0);
    assert_eq!(select_frame(state, frame, false), PortraitFrame::Blink);
    state.activity = ConversationState::Thinking;
    state.emotion = Emotion::Neutral;
    frame.eyes_open = 1.0;
    assert_eq!(select_frame(state, frame, false), PortraitFrame::Thinking);
    assert_eq!(select_frame(state, frame, true), PortraitFrame::Idle);
}

#[test]
fn image_fit_preserves_ratio_and_breath_stays_inside_the_fixed_card() {
    let size = vec2(1024.0, 1536.0);
    for (width, height) in [(180.0, 320.0), (600.0, 480.0), (80.0, 60.0)] {
        let stage = Rect::from_min_size(egui::pos2(12.0, 20.0), vec2(width, height));
        for breath in [-1.0, 0.0, 1.0, f32::NAN, f32::INFINITY] {
            let target = portrait_rect(stage, size).unwrap();
            assert!((target.aspect_ratio() - size.x / size.y).abs() < 0.001);
            assert!(stage.contains_rect(target));
            let uv = portrait_uv(breath);
            assert!(Rect::from_min_max(egui::Pos2::ZERO, egui::pos2(1.0, 1.0)).contains_rect(uv));
            assert!((uv.aspect_ratio() - 1.0).abs() < 0.001);
        }
    }
    assert!(portrait_rect(Rect::NOTHING, size).is_none());
    assert!(portrait_rect(Rect::EVERYTHING, size).is_none());
    assert!(portrait_rect(Rect::ZERO, size).is_none());
}

#[test]
fn corrupt_embedded_data_is_an_error_without_a_panic() {
    assert!(decode(b"invalid png").is_err());
}

#[test]
fn embedded_frames_share_a_high_resolution_canvas_and_are_decoded_once() {
    let base = decoded(PortraitFrame::Idle).as_ref().unwrap();
    for frame in [
        PortraitFrame::Idle,
        PortraitFrame::Blink,
        PortraitFrame::Speaking,
        PortraitFrame::Thinking,
        PortraitFrame::Happy,
        PortraitFrame::Sad,
        PortraitFrame::Angry,
        PortraitFrame::Surprised,
    ] {
        let pixels = decoded(frame).as_ref().unwrap();
        assert_eq!(pixels.size, base.size, "{frame:?} canvas");
        assert!(pixels.size[0] >= 768 && pixels.size[1] >= 1024);
        let opaque = pixels
            .pixels
            .iter()
            .filter(|pixel| pixel.a() == 255)
            .count();
        assert!(opaque > pixels.pixels.len() / 10, "{frame:?} character");
        assert!(Arc::ptr_eq(pixels, decoded(frame).as_ref().unwrap()));
    }
}

#[test]
fn drawing_reuses_linear_textures_and_silence_replaces_the_speaking_image() {
    let context = egui::Context::default();
    let mut portrait = AnimePortrait::default();
    let mut state = speaking();
    let render = |portrait: &mut AnimePortrait, state: PresentationState| {
        context.run_ui(egui::RawInput::default(), |ui| {
            portrait
                .draw(
                    ui.painter(),
                    Rect::from_min_size(egui::Pos2::ZERO, vec2(320.0, 480.0)),
                    state,
                    state.animate(1.0, false),
                    false,
                    Color32::from_rgb(154, 133, 184),
                )
                .unwrap();
        })
    };
    let first = render(&mut portrait, state);
    let texture = portrait.textures[&PortraitFrame::Speaking].id();
    let upload = first
        .textures_delta
        .set
        .iter()
        .find(|(id, _)| *id == texture)
        .unwrap();
    assert_eq!(upload.1.options, egui::TextureOptions::LINEAR);
    let again = render(&mut portrait, state);
    assert!(
        again
            .textures_delta
            .set
            .iter()
            .all(|(id, _)| *id != texture)
    );
    assert_eq!(portrait.textures.len(), 3);
    state.mouth_level = Some(0);
    state.emotion = Emotion::Neutral;
    let silent = render(&mut portrait, state);
    let idle = portrait.textures[&PortraitFrame::Idle].id();
    assert_ne!(idle, texture);
    assert_eq!(portrait.selected, Some(PortraitFrame::Idle));
    let primitives = context.tessellate(silent.shapes, silent.pixels_per_point);
    assert!(primitives.iter().any(|primitive| {
        matches!(&primitive.primitive, egui::epaint::Primitive::Mesh(mesh) if mesh.texture_id == idle)
    }));
    assert!(primitives.iter().all(|primitive| {
        !matches!(&primitive.primitive, egui::epaint::Primitive::Mesh(mesh) if mesh.texture_id == texture)
    }));
}

#[test]
fn emotion_can_speak_and_blink_without_replacing_the_body_or_eyebrows() {
    let state = speaking();
    let mut frame = state.animate(1.0, false);
    frame.eyes_open = 0.0;
    let layers = select_layers(state, frame, false);
    assert_eq!(layers.face, PortraitFrame::Happy);
    assert!(layers.blinking && layers.speaking);
    let still = select_layers(state, frame, true);
    assert_eq!(still.face, PortraitFrame::Happy);
    assert!(!still.blinking && !still.speaking);
}

#[test]
fn facial_meshes_are_feathered_and_never_cover_the_body() {
    let target = Rect::from_min_size(egui::pos2(20.0, 30.0), vec2(320.0, 480.0));
    for breath in [-1.0, 0.0, 1.0] {
        for patch in [
            patches::FACE,
            patches::LEFT_EYE,
            patches::RIGHT_EYE,
            patches::MOUTH,
        ] {
            let mesh = patches::mesh(
                egui::TextureId::Managed(3),
                target,
                portrait_uv(breath),
                patch,
                1.0,
            );
            assert!(mesh.is_valid());
            assert_eq!(mesh.vertices.len(), 8);
            assert_eq!(mesh.indices.len(), 30);
            assert!(mesh.vertices[..4].iter().all(|v| v.color == Color32::WHITE));
            assert!(
                mesh.vertices[4..]
                    .iter()
                    .all(|v| v.color == Color32::TRANSPARENT)
            );
            assert!(
                mesh.vertices
                    .iter()
                    .all(|v| target.contains(v.pos)
                        && v.pos.y < target.top() + target.height() * 0.36)
            );
        }
    }
}
