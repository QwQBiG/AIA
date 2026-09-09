use eframe::egui::{self, Color32, Rect, TextureId, epaint::Vertex, pos2, vec2};

#[derive(Clone, Copy)]
pub(super) struct Patch {
    bounds: [f32; 4],
    feather: [f32; 2],
}

// Coordinates were calibrated against the approved OC master and its matching
// eye/mouth edits. The right-eye edge stops above the identifying cheek mole.
pub(super) const LEFT_EYE: Patch = Patch {
    bounds: [0.406, 0.091, 0.464, 0.1165],
    feather: [0.004, 0.003],
};
pub(super) const RIGHT_EYE: Patch = Patch {
    bounds: [0.487, 0.106, 0.541, 0.1285],
    feather: [0.004, 0.0025],
};
pub(super) const MOUTH: Patch = Patch {
    bounds: [0.444, 0.133, 0.489, 0.156],
    feather: [0.0045, 0.003],
};

pub(super) fn draw(
    painter: &egui::Painter,
    texture: TextureId,
    target: Rect,
    uv: Rect,
    patch: Patch,
) {
    painter.add(mesh(texture, target, uv, patch));
}

pub(super) fn mesh(texture: TextureId, target: Rect, uv: Rect, patch: Patch) -> egui::Mesh {
    let [left, top, right, bottom] = patch.bounds;
    let outer = Rect::from_min_max(pos2(left, top), pos2(right, bottom));
    let inner = outer.shrink2(vec2(patch.feather[0], patch.feather[1]));
    let mut mesh = egui::Mesh::with_texture(texture);
    for (ring, color) in [(inner, Color32::WHITE), (outer, Color32::TRANSPARENT)] {
        for point in [
            ring.left_top(),
            ring.right_top(),
            ring.right_bottom(),
            ring.left_bottom(),
        ] {
            mesh.vertices.push(Vertex {
                pos: target.min + (point - uv.min) / uv.size() * target.size(),
                uv: point,
                color,
            });
        }
    }
    mesh.indices.extend_from_slice(&[0, 1, 2, 0, 2, 3]);
    for index in 0..4 {
        let next = (index + 1) % 4;
        mesh.indices
            .extend_from_slice(&[index, next, index + 4, next, next + 4, index + 4]);
    }
    mesh
}
