use eframe::egui::{
    self, ColorImage, Context, FullOutput, Pos2, Rect, TextureId, epaint::Primitive, pos2, vec2,
};
use image::{Rgba, RgbaImage};
use std::{collections::HashMap, error::Error, path::Path, sync::Arc};

/// Captures shapes, text and managed image textures without a window.
/// Append setup frames to the final output so their texture uploads are retained.
pub fn save(
    context: &Context,
    mut output: FullOutput,
    size: [u32; 2],
    path: &Path,
) -> Result<(), Box<dyn Error>> {
    let pixels_per_point = output.pixels_per_point;
    let primitives = context.tessellate(std::mem::take(&mut output.shapes), pixels_per_point);
    let textures = collect_textures(&output, context.fonts(|fonts| fonts.image()))?;
    let width = (size[0] as f32 * pixels_per_point).round() as u32;
    let height = (size[1] as f32 * pixels_per_point).round() as u32;
    let background = context.global_style().visuals.panel_fill.to_array();
    let mut canvas = RgbaImage::from_pixel(width, height, Rgba(background));
    for primitive in primitives {
        let Primitive::Mesh(mesh) = primitive.primitive else {
            return Err("headless snapshots do not support paint callbacks".into());
        };
        let texture = textures
            .get(&mesh.texture_id)
            .ok_or("missing texture upload: append the setup frames before saving the snapshot")?;
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
            rasterize(
                &mut canvas,
                texture,
                clip,
                vertices,
                mesh.texture_id != TextureId::Managed(0),
            );
        }
    }
    let mut file = std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)?;
    canvas.write_to(&mut file, image::ImageFormat::Png)?;
    Ok(())
}

fn collect_textures(
    output: &FullOutput,
    font_atlas: ColorImage,
) -> Result<HashMap<TextureId, Arc<ColorImage>>, Box<dyn Error>> {
    let mut textures = HashMap::new();
    textures.insert(TextureId::Managed(0), Arc::new(font_atlas));
    for (id, delta) in &output.textures_delta.set {
        if *id == TextureId::Managed(0) {
            continue;
        }
        let egui::ImageData::Color(image) = &delta.image;
        if let Some([x, y]) = delta.pos {
            let texture = textures
                .get_mut(id)
                .ok_or("texture patch arrived before its full image")?;
            let texture = Arc::make_mut(texture);
            if x.checked_add(image.size[0])
                .is_none_or(|end| end > texture.size[0])
                || y.checked_add(image.size[1])
                    .is_none_or(|end| end > texture.size[1])
            {
                return Err("texture patch exceeds its image bounds".into());
            }
            for row in 0..image.size[1] {
                let target = (y + row) * texture.size[0] + x;
                let source = row * image.size[0];
                texture.pixels[target..target + image.size[0]]
                    .copy_from_slice(&image.pixels[source..source + image.size[0]]);
            }
        } else {
            textures.insert(*id, Arc::clone(image));
        }
    }
    Ok(textures)
}

fn rasterize(
    canvas: &mut RgbaImage,
    atlas: &ColorImage,
    clip: Rect,
    vertices: [egui::epaint::Vertex; 3],
    linear: bool,
) {
    let positions = vertices.map(|vertex| vertex.pos);
    let area = cross(positions[0], positions[1], positions[2]);
    if area.abs() < 0.001 {
        return;
    }
    let owns_edge = [
        (positions[1], positions[2]),
        (positions[2], positions[0]),
        (positions[0], positions[1]),
    ]
    .map(|(a, b)| {
        let (a, b) = if area < 0.0 { (b, a) } else { (a, b) };
        a.y > b.y || (a.y == b.y && a.x < b.x)
    });
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
            if weights
                .iter()
                .zip(owns_edge)
                .any(|(weight, owned)| *weight < 0.0 || (*weight == 0.0 && !owned))
            {
                continue;
            }
            let uv = vertices
                .iter()
                .zip(weights)
                .fold(egui::Vec2::ZERO, |value, (vertex, weight)| {
                    value + vertex.uv.to_vec2() * weight
                });
            let texture = sample(atlas, uv, linear);
            let channel = |index: usize| {
                vertices
                    .iter()
                    .zip(weights)
                    .map(|(vertex, weight)| vertex.color.to_array()[index] as f32 * weight)
                    .sum::<f32>()
                    * texture[index]
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

fn sample(image: &ColorImage, uv: egui::Vec2, linear: bool) -> [f32; 4] {
    let texel = |x: usize, y: usize| {
        image.pixels[y.min(image.size[1] - 1) * image.size[0] + x.min(image.size[0] - 1)]
            .to_array()
            .map(f32::from)
    };
    if !linear {
        return texel(
            (uv.x * image.size[0] as f32).floor() as usize,
            (uv.y * image.size[1] as f32).floor() as usize,
        );
    }
    let x = (uv.x * image.size[0] as f32 - 0.5).max(0.0);
    let y = (uv.y * image.size[1] as f32 - 0.5).max(0.0);
    let left = x.floor() as usize;
    let top = y.floor() as usize;
    let [a, b, c, d] = [
        texel(left, top),
        texel(left + 1, top),
        texel(left, top + 1),
        texel(left + 1, top + 1),
    ];
    std::array::from_fn(|i| {
        (a[i] * (1.0 - x.fract()) + b[i] * x.fract()) * (1.0 - y.fract())
            + (c[i] * (1.0 - x.fract()) + d[i] * x.fract()) * y.fract()
    })
}

fn cross(a: Pos2, b: Pos2, c: Pos2) -> f32 {
    (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn texture_updates_preserve_untouched_pixels_and_reject_missing_or_oversized_base() {
        let id = TextureId::Managed(1);
        let base = ColorImage::filled([2, 2], egui::Color32::BLUE);
        let patch = egui::epaint::ImageDelta::partial(
            [1, 0],
            ColorImage::filled([1, 1], egui::Color32::RED),
            egui::TextureOptions::LINEAR,
        );
        let mut output = FullOutput::default();
        output.textures_delta.set.push((id, patch.clone()));
        assert!(collect_textures(&output, base.clone()).is_err());
        output.textures_delta.set.insert(
            0,
            (
                id,
                egui::epaint::ImageDelta::full(base.clone(), egui::TextureOptions::LINEAR),
            ),
        );
        let textures = collect_textures(&output, base.clone()).unwrap();
        assert_eq!(
            textures[&id].pixels,
            [
                egui::Color32::BLUE,
                egui::Color32::RED,
                egui::Color32::BLUE,
                egui::Color32::BLUE
            ]
        );
        let mut oversized = patch;
        oversized.pos = Some([2, 0]);
        output.textures_delta.set.push((id, oversized));
        assert!(collect_textures(&output, base).is_err());
    }

    #[test]
    fn transparent_character_pixels_blend_with_the_stage() {
        let texture = ColorImage::filled(
            [1, 1],
            egui::Color32::from_rgba_premultiplied(128, 0, 0, 128),
        );
        let mut canvas = RgbaImage::from_pixel(1, 1, Rgba([255, 255, 255, 255]));
        let vertices =
            [pos2(-2.0, -2.0), pos2(4.0, -2.0), pos2(-2.0, 4.0)].map(|pos| egui::epaint::Vertex {
                pos,
                uv: pos2(0.5, 0.5),
                color: egui::Color32::WHITE,
            });
        rasterize(
            &mut canvas,
            &texture,
            Rect::from_min_size(Pos2::ZERO, vec2(1.0, 1.0)),
            vertices,
            true,
        );
        assert_eq!(canvas.get_pixel(0, 0).0, [255, 127, 127, 255]);
    }

    #[test]
    fn shared_triangle_edges_blend_once_in_both_windings() {
        let texture = ColorImage::filled(
            [1, 1],
            egui::Color32::from_rgba_premultiplied(128, 0, 0, 128),
        );
        let clip = Rect::from_min_size(Pos2::ZERO, vec2(1.0, 1.0));
        for reverse in [false, true] {
            let mut canvas = RgbaImage::from_pixel(1, 1, Rgba([255, 255, 255, 255]));
            for positions in [
                [pos2(0.0, 0.0), pos2(1.0, 0.0), pos2(1.0, 1.0)],
                [pos2(0.0, 0.0), pos2(1.0, 1.0), pos2(0.0, 1.0)],
            ] {
                let mut vertices = positions.map(|pos| egui::epaint::Vertex {
                    pos,
                    uv: pos2(0.5, 0.5),
                    color: egui::Color32::WHITE,
                });
                if reverse {
                    vertices.swap(1, 2);
                }
                rasterize(&mut canvas, &texture, clip, vertices, true);
            }
            assert_eq!(canvas.get_pixel(0, 0).0, [255, 127, 127, 255]);
        }
    }
}
