use eframe::egui;

const STORAGE_KEY: &str = "preview.oc_gallery.selection";

struct Asset {
    id: &'static str,
    label: &'static str,
    caption: &'static str,
    bytes: &'static [u8],
}

const ASSETS: [Asset; 6] = [
    Asset {
        id: "portrait",
        label: "正式立绘",
        caption: "人物的正式外观基准，完整保留发型、服装与全身比例。",
        bytes: include_bytes!("../assets/oc-01/portrait.png"),
    },
    Asset {
        id: "expressions",
        label: "表情参考",
        caption: "六格表情参考：平静、开心、思考、惊讶、害羞、温柔关切。这是一张静态参考板。",
        bytes: include_bytes!("../assets/oc-01/expressions.png"),
    },
    Asset {
        id: "welcome",
        label: "欢迎",
        caption: "挥手问候，适合欢迎与初次见面的场景。",
        bytes: include_bytes!("../assets/oc-01/welcome.png"),
    },
    Asset {
        id: "focus",
        label: "专注",
        caption: "安静阅读，适合专注、学习与陪伴的场景。",
        bytes: include_bytes!("../assets/oc-01/focus.png"),
    },
    Asset {
        id: "success",
        label: "完成庆祝",
        caption: "轻轻握拳庆祝，适合完成一件事时的反馈。",
        bytes: include_bytes!("../assets/oc-01/success.png"),
    },
    Asset {
        id: "encourage",
        label: "温柔鼓励",
        caption: "温和的目光与伸手邀请，适合鼓励与继续尝试的场景。",
        bytes: include_bytes!("../assets/oc-01/encourage.png"),
    },
];

pub(super) struct OcGallery {
    selected: usize,
    textures: [Option<Result<egui::TextureHandle, String>>; ASSETS.len()],
}

impl Default for OcGallery {
    fn default() -> Self {
        Self {
            selected: 0,
            textures: std::array::from_fn(|_| None),
        }
    }
}

impl OcGallery {
    pub(super) fn load(storage: Option<&dyn eframe::Storage>) -> Self {
        let selected = storage
            .and_then(|storage| storage.get_string(STORAGE_KEY))
            .and_then(|id| ASSETS.iter().position(|asset| asset.id == id))
            .unwrap_or(0);
        Self {
            selected,
            ..Default::default()
        }
    }

    pub(super) fn save(&self, storage: &mut dyn eframe::Storage) {
        storage.set_string(STORAGE_KEY, self.selected_id().to_owned());
    }

    pub(super) fn selected_id(&self) -> &'static str {
        ASSETS[self.selected].id
    }

    pub(super) fn show(&mut self, ui: &mut egui::Ui) {
        ui.weak("这里只查看静态素材，不会应用到人物舞台。");
        ui.horizontal_wrapped(|ui| {
            for (index, asset) in ASSETS.iter().enumerate() {
                ui.selectable_value(&mut self.selected, index, asset.label);
            }
        });
        ui.add_space(6.0);
        ui.label(ASSETS[self.selected].caption);
        ui.add_space(6.0);
        let asset = &ASSETS[self.selected];
        let cached = self.textures[self.selected].get_or_insert_with(|| {
            decode(asset.bytes).map(|image| {
                ui.ctx().load_texture(
                    format!("oc-gallery-{}", asset.id),
                    image,
                    egui::TextureOptions::LINEAR,
                )
            })
        });
        match cached {
            Ok(texture) => {
                let original = texture.size_vec2();
                let scale = (ui.available_width().max(1.0) / original.x)
                    .min(380.0 / original.y)
                    .min(1.0);
                ui.vertical_centered(|ui| {
                    ui.image((texture.id(), original * scale));
                });
            }
            Err(error) => {
                ui.colored_label(ui.visuals().error_fg_color, "这张素材暂时无法显示。");
                ui.collapsing("查看原因", |ui| {
                    ui.small(error.as_str());
                });
            }
        }
    }
}

fn decode(bytes: &[u8]) -> Result<egui::ColorImage, String> {
    let mut reader =
        image::ImageReader::with_format(std::io::Cursor::new(bytes), image::ImageFormat::Png);
    let mut limits = image::Limits::default();
    limits.max_image_width = Some(2048);
    limits.max_image_height = Some(2048);
    limits.max_alloc = Some(32 * 1024 * 1024);
    reader.limits(limits);
    let pixels = reader
        .decode()
        .map_err(|error| error.to_string())?
        .into_rgba8();
    Ok(egui::ColorImage::from_rgba_unmultiplied(
        [pixels.width() as usize, pixels.height() as usize],
        pixels.as_raw(),
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Default)]
    struct Storage(std::collections::HashMap<String, String>);

    impl eframe::Storage for Storage {
        fn get_string(&self, key: &str) -> Option<String> {
            self.0.get(key).cloned()
        }

        fn set_string(&mut self, key: &str, value: String) {
            self.0.insert(key.to_owned(), value);
        }

        fn remove_string(&mut self, key: &str) {
            self.0.remove(key);
        }

        fn flush(&mut self) {}
    }

    #[test]
    fn selection_round_trips_and_unknown_saved_item_falls_back() {
        let mut storage = Storage::default();
        let gallery = OcGallery {
            selected: 4,
            ..Default::default()
        };
        gallery.save(&mut storage);
        assert_eq!(storage.0[STORAGE_KEY], "success");
        assert_eq!(OcGallery::load(Some(&storage)).selected, 4);
        storage
            .0
            .insert(STORAGE_KEY.to_owned(), "missing".to_owned());
        assert_eq!(OcGallery::load(Some(&storage)).selected, 0);
        assert_eq!(storage.0.len(), 1);
    }

    #[test]
    fn images_load_on_demand_and_each_asset_keeps_one_cached_texture() {
        let context = egui::Context::default();
        let mut gallery = OcGallery::default();
        assert!(gallery.textures.iter().all(Option::is_none));
        for index in 0..ASSETS.len() {
            gallery.selected = index;
            let _output = context.run_ui(Default::default(), |ui| gallery.show(ui));
            assert_eq!(
                gallery
                    .textures
                    .iter()
                    .filter(|entry| entry.is_some())
                    .count(),
                index + 1
            );
            assert!(gallery.textures[index].as_ref().unwrap().is_ok());
        }
        let texture_ids: Vec<_> = gallery
            .textures
            .iter()
            .map(|entry| entry.as_ref().unwrap().as_ref().unwrap().id())
            .collect();
        for (index, expected) in texture_ids.into_iter().enumerate() {
            gallery.selected = index;
            let _output = context.run_ui(Default::default(), |ui| gallery.show(ui));
            let actual = gallery.textures[index].as_ref().unwrap().as_ref().unwrap();
            assert_eq!(actual.id(), expected);
        }
    }

    #[test]
    fn corrupt_and_oversized_images_fail_with_a_visible_message() {
        assert!(decode(b"not a PNG").is_err());
        let mut encoded = std::io::Cursor::new(Vec::new());
        image::RgbaImage::new(2049, 1)
            .write_to(&mut encoded, image::ImageFormat::Png)
            .unwrap();
        assert!(decode(encoded.get_ref()).is_err());
        let mut gallery = OcGallery::default();
        gallery.textures[0] = Some(Err("broken image".to_owned()));
        let context = egui::Context::default();
        let output = context.run_ui(Default::default(), |ui| gallery.show(ui));
        assert!(output.shapes.iter().any(|shape| {
            matches!(&shape.shape, egui::Shape::Text(text)
                if text.galley.job.text == "这张素材暂时无法显示。")
        }));
        assert!(gallery.textures[0].as_ref().unwrap().is_err());
        assert!(gallery.textures[1..].iter().all(Option::is_none));
    }
}
