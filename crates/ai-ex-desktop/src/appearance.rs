use ai_ex_ui_model::PresentationState;
use eframe::egui::{self, Color32};

#[path = "appearance_paint.rs"]
mod paint;

#[path = "appearance_scene.rs"]
mod scene;

#[cfg(test)]
#[path = "appearance_tests.rs"]
mod tests;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AppearanceKind
{
    Companion,
    Orb,
    Images,
    Hidden,
}

pub struct AppearancePanel
{
    pub kind: AppearanceKind,
    pub accent: [u8; 3],
    pub reduced_motion: bool,
    images: crate::appearance_import::AppearanceImport,
    image_scale: f32,
}

impl Default for AppearancePanel
{
    fn default() -> Self
    {
        Self {
            kind: AppearanceKind::Companion, accent: [129, 178, 247], reduced_motion: false,
            images: Default::default(), image_scale: 0.95,
        }
    }
}

impl AppearancePanel
{
    pub fn load(storage: Option<&dyn eframe::Storage>) -> Self
    {
        let mut result = Self { images: crate::appearance_import::AppearanceImport::load(storage), ..Default::default() };
        if let Some(storage) = storage
        {
            result.kind = match storage.get_string("appearance.kind").as_deref()
            {
                Some("orb") => AppearanceKind::Orb,
                Some("images") => AppearanceKind::Images,
                Some("hidden") => AppearanceKind::Hidden,
                _ => AppearanceKind::Companion,
            };
            result.reduced_motion = storage.get_string("appearance.reduced_motion").as_deref() == Some("true");
            if let Some(scale) = storage.get_string("appearance.image_scale").and_then(|value| value.parse::<f32>().ok()).filter(|value| value.is_finite())
            {
                result.image_scale = scale.clamp(0.25, 1.0);
            }
            if let Some(color) = storage.get_string("appearance.accent")
            {
                let values: Result<Vec<u8>, _> = color.split(',').map(str::parse).collect();
                if let Ok(values) = values
                    && let Ok(rgb) = <[u8; 3]>::try_from(values)
                {
                    result.accent = rgb;
                }
            }
        }
        result
    }

    pub fn save(&self, storage: &mut dyn eframe::Storage)
    {
        let kind = match self.kind
        {
            AppearanceKind::Companion => "companion",
            AppearanceKind::Orb => "orb",
            AppearanceKind::Images => "images",
            AppearanceKind::Hidden => "hidden",
        };
        storage.set_string("appearance.kind", kind.to_owned());
        storage.set_string("appearance.reduced_motion", self.reduced_motion.to_string());
        storage.set_string("appearance.accent", format!("{},{},{}", self.accent[0], self.accent[1], self.accent[2]));
        storage.set_string("appearance.image_scale", self.image_scale.to_string());
        self.images.save(storage);
    }

    pub fn use_images(&mut self, context: &egui::Context, decoded: crate::image_appearance::DecodedAppearance)
    {
        self.images.install(context, decoded);
        self.kind = AppearanceKind::Images;
    }

    pub fn show(&mut self, ui: &mut egui::Ui, state: PresentationState, name: &str, height: f32)
    {
        if self.images.poll(ui.ctx())
        {
            self.kind = AppearanceKind::Images;
        }
        let previous = self.kind;
        ui.horizontal_wrapped(|ui|
        {
            ui.selectable_value(&mut self.kind, AppearanceKind::Companion, "2D 伙伴");
            ui.selectable_value(&mut self.kind, AppearanceKind::Orb, "光球");
            ui.selectable_value(&mut self.kind, AppearanceKind::Images, "图片角色");
            ui.selectable_value(&mut self.kind, AppearanceKind::Hidden, "隐藏外形");
            if self.kind == AppearanceKind::Images
            {
                ui.add(egui::Slider::new(&mut self.image_scale, 0.25..=1.0).text("大小"));
            }
            else
            {
                ui.label("配色");
                ui.color_edit_button_srgb(&mut self.accent);
            }
            ui.checkbox(&mut self.reduced_motion, "减少动态效果");
        });
        if previous != self.kind
        {
            self.images.keep_selection();
        }
        if self.kind == AppearanceKind::Images
        {
            self.images.controls(ui);
        }
        if self.kind != AppearanceKind::Hidden
        {
            let (rect, _) = ui.allocate_exact_size(egui::vec2(ui.available_width(), height), egui::Sense::hover());
            let time = ui.input(|input| input.time);
            let frame = state.animate(time, self.reduced_motion);
            let accent = Color32::from_rgb(self.accent[0], self.accent[1], self.accent[2]);
            if self.kind == AppearanceKind::Images && let Some(pack) = &self.images.current
            {
                pack.draw(ui.painter(), rect, state, frame, self.image_scale);
            }
            else
            {
                paint::draw(ui.painter(), rect, self.kind, state, frame, accent);
            }
            if !self.reduced_motion && state.connected && state.synchronized
            {
                ui.ctx().request_repaint_after(std::time::Duration::from_millis(33));
            }
        }
        ui.horizontal_wrapped(|ui|
        {
            ui.strong(name);
            ui.label(state.label());
        });
    }
}
