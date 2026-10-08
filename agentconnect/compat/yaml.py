"""Read a v0.4 YAML Team file into a mapping.

This is the only module that imports PyYAML. Callers in
``agentconnect.config`` validate the mapping with ``TeamConfig``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    """Return the mapping stored in a YAML Team file.

    Args:
        path: Existing ``.yaml`` or ``.yml`` file.

    Returns:
        The document as a dict. An empty or null document becomes ``{}``.

    Raises:
        ValueError: PyYAML is missing, the file cannot be read, YAML is
            invalid, or the document is not a mapping.
    """
    try:
        import yaml
    except ImportError as exc:
        raise ValueError(
            f"PyYAML is required to load {path}. Install agentconnect[cli] "
            "or migrate the file to TOML."
        ) from exc
    try:
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in {path}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"could not read {path}: {exc}") from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a mapping")
    return data
