use eframe::egui::{
    self, ColorImage, Context, FullOutput, Pos2, Rect, TextureId, epaint::Primitive, pos2, vec2,
};
use image::{Rgba, RgbaImage};
use std::{error::Error, path::Path};

/// Captures built-in shapes and text without a window or graphics device.
/// Custom image textures and paint callbacks are deliberately rejected.
pub fn save(
    context: &Context,
    output: FullOutput,
    size: [u32; 2],
    path: &Path,
) -> Result<(), Box<dyn Error>> {
    let pixels_per_point = output.pixels_per_point;
    let primitives = context.tessellate(output.shapes, pixels_per_point);
    let atlas = context.fonts(|fonts| fonts.image());
    let width = (size[0] as f32 * pixels_per_point).round() as u32;
    let height = (size[1] as f32 * pixels_per_point).round() as u32;
    let mut canvas = RgbaImage::from_pixel(width, height, Rgba([246, 246, 249, 255]));
    for primitive in primitives {
        let Primitive::Mesh(mesh) = primitive.primitive else {
            return Err("headless snapshots do not support paint callbacks".into());
        };
        if mesh.texture_id != TextureId::Managed(0) {
            return Err("headless snapshots support built-in shapes and text only".into());
        }
        let clip = Rect::from_min_max(
            primitive.clip_rect.min * pixels_per_point,
            primitive.clip_rect.max * pixels_per_point,
        );
        for triangle in mesh.indices.chunks_exact(3) {
            let vertices = [triangle[0], triangle[1], triangle[2]].map(|index| {
                let mut vertex = mesh.vertices[index as usize];
                vertex.pos *= pixels_per_point;
                vertex
            });
            rasterize(&mut canvas, &atlas, clip, vertices);
        }
    }
    let mut file = std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)?;
    canvas.write_to(&mut file, image::ImageFormat::Png)?;
    Ok(())
}

fn rasterize(
    canvas: &mut RgbaImage,
    atlas: &ColorImage,
    clip: Rect,
    vertices: [egui::epaint::Vertex; 3],
) {
    let positions = vertices.map(|vertex| vertex.pos);
    let area = cross(positions[0], positions[1], positions[2]);
    if area.abs() < 0.001 {
        return;
    }
    let bounds = Rect::from_points(&positions)
        .intersect(clip)
        .intersect(Rect::from_min_size(
            Pos2::ZERO,
            vec2(canvas.width() as f32, canvas.height() as f32),
        ));
    if !bounds.is_positive() {
        return;
    }
    for y in bounds.top().floor() as u32..(bounds.bottom().ceil() as u32).min(canvas.height()) {
        for x in bounds.left().floor() as u32..(bounds.right().ceil() as u32).min(canvas.width()) {
            let point = pos2(x as f32 + 0.5, y as f32 + 0.5);
            if !clip.contains(point) {
                continue;
            }
            let weights = [
                cross(positions[1], positions[2], point) / area,
                cross(positions[2], positions[0], point) / area,
                cross(positions[0], positions[1], point) / area,
            ];
            if weights.iter().any(|weight| *weight < 0.0) {
                continue;
            }
            let uv = vertices
                .iter()
                .zip(weights)
                .fold(egui::Vec2::ZERO, |value, (vertex, weight)| {
                    value + vertex.uv.to_vec2() * weight
                });
            let tx = ((uv.x * atlas.size[0] as f32).floor() as usize).min(atlas.size[0] - 1);
            let ty = ((uv.y * atlas.size[1] as f32).floor() as usize).min(atlas.size[1] - 1);
            let texture = atlas.pixels[ty * atlas.size[0] + tx].to_array();
            let channel = |index: usize| {
                vertices
                    .iter()
                    .zip(weights)
                    .map(|(vertex, weight)| vertex.color.to_array()[index] as f32 * weight)
                    .sum::<f32>()
                    * texture[index] as f32
                    / 255.0
            };
            let alpha = channel(3) / 255.0;
            let background = canvas.get_pixel(x, y).0;
            let mut color = [0, 0, 0, 255];
            for index in 0..3 {
                color[index] = (channel(index) + background[index] as f32 * (1.0 - alpha))
                    .round()
                    .clamp(0.0, 255.0) as u8;
            }
            canvas.put_pixel(x, y, Rgba(color));
        }
    }
}

fn cross(a: Pos2, b: Pos2, c: Pos2) -> f32 {
    (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
}
