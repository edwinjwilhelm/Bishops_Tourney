from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Optional


ROOT_DIR = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT_DIR / "bishops_settings.json"

DEFAULT_VARIANT = "golden"
VALID_VARIANTS = {"golden", "egg"}

ENGINE_FILES = {
    "golden": ROOT_DIR / "Bishops_Golden.py",
    "egg": ROOT_DIR / "Bishops_Golden_egg.py",
}

HARD_CODED_GOLDEN = ROOT_DIR / "spares" / "Bishops_Golden.py"


@dataclass
class EngineHandle:
    variant: str
    module: ModuleType
    path: Path


def _read_settings_variant() -> Optional[str]:
    try:
        if not SETTINGS_PATH.is_file():
            return None
        data = SETTINGS_PATH.read_text(encoding="utf-8")
        import json

        payload = json.loads(data)
        variant = payload.get("engine_variant")
        if isinstance(variant, str):
            return variant.lower()
    except Exception:
        return None
    return None


def resolve_variant(preferred: Optional[str] = None) -> str:
    if preferred:
        choice = preferred.lower()
        if choice in VALID_VARIANTS:
            return choice
        raise ValueError(f"Unknown engine variant '{preferred}'. Valid: {sorted(VALID_VARIANTS)}")
    env_val = os.environ.get("BISHOPS_ENGINE")
    if env_val:
        choice = env_val.strip().lower()
        if choice in VALID_VARIANTS:
            return choice
    settings_variant = _read_settings_variant()
    if settings_variant in VALID_VARIANTS:
        return settings_variant  # type: ignore[return-value]
    return DEFAULT_VARIANT


def _import_from_path(path: Path, module_name: str, force_reload: bool) -> ModuleType:
    if force_reload and module_name in sys.modules:
        sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load engine from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _syntax_is_clean(path: Path) -> bool:
    """Return True if the file exists and compiles without SyntaxError."""
    if not path.is_file():
        print(f"[EngineLoader] Missing engine file: {path}")
        return False
    try:
        with tokenize.open(str(path)) as handle:
            source = handle.read()
        compile(source, str(path), "exec")
    except Exception as exc:
        print(f"[EngineLoader] Syntax check failed for {path}: {exc}")
        return False
    return True


def _resolve_golden_path() -> Path:
    """Prefer the known-good golden engine; fall back if the primary is broken."""
    candidates = []
    candidates.append(ENGINE_FILES["golden"])
    if HARD_CODED_GOLDEN.exists():
        candidates.append(HARD_CODED_GOLDEN)
    print(f"[EngineLoader] Golden candidates: {candidates}")
    for candidate in candidates:
        if _syntax_is_clean(candidate):
            if candidate == HARD_CODED_GOLDEN:
                print("[EngineLoader] Using fallback golden engine from spares/Bishops_Golden.py")
            else:
                print("[EngineLoader] Using primary golden engine from Bishops_Golden.py")
            return candidate
    raise RuntimeError(
        "Unable to locate a syntax-valid Bishops_Golden.py. "
        "Both the hard-coded backup and the primary copy failed compilation."
    )


def load_engine(
    preferred_variant: Optional[str] = None,
    *,
    force_reload: bool = False,
) -> EngineHandle:
    variant = resolve_variant(preferred_variant)
    if variant == "golden":
        resolved_path = _resolve_golden_path()
        module = _import_from_path(resolved_path, "bishops_engine", force_reload)
        version = getattr(module, "__FILE_VERSION__", "unknown")
        print(f"[EngineLoader] Loaded {resolved_path} (version={version})")
    elif variant == "egg":
        module_name = "Bishops_Golden_egg"
        if force_reload and module_name in sys.modules:
            module = importlib.reload(sys.modules[module_name])
        else:
            module = importlib.import_module(module_name)
        resolved_path = Path(getattr(module, "__file__", ENGINE_FILES["egg"])).resolve()
    else:
        raise ValueError(f"Unsupported engine variant '{variant}'")
    return EngineHandle(variant=variant, module=module, path=resolved_path)


__all__ = [
    "EngineHandle",
    "DEFAULT_VARIANT",
    "ENGINE_FILES",
    "load_engine",
    "resolve_variant",
    "VALID_VARIANTS",
]
