//! Create a small original procedural character pack for the appearance studio.
use std::error::Error;
use std::path::PathBuf;

use image::{Rgba, RgbaImage};

fn main() -> Result<(), Box<dyn Error>> {
    let mut arguments = std::env::args_os().skip(1);
    let destination = PathBuf::from(
        arguments
            .next()
            .ok_or("usage: create_image_pack NEW_DIRECTORY")?,
    );
    if arguments.next().is_some() {
        return Err("usage: create_image_pack NEW_DIRECTORY".into());
    }
    // Refuse an existing directory so example generation cannot overwrite art.
    std::fs::create_dir(&destination)?;
    let poses = [
        "default",
        "speaking",
        "listening",
        "thinking",
        "happy",
        "happy_speaking",
        "blink",
    ];
    let mut manifest = String::from(
        "schema_version = 1\nid = 'aiex.demo.friend'\nname = '蓝色伙伴示例'\nauthor = 'AIex'\nlicense = 'MIT'\n\n[images]\n",
    );
    for pose in poses {
        portrait(pose).save(destination.join(format!("{pose}.png")))?;
        manifest.push_str(&format!("{pose} = '{pose}.png'\n"));
    }
    std::fs::write(destination.join("appearance.toml"), manifest)?;
    println!("{}", destination.join("appearance.toml").display());
    Ok(())
}

fn portrait(pose: &str) -> RgbaImage {
    let mut image = RgbaImage::new(256, 320);
    let speaking = pose.ends_with("speaking");
    let happy = pose.starts_with("happy");
    let gaze = if pose == "thinking" { 6 } else { 0 };
    for y in 0..320_i32 {
        for x in 0..256_i32 {
            let ellipse = |cx: i32, cy: i32, rx: i32, ry: i32| {
                ((x - cx) as f32 / rx as f32).powi(2) + ((y - cy) as f32 / ry as f32).powi(2) <= 1.0
            };
            let mut color = [0, 0, 0, 0];
            if ellipse(128, 248, 43, 53) {
                color = [55, 83, 125, 255];
            }
            if ellipse(75, 77, 26, 26) || ellipse(181, 77, 26, 26) || ellipse(128, 130, 78, 78) {
                color = if pose == "listening" {
                    [103, 205, 183, 255]
                } else {
                    [126, 179, 246, 255]
                };
            }
            if ellipse(128, 131, 61, 61) {
                color = [244, 242, 234, 255];
            }
            let eyes = [103 + gaze, 153 + gaze].iter().any(|cx| {
                (x - cx).abs() <= 4
                    && (y - 120).abs() <= if pose == "blink" || happy { 2 } else { 9 }
            });
            let mouth = if speaking {
                ellipse(128, 158, 11, 16)
            } else {
                (x - 128).abs() <= 15 && (y - (157 - (x - 128).pow(2) / 38)).abs() <= 1
            };
            if eyes || mouth {
                color = [37, 48, 67, 255];
            }
            if happy && (ellipse(90, 145, 8, 4) || ellipse(166, 145, 8, 4)) {
                color = [243, 169, 168, 255];
            }
            image.put_pixel(x as u32, y as u32, Rgba(color));
        }
    }
    image
}
