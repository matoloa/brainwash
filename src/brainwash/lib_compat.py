"""Redirect deprecated ``lib.*`` imports to ``brainwash.*``."""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys


class _AliasLoader(importlib.abc.Loader):
    def __init__(self, target_name: str):
        self._target_name = target_name

    def create_module(self, spec):
        return None

    def exec_module(self, module) -> None:
        target = importlib.import_module(self._target_name)
        module.__dict__.update(target.__dict__)
        module.__package__ = "lib" if module.__name__ == "lib" else module.__name__.rpartition(".")[0]
        if getattr(target, "__path__", None) is not None:
            module.__path__ = target.__path__  # type: ignore[attr-defined]
        sys.modules[module.__name__] = module


class _LibImportAlias(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname != "lib" and not fullname.startswith("lib."):
            return None
        target_name = "brainwash" + fullname[3:]
        target_spec = importlib.util.find_spec(target_name)
        if target_spec is None:
            return None
        return importlib.util.spec_from_loader(
            fullname,
            _AliasLoader(target_name),
            origin=target_spec.origin,
            is_package=target_spec.submodule_search_locations is not None,
        )


def install_lib_import_alias() -> None:
    for finder in sys.meta_path:
        if isinstance(finder, _LibImportAlias):
            return
    sys.meta_path.insert(0, _LibImportAlias())