use std::path::Path;

use eframe::egui;

pub(super) const SURFACE: egui::Color32 = egui::Color32::from_rgb(28, 33, 45);
pub(super) const ACCENT: egui::Color32 = egui::Color32::from_rgb(164, 190, 230);
pub(super) const MUTED: egui::Color32 = egui::Color32::from_rgb(157, 165, 184);

pub(crate) fn configure_appearance(context: &egui::Context) {
    let mut visuals = egui::Visuals::dark();
    visuals.panel_fill = egui::Color32::from_rgb(20, 24, 34);
    visuals.window_fill = SURFACE;
    visuals.extreme_bg_color = egui::Color32::from_rgb(17, 21, 31);
    visuals.faint_bg_color = SURFACE;
    visuals.weak_text_color = Some(MUTED);
    visuals.selection.bg_fill = egui::Color32::from_rgb(55, 75, 109);
    visuals.selection.stroke = egui::Stroke::new(1.0, ACCENT);
    visuals.hyperlink_color = ACCENT;
    visuals.widgets.inactive.bg_fill = egui::Color32::from_rgb(38, 45, 61);
    visuals.widgets.inactive.weak_bg_fill = egui::Color32::from_rgb(38, 45, 61);
    visuals.widgets.hovered.bg_fill = egui::Color32::from_rgb(54, 64, 84);
    visuals.widgets.active.bg_fill = egui::Color32::from_rgb(62, 79, 108);
    context.set_visuals(visuals);
    let mut style = (*context.style_of(egui::Theme::Dark)).clone();
    style.spacing.item_spacing = egui::vec2(10.0, 8.0);
    style.spacing.button_padding = egui::vec2(14.0, 7.0);
    style.spacing.interact_size.y = 32.0;
    style
        .text_styles
        .insert(egui::TextStyle::Body, egui::FontId::proportional(15.0));
    style
        .text_styles
        .insert(egui::TextStyle::Button, egui::FontId::proportional(15.0));
    style
        .text_styles
        .insert(egui::TextStyle::Heading, egui::FontId::proportional(23.0));
    context.set_style_of(egui::Theme::Dark, style);

    let font_paths = [
        Path::new("C:/Windows/Fonts/msyh.ttc"),
        Path::new("C:/Windows/Fonts/simhei.ttf"),
    ];
    let Some(bytes) = font_paths.iter().find_map(|path| std::fs::read(path).ok()) else {
        return;
    };
    let mut fonts = egui::FontDefinitions::default();
    fonts.font_data.insert(
        "ai-ex-cjk".to_owned(),
        egui::FontData::from_owned(bytes).into(),
    );
    for family in [egui::FontFamily::Proportional, egui::FontFamily::Monospace] {
        fonts
            .families
            .entry(family)
            .or_default()
            .insert(0, "ai-ex-cjk".to_owned());
    }
    context.set_fonts(fonts);
}
