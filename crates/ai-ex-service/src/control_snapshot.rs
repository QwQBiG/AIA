use std::io::{self, Write};

use ai_ex_observability::RuntimeSnapshot;

const SNAPSHOT_BYTES: usize = 8 * 1024;

/// Keep control replies within their transport budget without changing event identity.
pub(super) fn bounded(mut snapshot: RuntimeSnapshot) -> RuntimeSnapshot {
    if snapshot_size(&snapshot).is_some() {
        return snapshot;
    }
    let fault = snapshot.last_fault.as_mut().map(std::mem::take);
    let playback = std::mem::take(&mut snapshot.playback.text);
    let available =
        SNAPSHOT_BYTES.saturating_sub(snapshot_size(&snapshot).unwrap_or(SNAPSHOT_BYTES));
    if let Some(fault) = fault {
        let share = if playback.is_empty() {
            available
        } else {
            available / 2
        };
        snapshot.last_fault = Some(fit_text(fault, share));
    }
    let remaining =
        SNAPSHOT_BYTES.saturating_sub(snapshot_size(&snapshot).unwrap_or(SNAPSHOT_BYTES));
    snapshot.playback.text = fit_text(playback, remaining);
    snapshot
}

fn snapshot_size(snapshot: &RuntimeSnapshot) -> Option<usize> {
    let mut writer = ByteBudget::new(SNAPSHOT_BYTES);
    serde_json::to_writer(&mut writer, snapshot).ok()?;
    Some(writer.used)
}

fn text_fits(text: &str, content_bytes: usize) -> bool {
    // Empty JSON strings already occupy two bytes in the measured snapshot metadata.
    serde_json::to_writer(&mut ByteBudget::new(content_bytes + 2), text).is_ok()
}

fn fit_text(mut text: String, content_bytes: usize) -> String {
    if text_fits(&text, content_bytes) {
        return text;
    }
    const MARKER: &str = "…";
    if content_bytes < MARKER.len() {
        return String::new();
    }
    let prefix_bytes = content_bytes - MARKER.len();
    let mut low = 0;
    let mut high = text.len().min(prefix_bytes);
    while low < high {
        let middle = low + (high - low).div_ceil(2);
        let end = char_boundary(&text, middle);
        if text_fits(&text[..end], prefix_bytes) {
            low = middle;
        } else {
            high = middle - 1;
        }
    }
    text.truncate(char_boundary(&text, low));
    text.push_str(MARKER);
    text
}

fn char_boundary(text: &str, mut index: usize) -> usize {
    while !text.is_char_boundary(index) {
        index -= 1;
    }
    index
}

struct ByteBudget {
    used: usize,
    limit: usize,
}

impl ByteBudget {
    fn new(limit: usize) -> Self {
        Self { used: 0, limit }
    }
}

impl Write for ByteBudget {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        if bytes.len() > self.limit.saturating_sub(self.used) {
            return Err(io::Error::other("control snapshot byte budget exceeded"));
        }
        self.used += bytes.len();
        Ok(bytes.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

#[cfg(test)]
#[path = "control_snapshot_tests.rs"]
mod tests;
