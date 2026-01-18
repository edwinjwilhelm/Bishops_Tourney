"""
Export a machine-readable manifest from Bishops_Golden.py and update engine_manifest.json.
Run with your Python interpreter. Keeps the manifest next to the Golden file.
"""
from __future__ import annotations
import json
import os
import importlib.util
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ROOT)  # go up to c:\Bishops_chatGPT
ENGINE_PATH = os.path.join(ROOT, 'Bishops_Golden.py')
MANIFEST_PATH = os.path.join(ROOT, 'engine_manifest.json')


def _load_engine(path: str):
    # Prevent pygame/SDL from trying to open a window when importing the engine
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    spec = importlib.util.spec_from_file_location('bg_engine', path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def _get_attr(mod, name, default=None):
    return getattr(mod, name, default)


def main():
    mod = _load_engine(ENGINE_PATH)
    # core constants
    BOARD_SIZE = _get_attr(mod, 'BOARD_SIZE')
    CH_MIN = _get_attr(mod, 'CH_MIN')
    CH_MAX = _get_attr(mod, 'CH_MAX')
    LIGHT = _get_attr(mod, 'LIGHT')
    DARK = _get_attr(mod, 'DARK')
    TURN_ORDER = [c.name for c in _get_attr(mod, 'TURN_ORDER')]
    PLAYER_COLORS = _get_attr(mod, 'PLAYER_COLORS', None)
    CORNERS = _get_attr(mod, 'KING_CORNER_TL', None)
    VERSION = _get_attr(mod, '__FILE_VERSION__', 'unknown')

    # derive corner coordinates if not directly exposed
    if CORNERS is None:
        # the engine uses functions/logic; replicate the known mapping
        CORNERS = {
            'GREY': (0, 0),
            'BLACK': (0, BOARD_SIZE-2),
            'WHITE': (BOARD_SIZE-2, 0),
            'PINK': (BOARD_SIZE-2, BOARD_SIZE-2),
        }

    manifest = {
        'version': VERSION,
        'generatedAt': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'board': {
            'BOARD_SIZE': int(BOARD_SIZE),
            'CH_MIN': int(CH_MIN),
            'CH_MAX': int(CH_MAX),
            'corners': CORNERS,
        },
        'colors': {
            'LIGHT': list(LIGHT),
            'DARK': list(DARK),
            'players': {k.name if hasattr(k, 'name') else k: list(v) for k, v in getattr(mod, 'PLAYER_COLORS', {}).items()} if PLAYER_COLORS else {
                'WHITE': [255,255,255], 'GREY':[160,160,160], 'BLACK':[0,0,0], 'PINK':[255,105,180]
            }
        },
        'turnOrder': TURN_ORDER,
        'rules': {
            'edgePawnFirstRoundCapture': True,
            'twoStageMigration': {
                'enabled': True,
                'purgeOutside8x8': True,
                'kingsMustEnter': True,
                'chessLockAfterFullMigration': True
            },
            'finalsOrientationGreyPink': True
        }
    }

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    print(f"Updated {MANIFEST_PATH}")


if __name__ == '__main__':
    main()
