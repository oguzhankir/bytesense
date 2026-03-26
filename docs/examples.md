# Examples

Runnable scripts live in the repository under [`examples/`](https://github.com/oguzhankir/bytesense/tree/main/examples). Install bytesense (`pip install bytesense` or `pip install -e .` from a checkout), then run e.g. `python examples/basic_detect.py` from the repo root.

## Basic detection (`from_bytes`, `from_path`)

```python
--8<-- "examples/basic_detect.py"
```

## Chardet-style `detect()` dict

```python
--8<-- "examples/chardet_compat.py"
```

## Streaming chunks (`StreamDetector`)

```python
--8<-- "examples/streaming.py"
```

## Mojibake repair

```python
--8<-- "examples/repair_mojibake.py"
```

## HTTP + HTML/XML hints

```python
--8<-- "examples/http_hints.py"
```

## Multi-encoding documents

```python
--8<-- "examples/multi_encoding.py"
```
