"""
config_lib.py
─────────────
Lightweight JSON-backed configuration store.

Usage
-----
    from config_lib import Config

    cfg = Config("farmauto_config.json")   # path relative to CWD or absolute
    cfg.set("hoe_slot", 3)
    cfg.save()

    cfg2 = Config("farmauto_config.json")
    print(cfg2.get("hoe_slot"))            # → 3

The Config object also supports attribute-style access:

    cfg.hoe_slot = 3
    print(cfg.hoe_slot)                    # → 3

Any key that starts with "_" is treated as private and is never persisted.
"""

import json
import os


class Config:
    """
    A simple JSON-backed key-value store with dot-attribute access.

    Parameters
    ----------
    filepath : str
        Path to the JSON file (created automatically on first save).
    defaults : dict | None
        Optional mapping of default values.  These are applied only when a
        key is not already present in the loaded file.
    auto_load : bool
        If True (default) the file is loaded immediately on construction.
    """

    # Keys in this set are never written to disk.
    _PRIVATE_PREFIX = "_"

    def __init__(
        self,
        filepath: str,
        defaults: dict | None = None,
        auto_load: bool = True,
    ) -> None:
        # Store internal attributes directly in __dict__ to bypass __setattr__
        object.__setattr__(self, "_filepath", filepath)
        object.__setattr__(self, "_data", {})

        if defaults:
            self._data.update(defaults)

        if auto_load and os.path.isfile(filepath):
            self.load()

    # ------------------------------------------------------------------ #
    # Persistence                                                           #
    # ------------------------------------------------------------------ #

    def load(self) -> None:
        """Load (or reload) the JSON file into the internal store."""
        try:
            with open(self._filepath, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                self._data.update(loaded)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[Config] Warning: could not load '{self._filepath}': {exc}")

    def save(self) -> None:
        """Persist the current store to the JSON file."""
        # Filter out private keys
        to_write = {
            k: v
            for k, v in self._data.items()
            if not k.startswith(self._PRIVATE_PREFIX)
        }
        try:
            dirpath = os.path.dirname(self._filepath)
            if dirpath:
                os.makedirs(dirpath, exist_ok=True)
            with open(self._filepath, "w", encoding="utf-8") as fh:
                json.dump(to_write, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            print(f"[Config] Error: could not save '{self._filepath}': {exc}")

    # ------------------------------------------------------------------ #
    # Key/value API                                                         #
    # ------------------------------------------------------------------ #

    def get(self, key: str, default=None):
        """Return the value for *key*, or *default* if absent."""
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        """Store *value* under *key*."""
        self._data[key] = value

    def delete(self, key: str) -> None:
        """Remove *key* from the store (no-op if missing)."""
        self._data.pop(key, None)

    def has(self, key: str) -> bool:
        """Return True if *key* exists in the store."""
        return key in self._data

    def all(self) -> dict:
        """Return a shallow copy of the entire store."""
        return dict(self._data)

    def update(self, mapping: dict) -> None:
        """Merge *mapping* into the store (like dict.update)."""
        self._data.update(mapping)

    def clear(self) -> None:
        """Remove all keys from the store (does not touch the file)."""
        self._data.clear()

    # ------------------------------------------------------------------ #
    # Attribute-style access                                                #
    # ------------------------------------------------------------------ #

    def __getattr__(self, name: str):
        # Only called when normal attribute lookup fails
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(
                f"[Config] No key '{name}' in '{self._filepath}'"
            ) from None

    def __setattr__(self, name: str, value) -> None:
        if name.startswith("_"):
            # Private attributes → stored on the object itself
            object.__setattr__(self, name, value)
        else:
            self._data[name] = value

    def __delattr__(self, name: str) -> None:
        if name.startswith("_"):
            object.__delattr__(self, name)
        else:
            self._data.pop(name, None)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"Config('{self._filepath}', {self._data!r})"
