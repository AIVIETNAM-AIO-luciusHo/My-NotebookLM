"""
conftest.py — pytest fixtures and sys.modules safety net.

If ragas, datasets, or langchain packages are not yet installed (e.g. in a
bare CI environment), this file injects lightweight MagicMock stand-ins so
test collection does not fail with ImportError.  When the real packages are
installed, this file is effectively a no-op.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock


def _install_mock_module(name: str) -> MagicMock:
    """Register a MagicMock as *name* in sys.modules and return it."""
    mock = MagicMock(name=name)
    sys.modules[name] = mock
    return mock


def pytest_configure(config: object) -> None:  # noqa: ARG001
    """
    Called once before test collection begins.

    For each heavy dependency that is absent, install a mock so that
    `import ragas` (and friends) inside evaluate_rag.py will not raise
    ModuleNotFoundError during import.
    """
    _HEAVY_PACKAGES = [
        "ragas",
        "ragas.metrics",
        "ragas.llms",
        "ragas.embeddings",
        "datasets",
    ]
    for pkg in _HEAVY_PACKAGES:
        if pkg not in sys.modules:
            try:
                __import__(pkg)
            except ModuleNotFoundError:
                _install_mock_module(pkg)

    _LANGCHAIN_PACKAGES = [
        "langchain_community",
        "langchain_community.chat_models",
        "langchain_huggingface",
    ]
    for pkg in _LANGCHAIN_PACKAGES:
        if pkg not in sys.modules:
            try:
                __import__(pkg)
            except ModuleNotFoundError:
                _install_mock_module(pkg)
