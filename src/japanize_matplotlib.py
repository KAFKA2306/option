"""Minimal Japanese font configuration without the legacy distutils dependency.

This module intentionally provides the small import surface used by this
repository. It replaces the third-party package at runtime when ``src`` is on
``sys.path`` and degrades safely when no Japanese font is installed.
"""
from __future__ import annotations

from pathlib import Path

from matplotlib import font_manager, rcParams

_FONT_CANDIDATES = (
    "Noto Sans CJK JP",
    "Noto Sans JP",
    "IPAexGothic",
    "IPAGothic",
    "Yu Gothic",
    "Hiragino Sans",
)


def japanize() -> str | None:
    """Select the first installed Japanese-capable font, if available."""
    installed = {font.name for font in font_manager.fontManager.ttflist}
    selected = next((name for name in _FONT_CANDIDATES if name in installed), None)
    if selected is not None:
        rcParams["font.family"] = selected
    rcParams["axes.unicode_minus"] = False
    return selected


def get_font_path() -> str | None:
    """Return the configured font file path when one can be resolved."""
    selected = japanize()
    if selected is None:
        return None
    path = font_manager.findfont(selected, fallback_to_default=False)
    return str(Path(path))


def get_font_ttf_path() -> str | None:
    """Compatibility alias used by the original package."""
    return get_font_path()


japanize()
