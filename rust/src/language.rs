use pyo3::prelude::*;
use std::collections::{HashMap, HashSet};
use std::sync::RwLock;

/// Immutable corpus statistics only. No input text is retained between calls.
#[pyclass(frozen)]
pub struct NgramModel {
    letters: HashSet<char>,
    pairs: HashMap<(char, char), f64>,
    properties: RwLock<HashMap<char, (bool, bool, bool)>>,
}

#[pymethods]
impl NgramModel {
    #[new]
    fn new(letters: &str, pairs: Vec<(String, f64)>) -> Self {
        Self {
            properties: RwLock::new(HashMap::new()),
            letters: letters.chars().collect(),
            pairs: pairs
                .iter()
                .filter_map(|(s, weight)| {
                    let mut chars = s.chars();
                    Some(((chars.next()?, chars.next()?), *weight))
                })
                .collect(),
        }
    }

    /// Cache bounded Unicode scalar metadata, never input strings or sequences.
    fn quality(
        &self,
        py: Python<'_>,
        raw: &str,
        lower: &str,
        classify: &Bound<'_, PyAny>,
    ) -> PyResult<(f64, f64)> {
        let unknown: HashSet<char> = {
            let properties = self.properties.read().unwrap();
            raw.chars()
                .chain(lower.chars())
                .filter(|c| !properties.contains_key(c))
                .collect()
        };
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
            let mut properties = self.properties.write().unwrap();
            for (c, flags) in chars.into_iter().zip(values) {
                // BMP cache has at most 65,536 entries. Other scalars are local.
                if c <= '\u{ffff}' {
                    properties.insert(c, flags);
                } else {
                    local.insert(c, flags);
                }
            }
        }
        Ok(py.detach(|| {
            let properties = self.properties.read().unwrap();
            let flags = |c: &char| properties.get(c).or_else(|| local.get(c)).unwrap();
            let mut n = 0usize;
            let mut bad = 0usize;
            let mut symbols = 0usize;
            for c in raw.chars() {
                n += 1;
                let (_, unprintable, symbol) = flags(&c);
                bad += usize::from(*unprintable);
                symbols += usize::from(*symbol);
            }
            let mut letter_count = 0usize;
            let mut known_letters = 0usize;
            let mut pair_weight = 0usize;
            let mut known_pair_weight = 0.0f64;
            let mut previous = None;
            for c in lower.chars() {
                let current = if flags(&c).0 { c } else { ' ' };
                if current != ' ' {
                    letter_count += 1;
                    known_letters += usize::from(self.letters.contains(&current));
                }
                if let Some(before) = previous {
                    if before != ' ' || current != ' ' {
                        let weight = if before > '\u{7f}' || current > '\u{7f}' {
                            4
                        } else {
                            1
                        };
                        pair_weight += weight;
                        if let Some(support) = self.pairs.get(&(before, current)) {
                            known_pair_weight += weight as f64 * support;
                        }
                    }
                }
                previous = Some(current);
            }
            let bad_ratio = bad as f64 / n.max(1) as f64;
            (
                0.25 * known_letters as f64 / letter_count.max(1) as f64
                    + 0.75 * known_pair_weight / pair_weight.max(1) as f64
                    - 5.0 * bad_ratio
                    - 3.0 * symbols as f64 / n.max(1) as f64,
                bad_ratio,
            )
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
                        if let Some(support) = self.pairs.get(&(before, current)) {
                            known_pair_weight += weight as f64 * support;
                        }
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
