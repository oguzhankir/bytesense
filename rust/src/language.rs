use pyo3::prelude::*;
use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicU8, Ordering};

const BMP_LEN: usize = 1 << 16;
const INITIALIZED: u8 = 1;
const ALPHABETIC: u8 = 1 << 1;
const UNPRINTABLE: u8 = 1 << 2;
const SYMBOL: u8 = 1 << 3;
const KNOWN_LETTER: u8 = 1 << 4;

fn pair_key(a: char, b: char) -> u64 {
    ((a as u64) << 32) | b as u64
}

/// Immutable corpus statistics only. No input text is retained between calls.
#[pyclass(frozen)]
pub struct NgramModel {
    letters: HashSet<char>,
    pairs: HashMap<u64, f64>,
    latin_pairs: Box<[f64]>,
    max_pair_support: f64,
    // One byte per BMP scalar. Each atomic contains the complete property
    // record, so relaxed loads/stores need not publish any additional state.
    properties: Box<[AtomicU8]>,
}

impl NgramModel {
    #[inline]
    fn pair_support(&self, before: char, current: char) -> f64 {
        if before <= '\u{ff}' && current <= '\u{ff}' {
            self.latin_pairs[((before as usize) << 8) | current as usize]
        } else {
            self.pairs
                .get(&pair_key(before, current))
                .copied()
                .unwrap_or(0.0)
        }
    }
}

#[pymethods]
impl NgramModel {
    #[new]
    fn new(letters: &str, pairs: Vec<(String, f64)>) -> Self {
        // A bounded 512 KiB table avoids hashing common Latin/ASCII pairs.
        // It contains model weights only, independent of observed documents.
        let mut latin_pairs = vec![0.0; 256 * 256].into_boxed_slice();
        for (pair, weight) in &pairs {
            let mut chars = pair.chars();
            if let (Some(a), Some(b)) = (chars.next(), chars.next()) {
                if a <= '\u{ff}' && b <= '\u{ff}' {
                    latin_pairs[((a as usize) << 8) | b as usize] = *weight;
                }
            }
        }
        Self {
            latin_pairs,
            max_pair_support: pairs.iter().fold(1.0_f64, |m, (_, weight)| m.max(*weight)),
            properties: (0..BMP_LEN).map(|_| AtomicU8::new(0)).collect(),
            letters: letters.chars().collect(),
            pairs: pairs
                .iter()
                .filter_map(|(s, weight)| {
                    let mut chars = s.chars();
                    Some((pair_key(chars.next()?, chars.next()?), *weight))
                })
                .collect(),
        }
    }

    /// Cache bounded Unicode scalar metadata, never input strings or sequences.
    #[pyo3(signature = (raw, lower, classify, minimum=None))]
    fn quality(
        &self,
        py: Python<'_>,
        raw: &str,
        lower: &str,
        classify: &Bound<'_, PyAny>,
        minimum: Option<f64>,
    ) -> PyResult<Option<(f64, f64)>> {
        let unknown: HashSet<char> = raw
            .chars()
            .chain(lower.chars())
            .filter(|&c| {
                self.properties
                    .get(c as usize)
                    .is_none_or(|flags| flags.load(Ordering::Relaxed) == 0)
            })
            .collect();
        let chars: Vec<char> = unknown.into_iter().collect();
        let mut local = HashMap::new();
        if !chars.is_empty() {
            let values: Vec<(bool, bool, bool)> = classify
                .call1((chars.iter().collect::<String>(),))?
                .extract()?;
            if values.len() != chars.len() {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "one property record per scalar is required",
                ));
            }
            for (c, (alpha, bad, symbol)) in chars.into_iter().zip(values) {
                let flags = INITIALIZED
                    | if alpha { ALPHABETIC } else { 0 }
                    | if bad { UNPRINTABLE } else { 0 }
                    | if symbol { SYMBOL } else { 0 }
                    | if self.letters.contains(&c) {
                        KNOWN_LETTER
                    } else {
                        0
                    };
                if let Some(entry) = self.properties.get(c as usize) {
                    entry.store(flags, Ordering::Relaxed);
                } else {
                    local.insert(c, flags);
                }
            }
        }
        Ok(py.detach(|| {
            let flags = |c: char| {
                self.properties
                    .get(c as usize)
                    .map_or_else(|| local[&c], |entry| entry.load(Ordering::Relaxed))
            };
            let mut n = 0usize;
            let mut bad = 0usize;
            let mut symbols = 0usize;
            for c in raw.chars() {
                n += 1;
                let properties = flags(c);
                bad += usize::from(properties & UNPRINTABLE != 0);
                symbols += usize::from(properties & SYMBOL != 0);
            }
            let bad_ratio = bad as f64 / n.max(1) as f64;
            let penalty = 5.0 * bad_ratio + 3.0 * symbols as f64 / n.max(1) as f64;
            // An optimistic bound: even perfect letter/pair coverage cannot
            // recover this candidate. Keep slack for Python's score rounding.
            if minimum
                .is_some_and(|floor| 0.25 + 0.75 * self.max_pair_support - penalty + 1e-9 < floor)
            {
                return None;
            }
            let mut letter_count = 0usize;
            let mut known_letters = 0usize;
            let mut pair_weight = 0usize;
            let mut known_pair_weight = 0.0f64;
            let mut previous = None;
            for c in lower.chars() {
                let properties = flags(c);
                let current = if properties & ALPHABETIC != 0 { c } else { ' ' };
                if current != ' ' {
                    letter_count += 1;
                    known_letters += usize::from(properties & KNOWN_LETTER != 0);
                }
                if let Some(before) = previous {
                    if before != ' ' || current != ' ' {
                        let weight = if before > '\u{7f}' || current > '\u{7f}' {
                            4
                        } else {
                            1
                        };
                        pair_weight += weight;
                        known_pair_weight += weight as f64 * self.pair_support(before, current);
                    }
                }
                previous = Some(current);
            }
            Some((
                0.25 * known_letters as f64 / letter_count.max(1) as f64
                    + 0.75 * known_pair_weight / pair_weight.max(1) as f64
                    - 5.0 * bad_ratio
                    - 3.0 * symbols as f64 / n.max(1) as f64,
                bad_ratio,
            ))
        }))
    }

    /// Input is normalized by Python using the interpreter's Unicode tables.
    fn score(&self, py: Python<'_>, text: &str, bad: f64, symbols: f64) -> f64 {
        py.detach(|| {
            let mut letter_count = 0usize;
            let mut known_letters = 0usize;
            let mut pair_weight = 0usize;
            let mut known_pair_weight = 0.0f64;
            let mut previous = None;
            for current in text.chars() {
                if current != ' ' {
                    letter_count += 1;
                    if self.letters.contains(&current) {
                        known_letters += 1;
                    }
                }
                if let Some(before) = previous {
                    if before != ' ' || current != ' ' {
                        let weight = if before > '\u{7f}' || current > '\u{7f}' {
                            4
                        } else {
                            1
                        };
                        pair_weight += weight;
                        known_pair_weight += weight as f64 * self.pair_support(before, current);
                    }
                }
                previous = Some(current);
            }
            0.25 * known_letters as f64 / letter_count.max(1) as f64
                + 0.75 * known_pair_weight / pair_weight.max(1) as f64
                - 5.0 * bad
                - 3.0 * symbols
        })
    }
}
