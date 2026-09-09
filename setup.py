"""Build native wheels when requested; source installs also work without Rust."""

import os
import platform
import shutil
import sysconfig

from setuptools import setup
from setuptools_rust import Binding, RustExtension

mode = os.environ.get("BYTESENSE_BUILD_RUST", "auto")
if mode not in {"auto", "0", "1"}:
    raise ValueError("BYTESENSE_BUILD_RUST must be auto, 0 or 1")
native_supported = platform.python_implementation() == "CPython" and not sysconfig.get_config_var(
    "Py_GIL_DISABLED"
)
if mode == "1" and not native_supported:
    raise RuntimeError("Native builds require a GIL-enabled CPython interpreter")
native = native_supported and (
    mode == "1" or (mode == "auto" and shutil.which("cargo") is not None)
)
setup(
    rust_extensions=[
        RustExtension(
            "bytesense._rust_core",
            path="rust/Cargo.toml",
            binding=Binding.PyO3,
            optional=mode != "1",
            py_limited_api=True,
            debug=False,
        )
    ]
    if native
    else [],
    options={"bdist_wheel": {"py_limited_api": "cp39"}} if native else {},
    zip_safe=False,
)
