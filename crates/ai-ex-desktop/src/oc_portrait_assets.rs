use eframe::egui::ColorImage;
use std::sync::{Arc, OnceLock};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub(super) enum Frame {
    Portrait,
    Blink,
    Speaking,
}

const IMAGES: [&[u8]; 3] = [
    include_bytes!("../assets/oc-01/portrait.png"),
    include_bytes!("../assets/oc-01/blink.png"),
    include_bytes!("../assets/oc-01/speaking.png"),
];
type Decoded = Result<Arc<ColorImage>, String>;
static PIXELS: [OnceLock<Decoded>; 3] = [const { OnceLock::new() }; 3];

pub(super) fn decoded(frame: Frame) -> &'static Decoded {
    PIXELS[frame as usize].get_or_init(|| decode(IMAGES[frame as usize]).map(Arc::new))
}

fn decode(bytes: &[u8]) -> Result<ColorImage, String> {
    let mut reader =
        image::ImageReader::with_format(std::io::Cursor::new(bytes), image::ImageFormat::Png);
    let mut limits = image::Limits::default();
    limits.max_image_width = Some(4096);
    limits.max_image_height = Some(4096);
    limits.max_alloc = Some(64 * 1024 * 1024);
    reader.limits(limits);
    let image = reader
        .decode()
        .map_err(|error| error.to_string())?
        .into_rgba8();
    Ok(ColorImage::from_rgba_unmultiplied(
        [image.width() as usize, image.height() as usize],
        image.as_raw(),
    ))
}
