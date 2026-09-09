use super::*;
use ai_ex_domain::Emotion;
use egui::{pos2, vec2};

fn speaking() -> PresentationState {
    PresentationState {
        connected: true,
        synchronized: true,
        activity: ConversationState::Speaking,
        emotion: Emotion::Neutral,
        mouth_level: Some(900),
    }
}

#[test]
fn stale_mouth_closes_on_silence_and_every_stop_without_cross_character_frames() {
    let state = speaking();
    let mut frame = state.animate(1.0, false);
    frame.eyes_open = 0.0;
    assert_eq!(selected_layers(state, frame, false), [true, true]);
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
        let layers = selected_layers(state, frame, false);
        assert!(!layers[1], "stop case {stop}");
        if [0, 1, 2, 3, 4, 6].contains(&stop) {
            assert!(!layers[0], "stopped blink {stop}");
            assert!(!motion_allowed(state, false));
        }
    }
    for emotion in [
        Emotion::Happy,
        Emotion::Sad,
        Emotion::Angry,
        Emotion::Surprised,
    ] {
        let state = PresentationState { emotion, ..state };
        assert_eq!(selected_layers(state, frame, true), [false, false]);
        assert_eq!(selected_layers(state, frame, false), [true, true]);
    }
}

#[test]
fn approved_canvas_is_shared_by_all_renderer_instances() {
    let base = assets::decoded(Frame::Portrait).as_ref().unwrap();
    for frame in [Frame::Portrait, Frame::Blink, Frame::Speaking] {
        let pixels = assets::decoded(frame).as_ref().unwrap();
        assert_eq!(pixels.size, [1024, 1536]);
        assert!(std::sync::Arc::ptr_eq(
            pixels,
            assets::decoded(frame).as_ref().unwrap()
        ));
        if frame != Frame::Portrait {
            assert!(!std::sync::Arc::ptr_eq(base, pixels));
        }
    }
}

#[test]
fn portrait_keeps_hair_and_full_body_keeps_the_complete_approved_canvas() {
    let unit = Rect::from_min_max(egui::Pos2::ZERO, pos2(1.0, 1.0));
    for breath in [None, Some(-1.0), Some(0.0), Some(1.0), Some(f32::NAN)] {
        let portrait = framing_uv(BuiltinFraming::Portrait, breath);
        assert!(unit.contains_rect(portrait));
        assert!(portrait.contains(pos2(0.5, 8.0 / 1536.0)), "hair top");
        assert!(portrait.contains(pos2(0.26, 0.12)), "left hair");
        assert!(portrait.contains(pos2(0.71, 0.13)), "right hair");
        assert_eq!(framing_uv(BuiltinFraming::FullBody, breath), unit);
        for (width, height) in [(320.0, 440.0), (160.0, 100.0), (800.0, 300.0)] {
            let stage = Rect::from_min_size(pos2(20.0, 30.0), vec2(width, height));
            let size = vec2(1024.0, 1536.0) * portrait.size();
            let fitted = fitted_rect(stage, size).unwrap();
            assert!(stage.contains_rect(fitted));
            assert!((fitted.aspect_ratio() - size.x / size.y).abs() < 0.001);
        }
    }
    assert!(fitted_rect(Rect::ZERO, vec2(1024.0, 1536.0)).is_none());
    assert!(fitted_rect(Rect::EVERYTHING, vec2(1024.0, 1536.0)).is_none());
}

#[test]
fn eye_and_mouth_patches_are_calibrated_to_this_oc_and_leave_the_body_untouched() {
    let target = Rect::from_min_size(pos2(20.0, 30.0), vec2(320.0, 480.0));
    for framing in [BuiltinFraming::Portrait, BuiltinFraming::FullBody] {
        let uv = framing_uv(framing, Some(1.0));
        for patch in [patches::LEFT_EYE, patches::RIGHT_EYE, patches::MOUTH] {
            let mesh = patches::mesh(egui::TextureId::Managed(3), target, uv, patch);
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
                    .all(|v| target.contains(v.pos) && v.uv.y < 0.17)
            );
            let bounds = Rect::from_min_max(mesh.vertices[4].uv, mesh.vertices[6].uv);
            assert!(
                !bounds.contains(pos2(0.531, 0.132)),
                "cheek mole must stay visible"
            );
        }
    }
}

#[test]
fn rendering_reuses_linear_textures_and_removes_speech_without_replacing_the_body() {
    let context = egui::Context::default();
    let mut portrait = OcPortrait::default();
    let state = speaking();
    let mut frame = state.animate(1.0, false);
    frame.eyes_open = 0.0;
    let render = |portrait: &mut OcPortrait, state, framing| {
        context.run_ui(egui::RawInput::default(), |ui| {
            portrait
                .draw(
                    ui.painter(),
                    Rect::from_min_size(egui::Pos2::ZERO, vec2(320.0, 480.0)),
                    state,
                    frame,
                    Options {
                        framing,
                        reduced_motion: false,
                        accent: Color32::LIGHT_BLUE,
                    },
                )
                .unwrap();
        })
    };
    let first = render(&mut portrait, state, BuiltinFraming::Portrait);
    assert_eq!(portrait.visible_layers, [true, true]);
    assert_eq!(portrait.textures.len(), 3);
    for texture in portrait.textures.values() {
        let upload = first
            .textures_delta
            .set
            .iter()
            .find(|(id, _)| *id == texture.id())
            .unwrap();
        assert_eq!(upload.1.options, egui::TextureOptions::LINEAR);
    }
    let again = render(&mut portrait, state, BuiltinFraming::FullBody);
    for texture in portrait.textures.values() {
        assert!(
            again
                .textures_delta
                .set
                .iter()
                .all(|(id, _)| *id != texture.id())
        );
    }
    let silent = render(
        &mut portrait,
        PresentationState {
            mouth_level: Some(0),
            ..state
        },
        BuiltinFraming::Portrait,
    );
    assert_eq!(portrait.visible_layers, [false, false]);
    let base = portrait.textures[&Frame::Portrait].id();
    let mouth = portrait.textures[&Frame::Speaking].id();
    let primitives = context.tessellate(silent.shapes, silent.pixels_per_point);
    assert!(primitives.iter().any(
        |p| matches!(&p.primitive, egui::epaint::Primitive::Mesh(mesh) if mesh.texture_id == base)
    ));
    assert!(primitives.iter().all(
        |p| !matches!(&p.primitive, egui::epaint::Primitive::Mesh(mesh) if mesh.texture_id == mouth)
    ));
}
