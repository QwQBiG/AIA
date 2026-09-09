use crate::builtin_character::BuiltinCharacter;
use ai_ex_config::scene::BuiltinFraming;
use ai_ex_ui_model::{PresentationAnimator, PresentationState};
use eframe::egui::{self, Color32};

#[path = "appearance_paint.rs"]
mod paint;

#[path = "anime_portrait.rs"]
mod anime;

#[path = "oc_portrait.rs"]
mod oc;

#[path = "appearance_scene.rs"]
mod scene;

#[cfg(test)]
#[path = "appearance_tests.rs"]
mod tests;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AppearanceKind {
    Companion,
    Images,
    Hidden,
}

pub struct AppearancePanel {
    pub kind: AppearanceKind,
    pub accent: [u8; 3],
    pub reduced_motion: bool,
    pub builtin: BuiltinCharacter,
    pub framing: BuiltinFraming,
    images: crate::appearance_import::AppearanceImport,
    image_scale: f32,
    animation: PresentationAnimator,
    portrait: anime::AnimePortrait,
    oc_portrait: oc::OcPortrait,
    rendered_builtin: Option<BuiltinCharacter>,
    unknown_builtin: bool,
}

impl Default for AppearancePanel {
    fn default() -> Self {
        Self {
            kind: AppearanceKind::Companion,
            accent: [154, 133, 184],
            reduced_motion: false,
            builtin: BuiltinCharacter::default(),
            framing: BuiltinFraming::default(),
            images: Default::default(),
            image_scale: 0.95,
            animation: PresentationAnimator::default(),
            portrait: anime::AnimePortrait::default(),
            oc_portrait: oc::OcPortrait::default(),
            rendered_builtin: None,
            unknown_builtin: false,
        }
    }
}

impl AppearancePanel {
    pub fn load(storage: Option<&dyn eframe::Storage>) -> Self {
        let mut result = Self {
            images: crate::appearance_import::AppearanceImport::load(storage),
            ..Default::default()
        };
        if let Some(storage) = storage {
            if let Some(id) = storage.get_string("appearance.builtin_id") {
                match BuiltinCharacter::from_id(&id) {
                    Some(builtin) => result.builtin = builtin,
                    None => result.unknown_builtin = true,
                }
            }
            result.framing = match storage.get_string("appearance.framing").as_deref() {
                Some("full_body") => BuiltinFraming::FullBody,
                _ => BuiltinFraming::Portrait,
            };
            result.kind = match storage.get_string("appearance.kind").as_deref() {
                Some("images") => AppearanceKind::Images,
                Some("hidden") => AppearanceKind::Hidden,
                _ => AppearanceKind::Companion,
            };
            result.reduced_motion =
                storage.get_string("appearance.reduced_motion").as_deref() == Some("true");
            if let Some(scale) = storage
                .get_string("appearance.image_scale")
                .and_then(|value| value.parse::<f32>().ok())
                .filter(|value| value.is_finite())
            {
                result.image_scale = scale.clamp(0.25, 1.0);
            }
            if let Some(color) = storage.get_string("appearance.accent") {
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

    pub fn save(&self, storage: &mut dyn eframe::Storage) {
        let kind = match self.kind {
            AppearanceKind::Companion => "companion",
            AppearanceKind::Images => "images",
            AppearanceKind::Hidden => "hidden",
        };
        storage.set_string("appearance.kind", kind.to_owned());
        storage.set_string("appearance.builtin_id", self.builtin.id().to_owned());
        storage.set_string(
            "appearance.framing",
            match self.framing {
                BuiltinFraming::Portrait => "portrait",
                BuiltinFraming::FullBody => "full_body",
            }
            .to_owned(),
        );
        storage.set_string("appearance.reduced_motion", self.reduced_motion.to_string());
        storage.set_string(
            "appearance.accent",
            format!("{},{},{}", self.accent[0], self.accent[1], self.accent[2]),
        );
        storage.set_string("appearance.image_scale", self.image_scale.to_string());
        self.images.save(storage);
    }

    pub fn use_images(
        &mut self,
        context: &egui::Context,
        decoded: crate::image_appearance::DecodedAppearance,
    ) {
        self.images.install(context, decoded);
        self.kind = AppearanceKind::Images;
    }

    pub(crate) fn builtin_character(&self) -> BuiltinCharacter {
        self.builtin
    }

    fn synchronize_builtin(&mut self) {
        if self.rendered_builtin != Some(self.builtin) {
            self.portrait = anime::AnimePortrait::default();
            self.oc_portrait = oc::OcPortrait::default();
            self.animation = PresentationAnimator::default();
            self.rendered_builtin = Some(self.builtin);
        }
    }

    #[cfg(test)]
    pub fn show(&mut self, ui: &mut egui::Ui, state: PresentationState, name: &str, height: f32) {
        self.show_controls(ui);
        self.show_portrait(ui, state, name, height);
    }

    pub fn show_controls(&mut self, ui: &mut egui::Ui) {
        self.poll(ui.ctx());
        let previous = self.kind;
        ui.horizontal_wrapped(|ui| {
            ui.selectable_value(&mut self.kind, AppearanceKind::Companion, "内置立绘");
            ui.selectable_value(&mut self.kind, AppearanceKind::Images, "自选图片");
            ui.selectable_value(&mut self.kind, AppearanceKind::Hidden, "隐藏外形");
        });
        if previous != self.kind {
            self.images.keep_selection();
        }
        ui.add_space(8.0);
        match self.kind {
            AppearanceKind::Companion => {
                let previous = self.builtin;
                ui.horizontal_wrapped(|ui| {
                    for builtin in BuiltinCharacter::ALL {
                        if ui
                            .selectable_value(&mut self.builtin, builtin, builtin.label())
                            .clicked()
                        {
                            self.unknown_builtin = false;
                        }
                    }
                });
                if previous != self.builtin {
                    self.unknown_builtin = false;
                    self.synchronize_builtin();
                }
                if self.builtin == BuiltinCharacter::Oc01 {
                    ui.horizontal_wrapped(|ui| {
                        ui.selectable_value(
                            &mut self.framing,
                            BuiltinFraming::Portrait,
                            "半身近景",
                        );
                        ui.selectable_value(
                            &mut self.framing,
                            BuiltinFraming::FullBody,
                            "全身立绘",
                        );
                    });
                    ui.weak("一号人物已准备好；可以选择更近的陪伴视角或完整立绘。");
                } else {
                    ui.weak("保留初始伙伴的表情与配色，可以随时切换回来。");
                }
            }
            AppearanceKind::Images => {
                self.images.controls(ui);
                ui.add(egui::Slider::new(&mut self.image_scale, 0.25..=1.0).text("显示大小"));
            }
            AppearanceKind::Hidden => {
                ui.weak("对话和声音会继续保留。");
            }
        }
        ui.add_space(8.0);
        ui.horizontal_wrapped(|ui| {
            ui.label("舞台点缀");
            ui.color_edit_button_srgb(&mut self.accent)
                .on_hover_text("调整立绘卡片与姓名旁的点缀颜色。人物服装保留原画配色。");
        });
        ui.checkbox(&mut self.reduced_motion, "减少动态效果");
    }

    pub fn poll(&mut self, context: &egui::Context) {
        if self.images.poll(context) {
            self.kind = AppearanceKind::Images;
        }
    }

    pub fn show_portrait(
        &mut self,
        ui: &mut egui::Ui,
        state: PresentationState,
        name: &str,
        height: f32,
    ) {
        self.synchronize_builtin();
        if self.kind != AppearanceKind::Hidden {
            let (rect, _) = ui.allocate_exact_size(
                egui::vec2(ui.available_width(), height),
                egui::Sense::hover(),
            );
            let time = ui.input(|input| input.time);
            let frame = self.animation.sample(state, time, self.reduced_motion);
            let accent = Color32::from_rgb(self.accent[0], self.accent[1], self.accent[2]);
            if self.kind == AppearanceKind::Images
                && let Some(pack) = &self.images.current
            {
                pack.draw(ui.painter(), rect, state, frame, self.image_scale);
            } else {
                match self.builtin {
                    BuiltinCharacter::Original => {
                        if self
                            .portrait
                            .draw(
                                ui.painter(),
                                rect,
                                state,
                                frame,
                                self.reduced_motion,
                                accent,
                            )
                            .is_err()
                        {
                            paint::draw(ui.painter(), rect, frame, accent);
                        }
                    }
                    BuiltinCharacter::Oc01 => {
                        if self
                            .oc_portrait
                            .draw(
                                ui.painter(),
                                rect,
                                state,
                                frame,
                                oc::Options {
                                    framing: self.framing,
                                    reduced_motion: self.reduced_motion,
                                    accent,
                                },
                            )
                            .is_err()
                        {
                            ui.painter().text(
                                rect.center(),
                                egui::Align2::CENTER_CENTER,
                                "一号人物暂时无法显示",
                                egui::FontId::proportional(16.0),
                                ui.visuals().weak_text_color(),
                            );
                        }
                    }
                }
            }
            let motion_allowed = if self.kind == AppearanceKind::Companion
                && self.builtin == BuiltinCharacter::Oc01
            {
                oc::motion_allowed(state, self.reduced_motion)
            } else {
                anime::motion_allowed(state, self.reduced_motion)
            };
            if motion_allowed {
                ui.ctx()
                    .request_repaint_after(std::time::Duration::from_millis(33));
            }
        }
        ui.allocate_ui_with_layout(
            egui::vec2(ui.available_width(), 24.0),
            egui::Layout::left_to_right(egui::Align::Center).with_main_align(egui::Align::Center),
            |ui| {
                ui.strong(name);
                ui.colored_label(
                    Color32::from_rgb(self.accent[0], self.accent[1], self.accent[2]),
                    "·",
                );
                ui.weak(state.label());
                if self.kind == AppearanceKind::Companion
                    && self.builtin == BuiltinCharacter::Oc01
                    && anime::motion_allowed(state, false)
                {
                    let emotion = match state.emotion {
                        ai_ex_domain::Emotion::Neutral => None,
                        ai_ex_domain::Emotion::Happy => Some("开心"),
                        ai_ex_domain::Emotion::Sad => Some("低落"),
                        ai_ex_domain::Emotion::Angry => Some("生气"),
                        ai_ex_domain::Emotion::Surprised => Some("惊讶"),
                    };
                    if let Some(emotion) = emotion {
                        ui.weak(format!("· {emotion}"));
                    }
                }
            },
        );
        if self.unknown_builtin && self.kind == AppearanceKind::Companion {
            ui.weak("保存的内置人物暂不可用，已显示一号人物。请重新选择人物。");
        }
    }
}
