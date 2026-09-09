use eframe::egui::{self, Color32, Rect, TextureHandle, TextureId, epaint::Vertex, pos2, vec2};

#[derive(Clone, Copy)]
pub(super) struct Patch {
    bounds: [f32; 4],
    feather: [f32; 2],
}

pub(super) const FACE: Patch = Patch {
    bounds: [0.345, 0.168, 0.66, 0.355],
    feather: [0.018, 0.012],
};
pub(super) const LEFT_EYE: Patch = Patch {
    bounds: [0.355, 0.217, 0.477, 0.266],
    feather: [0.006, 0.005],
};
pub(super) const RIGHT_EYE: Patch = Patch {
    bounds: [0.530, 0.197, 0.634, 0.243],
    feather: [0.006, 0.005],
};
pub(super) const MOUTH: Patch = Patch {
    bounds: [0.460, 0.289, 0.580, 0.331],
    feather: [0.009, 0.006],
};

pub(super) fn draw(
    painter: &egui::Painter,
    texture: &TextureHandle,
    target: Rect,
    uv: Rect,
    patch: Patch,
    opacity: f32,
) {
    painter.add(mesh(texture.id(), target, uv, patch, opacity));
}

pub(super) fn mesh(
    texture: TextureId,
    target: Rect,
    uv: Rect,
    patch: Patch,
    opacity: f32,
) -> egui::Mesh {
    let [left, top, right, bottom] = patch.bounds;
    let outer = Rect::from_min_max(pos2(left, top), pos2(right, bottom));
    let inner = outer.shrink2(vec2(patch.feather[0], patch.feather[1]));
    let mut mesh = egui::Mesh::with_texture(texture);
    // A fully opaque inner quad and transparent outer ring feather the source
    // face into the fixed body. UVs share the base card's breath transform.
    let fill = Color32::WHITE.gamma_multiply(opacity.clamp(0.0, 1.0));
    for (ring, color) in [(inner, fill), (outer, Color32::TRANSPARENT)] {
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
