/// Returns (is_valid, confidence_0_to_1).
pub fn utf8_check(data: &[u8]) -> (bool, f64) {
    match std::str::from_utf8(data) {
        Ok(_) => (true, 1.0),
        Err(e) => {
            let conf = if data.is_empty() {
                0.0
            } else {
                e.valid_up_to() as f64 / data.len() as f64
            };
            (false, conf)
        }
    }
}

/// UTF-8 multibyte continuation pattern score (0.0 – 1.0).
pub fn utf8_continuation_score(data: &[u8]) -> f64 {
    let mut valid: u32 = 0;
    let mut invalid: u32 = 0;
    let mut i = 0;
    while i < data.len() {
        let b = data[i];
        if b < 0x80 {
            i += 1;
            continue;
        }
        let seq = if (0xC2..=0xDF).contains(&b) {
            2
        } else if (0xE0..=0xEF).contains(&b) {
            3
        } else if (0xF0..=0xF4).contains(&b) {
            4
        } else {
            invalid += 1;
            i += 1;
            continue;
        };
        if i + seq > data.len() {
            invalid += 1;
            i += 1;
            continue;
        }
        if data[i + 1..i + seq].iter().all(|&b| (0x80..=0xBF).contains(&b)) {
            valid += 1;
            i += seq;
        } else {
            invalid += 1;
            i += 1;
        }
    }
    let total = valid + invalid;
    if total == 0 {
        0.0
    } else {
        valid as f64 / total as f64
    }
}

/// Detect null-byte pattern.  Returns 0=none, 16=utf16be, -16=utf16le, 32=utf32be, -32=utf32le.
pub fn detect_null_pattern(data: &[u8]) -> i32 {
    if data.len() < 8 {
        return 0;
    }
    let s = &data[..data.len().min(512)];
    let n = s.len();

    let be32 = (0..n.saturating_sub(3))
        .step_by(4)
        .filter(|&i| s[i] == 0 && s[i + 1] == 0 && s[i + 2] == 0 && s[i + 3] != 0)
        .count();
    if be32 > n / 8 {
        return 32;
    }

    let le32 = (0..n.saturating_sub(3))
        .step_by(4)
        .filter(|&i| s[i] != 0 && s[i + 1] == 0 && s[i + 2] == 0 && s[i + 3] == 0)
        .count();
    if le32 > n / 8 {
        return -32;
    }

    let be16 = (0..n.saturating_sub(1))
        .step_by(2)
        .filter(|&i| s[i] == 0 && s[i + 1] != 0)
        .count();
    if be16 > n / 4 {
        return 16;
    }

    let le16 = (0..n.saturating_sub(1))
        .step_by(2)
        .filter(|&i| s[i] != 0 && s[i + 1] == 0)
        .count();
    if le16 > n / 4 {
        return -16;
    }

    0
}
