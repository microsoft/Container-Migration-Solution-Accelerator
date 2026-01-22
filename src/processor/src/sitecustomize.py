# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Runtime compatibility hooks.

Python automatically imports `sitecustomize` (if present on `sys.path`) during
startup. We use this to patch the upstream `agent_framework` namespace package
without adding a local `agent_framework/__init__.py` (which can interfere with
package discovery and loading).

Why this is needed:
- Some versions of the `agent-framework` distribution ship `agent_framework` as a
  namespace package (no `__init__.py`), but submodules expect `agent_framework`
  to expose `__version__`, and this repo imports many public APIs from the
  top-level module.

This file:
- Injects `agent_framework.__version__` from package metadata when missing.
- Adds a lazy `__getattr__` re-exporter so `from agent_framework import ChatAgent`
  continues to work.
"""

from __future__ import annotations

from importlib import import_module

try:
    from importlib.metadata import PackageNotFoundError, version
except Exception:  # pragma: no cover
    from importlib_metadata import PackageNotFoundError, version  # type: ignore

from typing import Any


def _patch_agent_framework() -> None:
    try:
        import agent_framework  # type: ignore
    except Exception:
        # If the dependency isn't installed, do nothing.
        return

    # Ensure __version__ exists for submodules that import it.
    if not hasattr(agent_framework, "__version__"):
        try:
            agent_framework.__version__ = version("agent-framework")
        except PackageNotFoundError:
            agent_framework.__version__ = "0.0.0"

    export_modules: tuple[str, ...] = (
        "agent_framework._agents",
        "agent_framework._clients",
        "agent_framework._memory",
        "agent_framework._middleware",
        "agent_framework._mcp",
        "agent_framework._threads",
        "agent_framework._tools",
        "agent_framework._types",
        "agent_framework._workflows",
    )

    def __getattr__(name: str) -> Any:  # noqa: ANN401
        if name.startswith("__"):
            raise AttributeError(name)

        for module_name in export_modules:
            module = import_module(module_name)
            if hasattr(module, name):
                value = getattr(module, name)
                setattr(agent_framework, name, value)
                return value

        raise AttributeError(name)

    def __dir__() -> list[str]:
        names = set(dir(agent_framework))
        for module_name in export_modules:
            try:
                module = import_module(module_name)
            except Exception:
                continue
            names.update(getattr(module, "__all__", []))
            names.update(dir(module))
        return sorted(names)

    # Attach as module attributes so `from agent_framework import X` can resolve.
    agent_framework.__getattr__ = __getattr__  # type: ignore[attr-defined]
    agent_framework.__dir__ = __dir__  # type: ignore[attr-defined]


_patch_agent_framework()
