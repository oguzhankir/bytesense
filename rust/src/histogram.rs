/// Byte frequency histogram — 8-way loop unrolling for auto-vectorisation.
pub fn byte_histogram(data: &[u8]) -> [u64; 256] {
    let mut h = [0u64; 256];
    let (chunks, rem) = data.as_chunks::<8>();
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
    data.iter().filter(|b| (0x80..=0x9F).contains(*b)).count() as f64 / data.len() as f64
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn histogram_conserves_all_bytes_and_remainders() {
        for length in [0, 1, 7, 8, 9, 1_048_579] {
            let data: Vec<u8> = (0..length).map(|i| (i % 256) as u8).collect();
            let h = byte_histogram(&data);
            assert_eq!(h.iter().sum::<u64>(), length as u64);
            for (byte, count) in h.iter().enumerate() {
                assert_eq!(
                    *count,
                    (length / 256 + usize::from(byte < length % 256)) as u64
                );
            }
        }
    }
}
