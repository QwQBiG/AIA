use super::{AnimationFrame, Color32, Portrait};

pub(super) fn draw(p: &Portrait<'_>, frame: AnimationFrame) {
    let skin = Color32::from_rgb(250, 218, 200);
    let hair = p.tint(Color32::from_rgb(34, 36, 51), 0.12);
    let highlight = p.tint(Color32::from_rgb(65, 67, 87), 0.18);
    let ink = Color32::from_rgb(55, 45, 54);
    for x in [-44.0, 44.0] {
        p.ellipse(x, 100.0, 6.0, 10.0, Color32::from_rgb(232, 184, 167));
    }
    p.polygon(
        &[
            (0.0, 34.0),
            (25.0, 39.0),
            (41.0, 58.0),
            (45.0, 81.0),
            (41.0, 111.0),
            (30.0, 130.0),
            (13.0, 142.0),
            (0.0, 146.0),
            (-13.0, 142.0),
            (-30.0, 130.0),
            (-41.0, 111.0),
            (-45.0, 81.0),
            (-41.0, 58.0),
            (-25.0, 39.0),
        ],
        skin,
    );
    p.polygon(
        &[(35.0, 74.0), (45.0, 81.0), (41.0, 111.0), (31.0, 115.0)],
        Color32::from_rgb(240, 201, 183),
    );
    p.polygon(
        &[(31.0, 115.0), (41.0, 111.0), (30.0, 130.0), (13.0, 142.0)],
        Color32::from_rgb(240, 201, 183),
    );
    p.polygon(
        &[
            (-35.0, 32.0),
            (-5.0, 19.0),
            (16.0, 27.0),
            (-3.0, 68.0),
            (-39.0, 84.0),
            (-46.0, 67.0),
        ],
        hair,
    );
    p.polygon(
        &[
            (11.0, 29.0),
            (43.0, 42.0),
            (52.0, 80.0),
            (38.0, 71.0),
            (22.0, 54.0),
        ],
        hair,
    );
    p.polygon(
        &[(-53.0, 62.0), (-39.0, 77.0), (-36.0, 119.0), (-48.0, 141.0)],
        hair,
    );
    p.polygon(
        &[(49.0, 64.0), (54.0, 102.0), (36.0, 127.0), (41.0, 79.0)],
        hair,
    );
    p.line(
        &[(-36.0, 50.0), (-24.0, 37.0), (-10.0, 33.0)],
        3.0,
        highlight,
    );
    p.line(&[(25.0, 38.0), (35.0, 46.0), (41.0, 58.0)], 2.5, highlight);
    p.line(&[(-50.0, 92.0), (-47.0, 114.0)], 1.5, highlight);
    p.line(&[(40.0, 63.0), (50.0, 67.0)], 3.5, p.accent);
    p.line(
        &[(40.0, 68.0), (49.0, 72.0)],
        2.0,
        p.tint(Color32::WHITE, 0.35),
    );

    for x in [-19.0_f32, 19.0] {
        eye(p, x, frame, ink);
        let slope = x.signum() * frame.expression.brow_slant * 3.0;
        let lift = frame.expression.brow_raise * -4.0;
        p.line(
            &[
                (x - 9.0, 80.0 - slope + lift),
                (x, 78.0 + lift),
                (x + 9.0, 80.0 + slope + lift),
            ],
            1.8,
            hair,
        );
    }
    p.line(
        &[(1.0, 103.0), (3.0, 112.0), (-1.0, 114.0)],
        1.1,
        Color32::from_rgb(211, 161, 146),
    );
    let mouth_open = frame.mouth_open.clamp(0.0, 1.0);
    if mouth_open > 0.05 {
        let height = mouth_open * 7.0;
        p.ellipse(
            0.0,
            126.0,
            5.0 + mouth_open * 2.5,
            height,
            Color32::from_rgb(112, 58, 66),
        );
        if mouth_open > 0.35 {
            p.rounded_rect(
                (-3.5, 125.0 - height),
                (3.5, 127.0 - height),
                0.5,
                Color32::from_rgba_unmultiplied(
                    255,
                    238,
                    227,
                    ((mouth_open - 0.35).min(0.25) * 1020.0).round() as u8,
                ),
            );
        }
    } else {
        let bend = frame.expression.mouth_curve * 3.5;
        p.line(
            &[
                (-7.0, 126.0),
                (-3.5, 126.0 + bend * 0.75),
                (0.0, 126.0 + bend),
                (3.5, 126.0 + bend * 0.75),
                (7.0, 126.0),
            ],
            1.4,
            Color32::from_rgb(155, 92, 93),
        );
    }
    if frame.expression.blush > 0.0 {
        for x in [-29.0, 29.0] {
            p.ellipse(
                x,
                111.0,
                6.0,
                2.8,
                Color32::from_rgba_unmultiplied(
                    222,
                    129,
                    131,
                    (95.0 * frame.expression.blush.clamp(0.0, 1.0)).round() as u8,
                ),
            );
        }
    }
}

fn eye(p: &Portrait<'_>, x: f32, frame: AnimationFrame, ink: Color32) {
    let openness = frame.eyes_open.clamp(0.0, 1.0);
    if openness < 0.15 {
        p.line(&[(x - 10.0, 94.0), (x, 96.0), (x + 10.0, 94.0)], 1.8, ink);
        return;
    }
    let height = (5.5 + frame.expression.eye_widen * 1.5) * openness;
    p.ellipse(x, 95.0, 10.0, height, Color32::from_rgb(255, 249, 242));
    let gaze = frame.gaze_x.clamp(-1.0, 1.0) * 2.5;
    p.ellipse(
        x + gaze,
        95.0,
        4.4,
        height * 0.94,
        p.tint(Color32::from_rgb(61, 83, 100), 0.28),
    );
    p.ellipse(x + gaze, 95.0, 2.0, height * 0.8, ink);
    p.ellipse(
        x + gaze - 1.2,
        95.0 - height * 0.35,
        1.1,
        1.1 * openness,
        Color32::WHITE,
    );
    p.line(
        &[
            (x - 10.0, 94.0),
            (x - 5.0, 95.0 - height),
            (x + 3.0, 95.0 - height),
            (x + 10.0, 94.0),
        ],
        1.7,
        ink,
    );
    p.line(
        &[
            (x - 7.0, 96.0 + height * 0.7),
            (x + 5.0, 96.0 + height * 0.7),
        ],
        0.7,
        Color32::from_rgb(193, 140, 128),
    );
}
