/// Byte frequency histogram — 8-way loop unrolling for auto-vectorisation.
pub fn byte_histogram(data: &[u8]) -> [u32; 256] {
    let mut h = [0u32; 256];
    let chunks = data.chunks_exact(8);
    let rem = chunks.remainder();
    for c in chunks {
        h[c[0] as usize] += 1;
        h[c[1] as usize] += 1;
        h[c[2] as usize] += 1;
        h[c[3] as usize] += 1;
        h[c[4] as usize] += 1;
        h[c[5] as usize] += 1;
        h[c[6] as usize] += 1;
        h[c[7] as usize] += 1;
    }
    for &b in rem {
        h[b as usize] += 1;
    }
    h
}

pub fn high_byte_ratio(data: &[u8]) -> f64 {
    if data.is_empty() {
        return 0.0;
    }
    data.iter().filter(|b| **b >= 0x80).count() as f64 / data.len() as f64
}

pub fn null_byte_ratio(data: &[u8]) -> f64 {
    if data.is_empty() {
        return 0.0;
    }
    data.iter().filter(|b| **b == 0).count() as f64 / data.len() as f64
}

pub fn cp1252_zone_ratio(data: &[u8]) -> f64 {
    if data.is_empty() {
        return 0.0;
    }
    data.iter()
        .filter(|b| (0x80..=0x9F).contains(*b))
        .count() as f64
        / data.len() as f64
}
