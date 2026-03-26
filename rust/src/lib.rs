use pyo3::prelude::*;
use pyo3::types::PyBytes;

mod histogram;
mod utf8;

#[pyfunction]
fn byte_histogram(data: &Bound<'_, PyBytes>) -> Vec<u32> {
    histogram::byte_histogram(data.as_bytes()).to_vec()
}

#[pyfunction]
fn utf8_check(data: &Bound<'_, PyBytes>) -> (bool, f64) {
    utf8::utf8_check(data.as_bytes())
}

#[pyfunction]
fn utf8_continuation_score(data: &Bound<'_, PyBytes>) -> f64 {
    utf8::utf8_continuation_score(data.as_bytes())
}

#[pyfunction]
fn high_byte_ratio(data: &Bound<'_, PyBytes>) -> f64 {
    histogram::high_byte_ratio(data.as_bytes())
}

#[pyfunction]
fn null_byte_ratio(data: &Bound<'_, PyBytes>) -> f64 {
    histogram::null_byte_ratio(data.as_bytes())
}

#[pyfunction]
fn cp1252_zone_ratio(data: &Bound<'_, PyBytes>) -> f64 {
    histogram::cp1252_zone_ratio(data.as_bytes())
}

#[pyfunction]
fn detect_null_pattern(data: &Bound<'_, PyBytes>) -> i32 {
    utf8::detect_null_pattern(data.as_bytes())
}

#[pymodule]
fn _rust_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(byte_histogram, m)?)?;
    m.add_function(wrap_pyfunction!(utf8_check, m)?)?;
    m.add_function(wrap_pyfunction!(utf8_continuation_score, m)?)?;
    m.add_function(wrap_pyfunction!(high_byte_ratio, m)?)?;
    m.add_function(wrap_pyfunction!(null_byte_ratio, m)?)?;
    m.add_function(wrap_pyfunction!(cp1252_zone_ratio, m)?)?;
    m.add_function(wrap_pyfunction!(detect_null_pattern, m)?)?;
    Ok(())
}
