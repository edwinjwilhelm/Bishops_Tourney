import asyncio
import json
import os
import datetime
import time
import io
import random
import re
import socket
import subprocess
import threading
import sqlite3
from typing import Any, Dict, List, Optional


class RoomFullError(Exception):
    def __init__(self, room_id: str):
        self.room_id = room_id
        super().__init__(f"Room '{room_id}' is full")


class SeatTakenError(Exception):
    def __init__(self, seat: str):
        self.seat = seat
        super().__init__(f"Seat '{seat}' is already taken")


class UserRequiredError(Exception):
    pass

class UserInUseError(Exception):
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"user '{user_id}' already connected")

class SeatCountMismatchError(Exception):
    pass

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel, Field

from . import engine_adapter_v3 as _adapter
from .engine_adapter_v3 import create_engine
# Import Supabase auth helper (placed alongside server_v3.py on the server)
try:
    from supabase_auth import get_user_id
except Exception:
    # Fallback for package import if needed
    from .supabase_auth import get_user_id  # type: ignore
try:
    import qrcode
    from PIL import Image
except Exception:
    qrcode = None
    Image = None

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
# Expose original piece assets for the web client
WORKSPACE_ROOT = os.path.dirname(BASE_DIR)
PROFILE_DB = os.path.join(BASE_DIR, 'netplay.db')
ASSET_DIR = os.path.join(WORKSPACE_ROOT, 'pieces')
if os.path.isdir(ASSET_DIR):
    app.mount('/assets', StaticFiles(directory=ASSET_DIR), name='assets')
GAMES_DIR = os.path.join(WORKSPACE_ROOT, 'games')
os.makedirs(GAMES_DIR, exist_ok=True)
SETTINGS_PATH = os.path.join(BASE_DIR, 'server_settings.json')

# Serve engine_manifest.json from workspace root
ENGINE_MANIFEST = os.path.join(WORKSPACE_ROOT, 'engine_manifest.json')

# Color seats supported by the UI
COLOR_SEATS = ("WHITE", "GREY", "BLACK", "PINK")

DEFAULT_ROOM_ID = "main"
_ROOM_SLUG_RE = re.compile(r"[^a-z0-9]+")
AUTO_ROOM_PREFIX = "table"
MAX_AUTO_ROOMS = 10
AUTO_ROOM_SENTINEL = "auto"
_USER_ID_RE = re.compile(r"[^a-zA-Z0-9_-]+")
AUTH_HEADER = "authorization"
TURN_SECONDS_DEFAULT = 90
TURN_GRACE_SECONDS_DEFAULT = 5
AI_ENABLED = False

def _extract_bearer_token(request: Request) -> str:
    auth = request.headers.get(AUTH_HEADER)
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    return auth.split(" ", 1)[1].strip()

def _ensure_profile_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        "create table if not exists profiles ("
        "user_id text primary key, "
        "display_name text unique not null, "
        "country text, "
        "created_at timestamptz default current_timestamp)"
    )
    try:
        cur.execute("alter table profiles add column country text")
    except sqlite3.OperationalError:
        pass

def _run_profile_query(query: str, params=()):
    with sqlite3.connect(PROFILE_DB) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        _ensure_profile_schema(conn)
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.commit()
        return rows


def _slugify_room_id(value: Optional[str]) -> str:
    if not value:
        return ""
    slug = _ROOM_SLUG_RE.sub("-", value.strip().lower())
    slug = slug.strip("-")
    return slug


def _normalize_room_id(value: Optional[str]) -> str:
    slug = _slugify_room_id(value)
    return slug or DEFAULT_ROOM_ID


def _normalize_user_id(value: Optional[str]) -> str:
    if not value:
        return ""
    user = _USER_ID_RE.sub("", str(value).strip())
    return user[:48]

def _sanitize_country_code(value: Optional[str]) -> str:
    if not value:
        return ""
    code = re.sub(r'[^a-zA-Z]', '', str(value)).lower()
    return code[:2]

def _sanitize_display_name(value: Optional[str]) -> str:
    if not value:
        return ""
    name = _USER_ID_RE.sub("", str(value).strip())
    return name[:20]


def _random_user_id() -> str:
    return f"guest-{random.randint(100000, 999999)}"

# Friendly alias and tolerant handler for host link page
@app.get('/host')
def host_alias():
    """Serve the Host Links page at a simple path."""
    path = os.path.join(STATIC_DIR, 'host_link.html')
    if os.path.exists(path):
        return FileResponse(path)
    return HTMLResponse('<h3>host_link.html not found</h3>', status_code=404)

@app.get('/static/host_link.html/{rest:path}')
def host_link_catchall(rest: str = ''):
    """Serve host_link.html even if extra path segments were appended (tolerant)."""
    path = os.path.join(STATIC_DIR, 'host_link.html')
    if os.path.exists(path):
        return FileResponse(path)
    return HTMLResponse('<h3>host_link.html not found</h3>', status_code=404)

@app.get('/engine_manifest.json')
def engine_manifest():
    if os.path.exists(ENGINE_MANIFEST):
        return FileResponse(ENGINE_MANIFEST, media_type='application/json')
    # Fallback minimal manifest
    return HTMLResponse('{"version":"unknown"}', media_type='application/json')


@app.get('/version')
def version_info():
    engine_mod = getattr(_adapter, 'engine', None)
    engine_handle = getattr(_adapter, 'ENGINE_HANDLE', None)
    engine_path = getattr(engine_handle, 'path', None)
    return JSONResponse({
        "ok": True,
        "engine_version": getattr(engine_mod, "__FILE_VERSION__", "unknown"),
        "engine_path": str(engine_path) if engine_path else None,
        "engine_variant": getattr(engine_handle, "variant", None),
    })

def _lan_ip_guess() -> Optional[str]:
    # Prefer local interface enumeration to avoid external reachability
    try:
        hostname = socket.gethostname()
        # getaddrinfo returns multiple addresses; choose first IPv4 non-loopback
        infos = socket.getaddrinfo(hostname, None, family=socket.AF_INET)
        for fam, st, proto, canon, sockaddr in infos:
            ip = sockaddr[0]
            if ip and not ip.startswith('127.'):
                return ip
    except Exception:
        pass
    # Fallback: classic UDP connect trick (still offline; no data sent)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith('127.'):
            return ip
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip and not ip.startswith('127.'):
            return ip
    except Exception:
        pass
    return None

@app.get('/whereami')
def whereami(req: Request):
    """Return base URLs: host header and LAN IP when available, choosing a best default for QR links."""
    try:
        scheme = req.url.scheme or 'http'
        host_hdr = (req.headers.get('host') or '').strip()
        base_host = f"{scheme}://{host_hdr}" if host_hdr else None
        # Extract port: prefer parsed URL port, else from host header, else default 8000
        try:
            port = int(req.url.port or 0)
        except Exception:
            port = 0
        if not port and host_hdr and ':' in host_hdr:
            try:
                port = int(host_hdr.rsplit(':', 1)[1])
            except Exception:
                port = 0
        if not port:
            port = 8000
        lan_ip = _lan_ip_guess()
        base_lan = f"{scheme}://{lan_ip}:{port}" if lan_ip else None
        # Choose best: if host header is localhost/127, prefer LAN; else prefer host header
        def is_loopback(h: Optional[str]) -> bool:
            if not h:
                return True
            return 'localhost' in h.lower() or '127.0.0.1' in h or h.startswith('::1')
        chosen = base_lan if is_loopback(host_hdr) and base_lan else (base_host or base_lan or f"{scheme}://127.0.0.1:{port}")
        return JSONResponse({
            'ok': True,
            'base': chosen,
            'base_host': base_host,
            'base_lan': base_lan,
            'join_random': chosen + '/static/join_random.html',
            'join_chess': chosen + '/static/join_chess.html'
        })
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)
    """Run the exporter script to refresh engine_manifest.json.
    Note: For local/dev use. Consider securing this endpoint in production.
    """
    exporter = os.path.join(WORKSPACE_ROOT, 'tools', 'export_manifest.py')
    if not os.path.exists(exporter):
        return JSONResponse({'ok': False, 'error': 'export_manifest.py not found'}, status_code=404)
    try:
        # Use the same Python executable the server runs under
        subprocess.check_call([os.sys.executable, exporter], cwd=WORKSPACE_ROOT)
        return JSONResponse({'ok': True})
    except subprocess.CalledProcessError as e:
        return JSONResponse({'ok': False, 'error': f'Exporter failed: {e}'}, status_code=500)

@app.post('/admin/reload-engine')
async def reload_engine_and_reset(room: str = Query(DEFAULT_ROOM_ID)):
    """Hot-reload the Golden engine module and reset the current game.
    Use when Bishops_Golden.py has been updated to bring the Netplay server in sync.
    """
    try:
        # Reload the engine module in the adapter
        if hasattr(_adapter, 'reload_engine') and callable(_adapter.reload_engine):
            _adapter.reload_engine()
        else:
            return JSONResponse({'ok': False, 'error': 'reload_engine not available'}, status_code=500)
        # Reset the game so the new engine is used
        hub = _room_or_404(room)
        res = await hub.reset_game()
        return JSONResponse({'ok': True, **res})
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.get('/debug/piece-count')
def debug_piece_count(room: str = Query(DEFAULT_ROOM_ID)):
    try:
        hub = _room_or_404(room)
        b = hub.engine.board
        engine_mod = _adapter.engine
        total = 0
        by = {c.name: 0 for c in engine_mod.TURN_ORDER}
        for r in range(engine_mod.BOARD_SIZE):
            for c in range(engine_mod.BOARD_SIZE):
                p = b.get(r, c)
                if p is not None:
                    total += 1
                    try:
                        by[p.color.name] += 1
                    except Exception:
                        pass
        return JSONResponse({'ok': True, 'total': total, 'byColor': by})
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.get('/debug/assets-check')
def debug_assets_check():
    try:
        exists = os.path.isdir(ASSET_DIR)
        return JSONResponse({'ok': True, 'exists': exists, 'dir': ASSET_DIR, 'mounted': exists})
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.get('/debug/diagnose')
def debug_diagnose(room: str = Query(DEFAULT_ROOM_ID)):
    try:
        hub = _room_or_404(room)
        engine = hub.engine
        act = None
        try:
            act = engine.active_color().name
        except Exception:
            act = None
        try:
            legal = len(engine.legal_moves_for_active())
        except Exception:
            legal = None
        try:
            mode = hub.modes.get(act or '', 'HUM') if act else None
        except Exception:
            mode = None
        try:
            forced = getattr(engine, 'forced_turn', None)
            forced = forced.name if forced is not None else None
        except Exception:
            forced = None
        try:
            two = bool(getattr(_adapter.engine.gs, 'two_stage_active', False))
            lock = bool(getattr(_adapter.engine.gs, 'chess_lock', False))
            thr = int(getattr(_adapter.engine.gs, 'auto_elim_threshold', 0) or 0)
        except Exception:
            two, lock, thr = None, None, None
        try:
            alive = [c.name for c in engine.alive_colors()]
        except Exception:
            alive = None
        try:
            mv_count = len(engine.moves_list)
        except Exception:
            mv_count = None
        return JSONResponse({'ok': True, 'active': act, 'mode': mode, 'legal': legal, 'forced': forced, 'two_stage': two, 'chess_lock': lock, 'auto_elim_threshold': thr, 'alive': alive, 'moves': mv_count})
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.post('/admin/sync-rules')
def sync_rules_from_golden():
    """Extract RULES_REFERENCE from Bishops_Golden.py and write to static rules file.
    Note: For local/dev use. Consider securing this endpoint in production.
    """
    # Try to read RULES_REFERENCE off the already-loaded engine module used by engine_adapter_v3
    engine_mod = getattr(_adapter, 'engine', None)
    if engine_mod is None:
        return JSONResponse({'ok': False, 'error': 'Engine module not loaded'}, status_code=500)
    rules = getattr(engine_mod, 'RULES_REFERENCE', None)
    if not isinstance(rules, str) or not rules.strip():
        return JSONResponse({'ok': False, 'error': 'RULES_REFERENCE not found in engine'}, status_code=404)
    # Normalize newlines and strip trailing whitespace
    text = rules.replace('\r\n', '\n').replace('\r', '\n').strip() + "\n"
    out_path = os.path.join(STATIC_DIR, 'rules_reference.txt')
    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(text)
        return JSONResponse({'ok': True, 'bytes': len(text), 'path': '/static/rules_reference.txt'})
    except Exception as e:
        return JSONResponse({'ok': False, 'error': f'Failed to write rules: {e}'}, status_code=500)

class GameHub:
    def __init__(self, room_id: str = DEFAULT_ROOM_ID, label: Optional[str] = None):
        self.room_id = _normalize_room_id(room_id)
        self.label = label or room_id or self.room_id
        self.created_at = datetime.datetime.utcnow()
        self.storage_slug = _slugify_room_id(self.room_id) or DEFAULT_ROOM_ID
        self._games_dir = os.path.join(GAMES_DIR, self.storage_slug)
        os.makedirs(self._games_dir, exist_ok=True)
        self.clients: Dict[str, Dict[str, Any]] = {}
        self.seat_owners: Dict[str, str] = {}  # seat -> user_id
        self.seat_countries: Dict[str, str] = {}  # seat -> country code
        self.user_connections: Dict[str, set[str]] = {}  # user -> set(conn_ids)
        self._conn_counter = 0
        # Single shared engine instance; one game per process for now
        self.engine = create_engine()
        self.state: Dict[str, Any] = self.engine.serialize_state()
        # Keep the very first board as the initial snapshot for timeline/replay
        try:
            self.initial_board: List[List[Any]] = self._deep_copy_board(self.state.get('board'))
        except Exception:
            self.initial_board = self.state.get('board') or []
        self.lock = asyncio.Lock()
        # Per-color player mode mapping: 'HUM' or 'AI'
        self.modes: Dict[str, str] = { 'WHITE':'HUM', 'GREY':'HUM', 'BLACK':'HUM', 'PINK':'HUM' }
        # Background AI runner task handle
        self._ai_task = None
        # AI move delay (seconds)
        self.ai_delay_seconds = 1.0
        # AI loop diagnostics
        self._ai_running: bool = False
        self._ai_last_stop: Optional[str] = None
        # Auto-elimination threshold (0=Off, 18, 30)
        self.auto_elim_threshold = 18
        # Turn timer defaults (seconds)
        self.turn_seconds = TURN_SECONDS_DEFAULT
        self.turn_grace_seconds = TURN_GRACE_SECONDS_DEFAULT
        self._turn_last = None
        self._turn_deadline = None
        self._turn_grace_deadline = None
        self._turn_task = None
        self._turn_timeout_fired = False
        self._turn_timer_paused = False
        self._turn_pause_remaining = None
        self._turn_pause_grace_remaining = None
        self._turn_timer_paused_by = None
        # Seats that have handed off control to AI for the current game
        self.quit_locked: set[str] = set()
        # Active new-game request (requires explicit confirmation)
        self.reset_pending_by: Optional[str] = None
        self.duel_epoch_seen: int = 0
        self.duel_seat_map: Dict[str, str] = {}
        self.duel_ready: bool = True
        self.duel_wait_ms: int = 0
        self._duel_wait_handle = None
        self._duel_ai_pending: bool = False
        self._suppress_duel_ai_schedule: bool = False
        # Load persisted settings
        try:
            if os.path.isfile(SETTINGS_PATH):
                with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                    s = json.load(f)
                if isinstance(s, dict):
                    v = int(s.get('auto_elim_threshold', 18))
                    if v in (0, 18, 30):
                        self.auto_elim_threshold = v
        except Exception:
            pass
        # Ensure engine.gs is aware of default modes if present
        try:
            for name in self.modes.keys():
                col = getattr(_adapter.engine.PColor, name)
                _adapter.engine.gs.player_is_ai[col] = False
            # Reflect auto-elim threshold to engine module
            setattr(_adapter.engine.gs, 'auto_elim_threshold', int(self.auto_elim_threshold))
        except Exception:
            pass

    def _deep_copy_board(self, board_grid):
        if not isinstance(board_grid, list):
            return []
        out = []
        for row in board_grid:
            r = []
            for cell in row or []:
                if cell is None:
                    r.append(None)
                else:
                    r.append({"kind": cell.get("kind"), "color": cell.get("color")})
            out.append(r)
        return out

    def _cancel_duel_ready_check(self) -> None:
        handle = getattr(self, '_duel_wait_handle', None)
        if handle is not None:
            try:
                handle.cancel()
            except Exception:
                pass
        self._duel_wait_handle = None

    def _schedule_duel_ready_check(self, wait_ms: int) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        delay = max(0.1, (wait_ms / 1000.0) if wait_ms else 0.3)
        self._cancel_duel_ready_check()
        self._duel_wait_handle = loop.call_later(delay, lambda: asyncio.create_task(self._ensure_ai_tick()))

    def _touch_turn_timer(self, turn: Optional[str]) -> None:
        if not turn:
            return
        now = time.monotonic()
        self._turn_last = str(turn)
        self._turn_deadline = now + float(self.turn_seconds)
        if self.turn_grace_seconds and self.turn_grace_seconds > 0:
            self._turn_grace_deadline = self._turn_deadline + float(self.turn_grace_seconds)
        else:
            self._turn_grace_deadline = None
        self._turn_timeout_fired = False
        if self._turn_timer_paused:
            self._turn_pause_remaining = float(self.turn_seconds)
            if self.turn_grace_seconds and self.turn_grace_seconds > 0:
                self._turn_pause_grace_remaining = float(self.turn_grace_seconds)
            else:
                self._turn_pause_grace_remaining = None

    def _clear_turn_timer(self) -> None:
        self._turn_deadline = None
        self._turn_grace_deadline = None
        self._turn_timeout_fired = False
        self._turn_timer_paused = False
        self._turn_pause_remaining = None
        self._turn_pause_grace_remaining = None
        self._turn_timer_paused_by = None

    def _pause_turn_timer(self, paused: bool, by: Optional[str] = None) -> bool:
        if paused:
            if self._turn_timer_paused:
                return False
            now = time.monotonic()
            if self._turn_deadline:
                self._turn_pause_remaining = max(0.0, self._turn_deadline - now)
            else:
                self._turn_pause_remaining = None
            if self._turn_grace_deadline:
                self._turn_pause_grace_remaining = max(0.0, self._turn_grace_deadline - now)
            else:
                self._turn_pause_grace_remaining = None
            self._turn_timer_paused = True
            if by:
                self._turn_timer_paused_by = by
            return True
        if not self._turn_timer_paused:
            return False
        now = time.monotonic()
        if self._turn_pause_remaining is not None:
            self._turn_deadline = now + float(self._turn_pause_remaining)
        if self._turn_pause_grace_remaining is not None:
            self._turn_grace_deadline = now + float(self._turn_pause_grace_remaining)
        else:
            self._turn_grace_deadline = None
        self._turn_timer_paused = False
        self._turn_pause_remaining = None
        self._turn_pause_grace_remaining = None
        self._turn_timer_paused_by = None
        return True

    def _turn_timer_snapshot(self) -> Optional[Dict[str, Any]]:
        if self._turn_timer_paused:
            remaining = float(self._turn_pause_remaining or 0.0)
            grace_remaining = float(self._turn_pause_grace_remaining or 0.0)
            return {
                "turn": self._turn_last,
                "remaining": int(round(remaining)),
                "grace_remaining": int(round(grace_remaining)),
                "grace_active": False,
                "seconds": int(self.turn_seconds),
                "grace_seconds": int(self.turn_grace_seconds),
                "deadline_ms": None,
                "grace_deadline_ms": None,
                "paused": True,
                "paused_by": self._turn_timer_paused_by,
            }
        if not self._turn_deadline:
            return None
        try:
            now_mono = time.monotonic()
            now_wall = time.time()
            remaining = max(0.0, self._turn_deadline - now_mono)
            grace_remaining = 0.0
            grace_active = False
            grace_deadline_ms = None
            if self._turn_grace_deadline:
                grace_remaining = max(0.0, self._turn_grace_deadline - now_mono)
                grace_active = now_mono >= self._turn_deadline
                grace_deadline_ms = int((now_wall + (self._turn_grace_deadline - now_mono)) * 1000)
            deadline_ms = int((now_wall + (self._turn_deadline - now_mono)) * 1000)
            return {
                "turn": self._turn_last,
                "remaining": int(round(remaining)),
                "grace_remaining": int(round(grace_remaining)),
                "grace_active": bool(grace_active),
                "seconds": int(self.turn_seconds),
                "grace_seconds": int(self.turn_grace_seconds),
                "deadline_ms": deadline_ms,
                "grace_deadline_ms": grace_deadline_ms,
            }
        except Exception:
            return None

    def _ensure_turn_timer_task(self) -> None:
        if self._turn_task and not self._turn_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._turn_task = loop.create_task(self._turn_timer_loop())

    async def _turn_timer_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(0.5)
                if not self.clients and not self.seat_owners:
                    break
                await self._check_turn_timeout()
        finally:
            self._turn_task = None

    async def _check_turn_timeout(self) -> None:
        payload = None
        timed_out = None
        async with self.lock:
            try:
                st = self.engine.serialize_state()
            except Exception:
                return
            turn = st.get("turn")
            if not turn:
                return
            if self._turn_last != turn or not self._turn_deadline:
                self._touch_turn_timer(turn)
            if self._turn_timer_paused:
                return
            now = time.monotonic()
            if not self._turn_deadline or now < self._turn_deadline:
                return
            if self.turn_grace_seconds and self._turn_grace_deadline and now < self._turn_grace_deadline:
                return
            if self._turn_timeout_fired:
                return
            self._turn_timeout_fired = True
            timed_out = str(turn)
            try:
                color_enum = getattr(_adapter.engine.PColor, timed_out)
                self.engine._eliminate_color(color_enum, reason="timeout")
            except Exception:
                return
            self.state = self.engine.serialize_state()
            self._turn_last = None
            self._clear_turn_timer()
            payload = self._state_for_send()
        if timed_out and payload:
            await self._broadcast({"type": "error", "payload": f"{timed_out} timed out."})
            await self._broadcast({"type": "state", "payload": payload})
            await self._ensure_ai_tick()

    def _state_for_send(self) -> Dict[str, Any]:
        payload = self.engine.serialize_state()
        try:
            payload['initial'] = self._deep_copy_board(self.initial_board)
        except Exception:
            payload['initial'] = self.initial_board
        try:
            payload['modes'] = dict(self.modes)
        except Exception:
            payload['modes'] = { 'WHITE':'HUM', 'GREY':'HUM', 'BLACK':'HUM', 'PINK':'HUM' }
        try:
            payload['seat_countries'] = dict(self.seat_countries)
        except Exception:
            payload['seat_countries'] = {}
        try:
            payload['auto_elim_threshold'] = int(self.auto_elim_threshold)
        except Exception:
            payload['auto_elim_threshold'] = 0
        try:
            payload['quit_locked'] = list(self.quit_locked)
        except Exception:
            payload['quit_locked'] = []
        try:
            turn = payload.get('turn')
            if turn and turn != self._turn_last:
                self._touch_turn_timer(turn)
            timer_payload = self._turn_timer_snapshot()
            if timer_payload:
                payload['turn_timer'] = timer_payload
        except Exception:
            pass
        payload['reset_pending_by'] = self.reset_pending_by
        duel_info = payload.get('duel')
        if isinstance(duel_info, dict) and self._align_duel_modes(duel_info):
            payload['modes'] = dict(self.modes)
            payload['quit_locked'] = list(self.quit_locked)
        if self._duel_ai_pending and not self._suppress_duel_ai_schedule:
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon(lambda: asyncio.create_task(self._ensure_ai_tick()))
            except RuntimeError:
                pass
            self._duel_ai_pending = False
        self._ensure_turn_timer_task()
        return payload

    def _align_duel_modes(self, duel_info: Dict[str, Any]) -> bool:
        """Align hub state to the duel seat mapping. Returns True when modes/locks or readiness change."""
        try:
            active = bool(duel_info.get('active'))
        except Exception:
            active = False
        try:
            epoch = int(duel_info.get('epoch') or 0)
        except Exception:
            epoch = 0
        try:
            wait_ms = int(duel_info.get('wait_ms', 0) or 0)
        except Exception:
            wait_ms = 0
        ready = bool(duel_info.get('ready', True))
        prev_ready = self.duel_ready
        self.duel_wait_ms = max(0, wait_ms)
        changed_ready = False
        if not active:
            self.duel_seat_map = {}
            if epoch == 0:
                self.duel_epoch_seen = 0
            if not self.duel_ready or self.duel_wait_ms:
                changed_ready = True
            self.duel_ready = True
            self.duel_wait_ms = 0
            self._cancel_duel_ready_check()
            self._duel_ai_pending = False
            return changed_ready
        white_origin = 'WHITE'
        black_origin = 'BLACK'
        self.duel_seat_map = {'WHITE': 'WHITE', 'BLACK': 'BLACK'}
        changed = False
        finalists = {white_origin, black_origin}
        # Force finalists into human mode
        white_mode = 'HUM'
        black_mode = 'HUM'
        if self.modes.get('WHITE') != white_mode:
            self.modes['WHITE'] = white_mode
            changed = True
        if self.modes.get('BLACK') != black_mode:
            self.modes['BLACK'] = black_mode
            changed = True
        if self.modes.get(white_origin) != white_mode:
            self.modes[white_origin] = white_mode
            changed = True
        if self.modes.get(black_origin) != black_mode:
            self.modes[black_origin] = black_mode
            changed = True
        eliminated = [seat for seat in COLOR_SEATS if seat not in finalists]
        for seat in eliminated:
            if self.modes.get(seat) != 'HUM':
                self.modes[seat] = 'HUM'
                changed = True
            if seat not in self.quit_locked:
                self.quit_locked.add(seat)
                changed = True
        origin_white_locked = white_origin in self.quit_locked
        origin_black_locked = black_origin in self.quit_locked
        if origin_white_locked and 'WHITE' not in self.quit_locked:
            self.quit_locked.add('WHITE')
            changed = True
        if not origin_white_locked and 'WHITE' in self.quit_locked and white_origin != 'WHITE':
            self.quit_locked.discard('WHITE')
            changed = True
        if origin_black_locked and 'BLACK' not in self.quit_locked:
            self.quit_locked.add('BLACK')
            changed = True
        if not origin_black_locked and 'BLACK' in self.quit_locked and black_origin != 'BLACK':
            self.quit_locked.discard('BLACK')
            changed = True
        try:
            enum = _adapter.engine.PColor
            if enum:
                _adapter.engine.gs.player_is_ai[getattr(enum, 'WHITE')] = False
                _adapter.engine.gs.player_is_ai[getattr(enum, 'BLACK')] = False
                for seat in eliminated:
                    if hasattr(enum, seat):
                        _adapter.engine.gs.player_is_ai[getattr(enum, seat)] = False
        except Exception:
            pass
        if epoch and epoch != self.duel_epoch_seen:
            self.duel_epoch_seen = epoch
        if not ready:
            self.duel_ready = False
            if prev_ready:
                changed_ready = True
            self._schedule_duel_ready_check(self.duel_wait_ms)
            self._duel_ai_pending = False
        else:
            self.duel_ready = True
            if not prev_ready:
                changed_ready = True
                self._duel_ai_pending = True
            self._cancel_duel_ready_check()
        return changed or changed_ready

    def _canonical_seat(self, seat: str) -> str:
        try:
            key = (seat or 'SPECTATOR').upper()
        except Exception:
            key = 'SPECTATOR'
        return self.duel_seat_map.get(key, key)

    def _save_current_game(self) -> Dict[str, Any]:
        """Persist current game to games/ as a JSON file if any moves were played."""
        try:
            moves = list(self.engine.moves_list)
            if not moves:
                return {"ok": True, "saved": False, "room": self.room_id}
            ended_at = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            name = f"{self.storage_slug}_{ended_at}.json"
            body = {
                "started_at": getattr(self, 'started_at', None),
                "ended_at": ended_at,
                "room_id": self.room_id,
                "label": self.label,
                "initial": self.initial_board,
                "final": self.engine.serialize_state(),
                "moves": moves,
                "engine_version": getattr(_adapter.engine, 'VERSION_STR', 'unknown'),
            }
            os.makedirs(self._games_dir, exist_ok=True)
            with open(os.path.join(self._games_dir, name), 'w', encoding='utf-8') as f:
                json.dump(body, f, ensure_ascii=False)
            return {"ok": True, "saved": True, "file": name, "room": self.room_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def summary(self) -> Dict[str, Any]:
        # Recompute live counts directly from current connections
        taken = []
        watchers = 0
        for info in self.clients.values():
            seat = info.get("seat")
            if seat in COLOR_SEATS and seat not in taken:
                taken.append(seat)
            else:
                watchers += 1
        available = [seat for seat in COLOR_SEATS if seat not in taken]
        # Keep seat_owners in sync with live connections
        try:
            for seat in list(self.seat_owners.keys()):
                if seat not in taken:
                    self.seat_owners.pop(seat, None)
        except Exception:
            pass
        try:
            moves_played = len(self.engine.moves_list)
        except Exception:
            moves_played = 0
        created_iso = self.created_at.isoformat() + "Z"
        return {
            "room_id": self.room_id,
            "label": self.label,
            "created_at": created_iso,
            "taken": taken,
            "available": available,
            "spectators": watchers,
            "clients": len(self.clients),
            "moves_played": moves_played,
            "full": self.room_full(),
        }

    def room_full(self) -> bool:
        return len(self.seat_owners) >= len(COLOR_SEATS)

    def _room_locked_for_new_entries(self, seat: str) -> bool:
        if not self.room_full():
            return False
        return seat not in COLOR_SEATS or seat not in self.seat_owners

    def _seat_for_user(self, user_id: str) -> Optional[str]:
        for seat, owner in self.seat_owners.items():
            if owner == user_id:
                return seat
        return None

    async def connect(self, seat: str, user_id: str, ws: WebSocket, country: Optional[str] = None, allow_multi: bool = False) -> tuple[str, str]:
        if not user_id:
            raise UserRequiredError()
        user_id = _normalize_user_id(user_id)
        if not user_id:
            raise UserRequiredError()
        try:
            seat_raw = (seat or "AUTO").upper()
        except Exception:
            seat_raw = "AUTO"
        seat_norm = self._canonical_seat(seat_raw)
        async with self.lock:
            existing_seat = self._seat_for_user(user_id)
            if seat_norm not in COLOR_SEATS:
                if existing_seat:
                    seat_norm = existing_seat
                    seat_raw = existing_seat
                else:
                    for candidate in COLOR_SEATS:
                        if candidate not in self.seat_owners:
                            seat_norm = candidate
                            seat_raw = candidate
                            break
                    else:
                        raise RoomFullError(self.room_id)
            if existing_seat and existing_seat != seat_norm and not allow_multi:
                # Prevent same name joining a different seat concurrently
                raise UserInUseError(user_id)
            if seat_norm in COLOR_SEATS:
                owner = self.seat_owners.get(seat_norm)
                if owner and owner != user_id:
                    raise SeatTakenError(seat_norm)
                if owner != user_id and self.room_full():
                    raise RoomFullError(self.room_id)
                if existing_seat and existing_seat != seat_norm and not allow_multi:
                    self.seat_owners.pop(existing_seat, None)
                self.seat_owners[seat_norm] = user_id
                if country:
                    self.seat_countries[seat_norm] = country
        await ws.accept()
        async with self.lock:
            conn_id = f"{self.room_id}-conn-{self._conn_counter}"
            self._conn_counter += 1
            self.clients[conn_id] = {"seat_raw": seat_raw, "seat": seat_norm, "ws": ws, "user": user_id}
            self.user_connections.setdefault(user_id, set()).add(conn_id)
        # Auto-reset stale room when only one seat is occupied.
        try:
            moves_played = len(self.engine.moves_list)
        except Exception:
            moves_played = 0
        try:
            seat_count = len(self.seat_owners)
        except Exception:
            seat_count = 0
        if moves_played > 0 and seat_count <= 1:
            try:
                await self.reset_game()
            except Exception:
                pass
        # Broadcast updated counts
        await self._broadcast({"type": "rooms_update", "rooms": rooms.snapshot()})
        await self._send_state(ws)
        return conn_id, seat_norm

    async def disconnect(self, conn_id: str):
        empty_now = False
        async with self.lock:
            info = self.clients.pop(conn_id, None)
            if not info:
                return
            seat_norm = info.get("seat")
            user_id = info.get("user")
            if user_id:
                conns = self.user_connections.get(user_id)
                if conns and conn_id in conns:
                    conns.discard(conn_id)
                if conns and not conns:
                    self.user_connections.pop(user_id, None)
            if seat_norm in COLOR_SEATS and user_id:
                owner = self.seat_owners.get(seat_norm)
                if owner == user_id:
                    self.seat_owners.pop(seat_norm, None)
                    self.seat_countries.pop(seat_norm, None)
            empty_now = (not self.clients) and (not self.seat_owners)
        if empty_now:
            try:
                async with self.lock:
                    for col in COLOR_SEATS:
                        self.modes[col] = 'HUM'
                    self.quit_locked.clear()
                    self.reset_pending_by = None
                    self._turn_last = None
                    self._clear_turn_timer()
                await self.reset_game()
            except Exception:
                pass
        try:
            await self._broadcast({"type": "rooms_update", "rooms": rooms.snapshot()})
        except Exception:
            pass

    async def _broadcast(self, message: Dict[str, Any]):
        dead: List[str] = []
        payload = json.dumps(message)
        for conn_id, info in list(self.clients.items()):
            ws = info.get("ws")
            if ws is None:
                dead.append(conn_id)
                continue
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(conn_id)
        for conn_id in dead:
            try:
                await self.disconnect(conn_id)
            except Exception:
                self.clients.pop(conn_id, None)

    async def _send_state(self, ws: WebSocket):
        # Refresh from engine before sending
        self.state = self.engine.serialize_state()
        payload = json.dumps({"type": "state", "payload": self._state_for_send()})
        await ws.send_text(payload)

    async def reset_game(self) -> Dict[str, Any]:
        # Reinitialize engine and broadcast fresh state
        async with self.lock:
            # Save previous game if any moves were made
            try:
                self._save_current_game()
            except Exception:
                pass
            self.engine = create_engine()
            # Unlock any seats that quit-to-AI during the prior game
            for col in list(self.quit_locked):
                self.modes[col] = 'HUM'
            self.quit_locked.clear()
            self.reset_pending_by = None
            self.duel_epoch_seen = 0
            self.duel_seat_map = {}
            self.duel_seat_map = {}
            self.duel_ready = True
            self.duel_wait_ms = 0
            self._cancel_duel_ready_check()
            self._duel_ai_pending = False
            self._turn_last = None
            self._clear_turn_timer()
            self.state = self.engine.serialize_state()
            try:
                self.initial_board = self._deep_copy_board(self.state.get('board'))
                self.started_at = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            except Exception:
                self.initial_board = self.state.get('board')
            # Reapply player modes into fresh engine.gs
            try:
                for name in self.modes.keys():
                    col = getattr(_adapter.engine.PColor, name)
                    _adapter.engine.gs.player_is_ai[col] = False
                # Also reapply auto-elim threshold
                setattr(_adapter.engine.gs, 'auto_elim_threshold', int(self.auto_elim_threshold))
            except Exception:
                pass
            # Reset AI task and keep modes as-is
            if self._ai_task and not self._ai_task.done():
                try:
                    self._ai_task.cancel()
                except Exception:
                    pass
                self._ai_task = None
        await self._broadcast({"type": "state", "payload": self._state_for_send()})
        # Kick AI if needed on fresh board
        await self._ensure_ai_tick()
        return {"ok": True}

    async def reset_game_chess(self) -> Dict[str, Any]:
        """Reset to a chess-only session (WHITE vs BLACK inside 8×8)."""
        async with self.lock:
            try:
                self._save_current_game()
            except Exception:
                pass
            self.engine = create_engine()
            for col in list(self.quit_locked):
                self.modes[col] = 'HUM'
            self.quit_locked.clear()
            self.reset_pending_by = None
            self.duel_epoch_seen = 0
            try:
                # Switch engine board to chess-only and align flags
                if hasattr(self.engine, 'reset_chess_only'):
                    self.engine.reset_chess_only()
            except Exception:
                pass
            # Map duel seats to WHITE/BLACK only
            self.duel_seat_map = { 'WHITE': 'WHITE', 'BLACK': 'BLACK' }
            self.duel_ready = True
            self.duel_wait_ms = 0
            self._cancel_duel_ready_check()
            self._duel_ai_pending = False
            self._turn_last = None
            self._clear_turn_timer()
            self.state = self.engine.serialize_state()
            try:
                self.initial_board = self._deep_copy_board(self.state.get('board'))
                self.started_at = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            except Exception:
                self.initial_board = self.state.get('board')
            # Reapply player modes to engine.gs (only WHITE/BLACK relevant)
            try:
                for name in self.modes.keys():
                    col = getattr(_adapter.engine.PColor, name)
                    _adapter.engine.gs.player_is_ai[col] = False
                setattr(_adapter.engine.gs, 'auto_elim_threshold', int(self.auto_elim_threshold))
            except Exception:
                pass
            # Cancel any running AI loop
            if self._ai_task and not self._ai_task.done():
                try:
                    self._ai_task.cancel()
                except Exception:
                    pass
                self._ai_task = None
        await self._broadcast({"type": "state", "payload": self._state_for_send()})
        await self._ensure_ai_tick()
        return {"ok": True}

    async def _ensure_ai_tick(self):
        return

    async def handle(self, conn_id: str, msg: Dict[str, Any]):
        info = self.clients.get(conn_id)
        if not info:
            return
        ws = info.get("ws")
        ws = info.get("ws")
        if ws is None:
            return
        seat_raw = str(info.get("seat_raw", "SPECTATOR") or "SPECTATOR").upper()
        seat = seat_raw
        t = msg.get("type")
        seat_norm = self._canonical_seat(seat_raw)
        if t == "hello":
            # no-op
            return
        if t == "duel_ready":
            async with self.lock:
                try:
                    mark = getattr(self.engine, 'mark_duel_ready', None)
                    if callable(mark):
                        mark()
                except Exception:
                    pass
                self.state = self.engine.serialize_state()
                payload = self._state_for_send()
            await self._broadcast({"type":"state","payload": payload})
            await self._ensure_ai_tick()
            return
        if t == "switch_seat":
            desired = (msg.get("payload") or {}).get("seat") or ""
            try:
                desired = str(desired).upper()
            except Exception:
                desired = ""
            if desired not in ("WHITE", "BLACK"):
                await ws.send_text(json.dumps({"type":"error","payload":"Switch seat requires WHITE or BLACK."}))
                return
            if seat_norm not in ("WHITE", "BLACK"):
                await ws.send_text(json.dumps({"type":"error","payload":"Switch seat is only for duel seats."}))
                return
            try:
                duel_info = self.engine.serialize_state().get("duel")
            except Exception:
                duel_info = None
            if not (isinstance(duel_info, dict) and duel_info.get("active")):
                await ws.send_text(json.dumps({"type":"error","payload":"Switch seat is only available during duel."}))
                return
            user_id = info.get("user")
            if not user_id:
                await ws.send_text(json.dumps({"type":"error","payload":"User required."}))
                return
            async with self.lock:
                owner = self.seat_owners.get(desired)
                if owner and owner != user_id:
                    await ws.send_text(json.dumps({"type":"error","payload":"Seat already taken."}))
                    return
                prev_country = None
                if self.seat_owners.get(seat_norm) == user_id:
                    self.seat_owners.pop(seat_norm, None)
                    prev_country = self.seat_countries.pop(seat_norm, None)
                self.seat_owners[desired] = user_id
                if prev_country:
                    self.seat_countries[desired] = prev_country
                info["seat_raw"] = desired
                info["seat"] = desired
            await ws.send_text(json.dumps({"type":"seat_changed","seat": desired}))
            await self._broadcast({"type": "rooms_update", "rooms": rooms.snapshot()})
            await self._broadcast({"type":"state","payload": self._state_for_send()})
            return
        if t == "force_duel":
            if seat_norm not in COLOR_SEATS:
                await ws.send_text(json.dumps({"type": "error", "payload": "Force Duel requires an active seat."}))
                return
            err_msg = None
            async with self.lock:
                try:
                    ok = bool(getattr(self.engine, 'force_duel', lambda: False)())
                except Exception as exc:  # pragma: no cover - defensive
                    ok = False
                    err_msg = f"Force duel failed: {exc}"
                if ok:
                    try:
                        setattr(self.engine, 'forced_turn', None)
                    except Exception:
                        pass
                    try:
                        if hasattr(self.engine, 'turn_i'):
                            self.engine.turn_i = _adapter.engine.TURN_ORDER.index(_adapter.engine.PColor.WHITE)
                    except Exception:
                        pass
                    self.state = self.engine.serialize_state()
            if not ok:
                await ws.send_text(json.dumps({"type": "error", "payload": err_msg or "Force duel failed."}))
            else:
                await self._broadcast({"type":"state","payload": self._state_for_send()})
                await self._ensure_ai_tick()
            return
        if t == "chat":
            p = msg.get("payload") or {}
            text = str(p.get("text", "")).strip()
            if not text:
                return
            if len(text) > 300:
                text = text[:300]
            user = info.get("user") or "Guest"
            seat_label = seat_norm if seat_norm in COLOR_SEATS else "SPECTATOR"
            await self._broadcast({
                "type": "chat",
                "payload": {
                    "user": str(user),
                    "seat": seat_label,
                    "text": text,
                    "ts": time.time(),
                }
            })
            return
        if t == "request_new_game":
            if seat_norm not in COLOR_SEATS:
                await ws.send_text(json.dumps({"type":"error","payload":"Only seated players can request a new game."}))
                return
            conflict: Optional[str] = None
            async with self.lock:
                if self.reset_pending_by is None:
                    self.reset_pending_by = seat_norm
                elif self.reset_pending_by == seat_norm:
                    # Toggle off (cancel) if the same seat taps again
                    self.reset_pending_by = None
                else:
                    conflict = self.reset_pending_by
            await self._broadcast({"type":"state","payload": self._state_for_send()})
            if conflict:
                await ws.send_text(json.dumps({"type":"error","payload": f"New game already requested by {conflict}."}))
            return
        if t == "reset_room":
            # Hard reset: clear locks/modes and reset the game state
            async with self.lock:
                for col in COLOR_SEATS:
                    self.modes[col] = 'HUM'
                self.quit_locked.clear()
                self.reset_pending_by = None
            await self.reset_game()
            return
        if t == "confirm_new_game":
            if seat_norm not in COLOR_SEATS:
                await ws.send_text(json.dumps({"type":"error","payload":"Only seated players can confirm a new game."}))
                return
            confirmed = False
            blocker: Optional[str] = None
            async with self.lock:
                if self.reset_pending_by == seat_norm:
                    self.reset_pending_by = None
                    confirmed = True
                else:
                    blocker = self.reset_pending_by
                new_state = self._state_for_send()
            await self._broadcast({"type":"state","payload": new_state})
            if not confirmed:
                if blocker:
                    await ws.send_text(json.dumps({"type":"error","payload": f"Awaiting confirmation from {blocker}."}))
                else:
                    await ws.send_text(json.dumps({"type":"error","payload":"No new game request to confirm."}))
                return
            await self.reset_game()
            return
        if t == "set_auto_elim":
            # payload: { threshold: 0|18|30 }
            p = msg.get('payload') or {}
            try:
                thr = int(p.get('threshold', 18))
            except Exception:
                thr = 18
            if thr not in (0, 18, 30):
                # Clamp to nearest allowed
                thr = 0 if thr <= 9 else (18 if thr <= 24 else 30)
            async with self.lock:
                self.auto_elim_threshold = thr
                try:
                    setattr(_adapter.engine.gs, 'auto_elim_threshold', int(thr))
                except Exception:
                    pass
                # Persist settings
                try:
                    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
                        json.dump({'auto_elim_threshold': int(self.auto_elim_threshold)}, f)
                except Exception:
                    pass
            await self._broadcast({"type":"state","payload": self._state_for_send()})
            # If an AI should move next, ensure loop runs
            await self._ensure_ai_tick()
            return
        if t == "timer_pause":
            if seat_norm not in COLOR_SEATS:
                await ws.send_text(json.dumps({"type":"error","payload":"Only seated players can pause the timer."}))
                return
            p = msg.get('payload') or {}
            pause = bool(p.get('paused'))
            async with self.lock:
                changed = self._pause_turn_timer(pause, by=seat_norm)
                payload = self._state_for_send()
            if changed:
                await self._broadcast({"type":"state","payload": payload})
            else:
                await ws.send_text(json.dumps({"type":"state","payload": payload}))
            return
        if t == "set_mode":
            return
        if t in ("quit_seat", "resign"):
            if seat_norm not in COLOR_SEATS:
                await ws.send_text(json.dumps({"type": "error", "payload": "You must occupy a seat to resign."}))
                return
            async with self.lock:
                color_enum = None
                try:
                    enum = _adapter.engine.PColor
                    if enum and hasattr(enum, seat_norm):
                        color_enum = getattr(enum, seat_norm)
                except Exception:
                    color_enum = None
                try:
                    if color_enum is not None and hasattr(self.engine, "_eliminate_color"):
                        self.engine._eliminate_color(color_enum, reason="resign")
                    elif color_enum is not None:
                        elim_fn = getattr(_adapter.engine, "eliminate_color", None)
                        if callable(elim_fn):
                            elim_fn(self.engine.board, getattr(_adapter.engine, "gs", None), color_enum, reason="resign", flash=False)
                except Exception:
                    pass
                for name in {seat_norm, seat_raw}:
                    if name in COLOR_SEATS:
                        self.seat_owners.pop(name, None)
                        self.seat_countries.pop(name, None)
                        self.quit_locked.discard(name)
                        self.modes[name] = 'HUM'
                        try:
                            enum = _adapter.engine.PColor
                            if enum and hasattr(enum, name):
                                _adapter.engine.gs.player_is_ai[getattr(enum, name)] = False
                        except Exception:
                            pass
                self.state = self.engine.serialize_state()
                new_state = self._state_for_send()
            await self._broadcast({"type": "state", "payload": new_state})
            await self._broadcast({"type": "rooms_update", "rooms": rooms.snapshot()})
            try:
                await ws.send_text(json.dumps({"type": "resigned", "color": seat_norm}))
            except Exception:
                pass
            try:
                await ws.close(code=1000)
            except Exception:
                pass
            return
        if t == "swap_kq":
            payload = msg.get('payload') or {}
            target = str(payload.get('color', '')).upper()
            if target not in COLOR_SEATS:
                await ws.send_text(json.dumps({"type":"error", "payload": "Invalid color for swap."}))
                return
            async with self.lock:
                # Allow swap only before that color's first move
                try:
                    moves_by_color = getattr(self.engine, "moves_list", [])
                    color_moves = [m for m in moves_by_color if m.get("by") == target]
                    if color_moves:
                        await ws.send_text(json.dumps({"type":"error", "payload": "Swap allowed only before your first move."}))
                        return
                except Exception:
                    pass
                swap_fn = getattr(self.engine, 'swap_kq', None)
                ok = bool(callable(swap_fn) and swap_fn(target))
                if ok:
                    # Count swap as that color's first move and advance turn
                    try:
                        moves_by_color = getattr(self.engine, "moves_list", None)
                        if isinstance(moves_by_color, list):
                            moves_by_color.append({"by": target, "swap": True})
                    except Exception:
                        pass
                    try:
                        advance_fn = getattr(self.engine, "advance_turn", None)
                        if callable(advance_fn):
                            advance_fn()
                    except Exception:
                        pass
                    self.state = self.engine.serialize_state()
                    payload_state = self._state_for_send()
                else:
                    payload_state = None
            if not ok:
                await self._broadcast({"type":"error", "payload": "Unable to swap king and queen."})
                return
            await self._broadcast({"type":"state", "payload": payload_state})
            await self._broadcast({"type":"state","payload": self._state_for_send()})
            return

        if t == "move":
            # Expect payload: {sr,sc,er,ec}
            mv = msg.get("payload", {})
            try:
                sr, sc, er, ec = int(mv.get("sr")), int(mv.get("sc")), int(mv.get("er")), int(mv.get("ec"))
            except Exception:
                await self._broadcast({"type":"error","payload": "Invalid move payload"})
                return
            if seat_norm in self.quit_locked or seat_raw in self.quit_locked:
                await ws.send_text(json.dumps({"type":"error","payload":"Seat is locked for this game."}))
                return
            async with self.lock:
                if not self.duel_ready:
                    try:
                        mark = getattr(self.engine, 'mark_duel_ready', None)
                        if callable(mark):
                            mark()
                    except Exception:
                        pass
                result = self.engine.apply_move(seat_norm, sr, sc, er, ec)
                if result.get("ok"):
                    self.state = self.engine.serialize_state()
                    payload = self._state_for_send()
                else:
                    payload = None
            if not result.get("ok"):
                await self._broadcast({"type":"error","payload": result.get("error", "Illegal move")})
                return
            await self._broadcast({"type":"state","payload": payload})
            # After a human move, if next to play is AI, start AI loop
            await self._ensure_ai_tick()
        elif t == "legal_for":
            # Expect payload: {sr, sc} and return legal destinations for active color matching that source
            try:
                sr, sc = int(msg.get("payload", {}).get("sr")), int(msg.get("payload", {}).get("sc"))
            except Exception:
                await ws.send_text(json.dumps({"type":"error","payload":"Invalid legal_for payload"}))
                return
            moves = []
            try:
                for (r0, c0, r1, c1) in self.engine.legal_moves_for_active():
                    if r0 == sr and c0 == sc:
                        moves.append({"er": int(r1), "ec": int(c1)})
            except Exception:
                pass
            await ws.send_text(json.dumps({"type":"legal","payload": {"sr": sr, "sc": sc, "moves": moves}}))
        elif t == "request_state":
            # Send current state to all (or could send only to requester if we tracked it)
            self.state = self.engine.serialize_state()
            await self._broadcast({"type":"state","payload": self._state_for_send()})
            await self._ensure_ai_tick()

class RoomManager:
    def __init__(self):
        self._rooms: Dict[str, GameHub] = {}
        self._lock = threading.RLock()
        self._serial = 1
        self._auto_counter = 2
        self._auto_history: Dict[str, Dict[str, Any]] = {}
        self.get_or_create(DEFAULT_ROOM_ID, label="Main Room")
        # Precreate a fixed set of tables
        for i in range(2, MAX_AUTO_ROOMS + 1):
            rid = f"{AUTO_ROOM_PREFIX}-{i}"
            label = f"Table {i}"
            self._rooms[rid] = GameHub(room_id=rid, label=label)
            self._auto_history[rid] = {"created_at": datetime.datetime.utcnow(), "had_clients": False}

    def normalize(self, room_id: Optional[str]) -> str:
        return _normalize_room_id(room_id)

    def get_or_create(self, room_id: Optional[str], label: Optional[str] = None) -> GameHub:
        rid = self.normalize(room_id)
        with self._lock:
            hub = self._rooms.get(rid)
            if hub is None:
                hub = GameHub(room_id=rid, label=label or room_id or rid)
                self._rooms[rid] = hub
            elif label and hub.label != label:
                hub.label = label
            return hub

    def require(self, room_id: Optional[str]) -> GameHub:
        rid = self.normalize(room_id)
        with self._lock:
            hub = self._rooms.get(rid)
            if hub is None:
                raise KeyError(rid)
            return hub

    def create_room(self, *, room_id: Optional[str] = None, label: Optional[str] = None) -> GameHub:
        with self._lock:
            if len(self._rooms) >= MAX_AUTO_ROOMS:
                raise ValueError("Maximum number of rooms reached")
            base = room_id or label or f"table-{self._serial}"
            slug = _slugify_room_id(base)
            if not slug:
                slug = f"table-{self._serial}"
            candidate = slug
            suffix = 1
            while candidate in self._rooms:
                suffix += 1
                candidate = f"{slug}-{suffix}"
            hub = GameHub(room_id=candidate, label=label or room_id or candidate)
            self._rooms[candidate] = hub
            self._serial += 1
            return hub

    def _room_has_open_seat(self, hub: GameHub) -> bool:
        try:
            taken = len(hub.seat_owners)
        except Exception:
            taken = 0
        return taken < len(COLOR_SEATS)

    def _room_sort_key(self, hub: GameHub) -> tuple[int, int, str]:
        rid = (hub.room_id or '').lower()
        label = (hub.label or '').lower()
        if rid == DEFAULT_ROOM_ID:
            return (0, 1, rid)
        num: Optional[int] = None
        if rid.startswith(f"{AUTO_ROOM_PREFIX}-"):
            tail = rid.split('-', 1)[-1]
            if tail.isdigit():
                num = int(tail)
        if num is None:
            match = re.search(r"\d+", rid) or re.search(r"\d+", label)
            if match:
                num = int(match.group(0))
        if num is None:
            num = 9999
        return (1, num, rid)

    def _sorted_rooms_locked(self) -> List[GameHub]:
        return sorted(self._rooms.values(), key=self._room_sort_key)

    def find_room_for_user(self, user_id: str) -> Optional[GameHub]:
        if not user_id:
            return None
        with self._lock:
            for hub in self._rooms.values():
                try:
                    if hub._seat_for_user(user_id):
                        return hub
                except Exception:
                    continue
        return None

    def _next_auto_room_id_locked(self) -> str:
        while True:
            candidate = f"{AUTO_ROOM_PREFIX}-{self._auto_counter}"
            self._auto_counter += 1
            if candidate not in self._rooms:
                return candidate

    def _create_auto_room_locked(self) -> Optional[GameHub]:
        if len(self._rooms) >= MAX_AUTO_ROOMS:
            return None
        room_id = self._next_auto_room_id_locked()
        label = f"Table {room_id.split('-', 1)[-1]}"
        hub = GameHub(room_id=room_id, label=label)
        self._rooms[room_id] = hub
        self._auto_history[room_id] = {
            "created_at": datetime.datetime.utcnow(),
            "had_clients": False,
        }
        return hub

    def _cleanup_empty_rooms_locked(self) -> None:
        # Fixed rooms; do not drop precreated tables
        return

    def _ensure_room_capacity_locked(self) -> None:
        while len(self._rooms) < MAX_AUTO_ROOMS:
            for hub in self._rooms.values():
                if self._room_has_open_seat(hub):
                    break
            else:
                self._create_auto_room_locked()
                continue
            break
        self._cleanup_empty_rooms_locked()

    def ensure_capacity(self) -> None:
        with self._lock:
            self._ensure_room_capacity_locked()

    def assign_room(self) -> GameHub:
        """Pick the first room with an open seat, creating a new auto room if needed."""
        with self._lock:
            self._ensure_room_capacity_locked()
            for hub in self._sorted_rooms_locked():
                if self._room_has_open_seat(hub):
                    return hub
            # No open seats anywhere; return main as fallback
            return self.get_or_create(DEFAULT_ROOM_ID)

    def delete_room(self, room_id: str) -> None:
        rid = self.normalize(room_id)
        if rid == DEFAULT_ROOM_ID:
            raise ValueError("default room cannot be removed")
        with self._lock:
            self._rooms.pop(rid, None)

    def list_rooms(self) -> List[GameHub]:
        with self._lock:
            return list(self._rooms.values())

    def snapshot(self) -> List[Dict[str, Any]]:
        with self._lock:
            self._ensure_room_capacity_locked()
            return [hub.summary() for hub in self._rooms.values()]


rooms = RoomManager()


def _room_or_404(room_id: Optional[str]) -> GameHub:
    try:
        return rooms.require(room_id)
    except KeyError as exc:
        ident = rooms.normalize(room_id)
        raise HTTPException(status_code=404, detail=f"room '{ident}' not found") from exc


class RoomCreatePayload(BaseModel):
    room_id: Optional[str] = Field(
        default=None,
        description="Optional slug for the room (letters/numbers/hyphen). Leave blank for auto.",
        max_length=64,
    )
    label: Optional[str] = Field(
        default=None,
        description="Friendly display name for UI lists.",
        max_length=80,
    )


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    seat_raw = ws.query_params.get("seat")
    seat = seat_raw.upper() if seat_raw else "AUTO"
    if seat in ("SPECTATOR", "VIEW"):
        seat = "AUTO"
    room_param_raw = ws.query_params.get("room")
    user_param = ws.query_params.get("user")
    country_param = ws.query_params.get("country")
    selfplay_param = ws.query_params.get("selfplay")
    user_id = _normalize_user_id(user_param)
    if not user_id:
        await ws.accept()
        await ws.send_text(json.dumps({"type": "user_required"}))
        await ws.close()
        return
    # Enforce fill order: always assign the first room with an open seat.
    hub = rooms.find_room_for_user(user_id) or rooms.assign_room()
    country_code = _sanitize_country_code(country_param)
    allow_multi = str(selfplay_param or '').lower() in ('1', 'true', 'yes')
    try:
        conn_id, seat_norm = await hub.connect(seat, user_id, ws, country_code or None, allow_multi)
        rooms.ensure_capacity()
    except RoomFullError as e:
        rooms.ensure_capacity()
        await ws.send_text(json.dumps({"type": "room_full", "room": e.room_id}))
        await ws.close()
        return
    except UserInUseError as e:
        await ws.accept()
        await ws.send_text(json.dumps({"type": "user_in_use", "user": e.user_id}))
        await ws.close()
        return
    except SeatTakenError as e:
        await ws.send_text(json.dumps({"type": "seat_taken", "seat": e.seat}))
        await ws.close()
        return
    except UserRequiredError:
        await ws.send_text(json.dumps({"type": "user_required"}))
        await ws.close()
        return
    try:
        while True:
            txt = await ws.receive_text()
            try:
                msg = json.loads(txt)
            except Exception:
                msg = {"type":"raw","payload": txt}
            try:
                await hub.handle(conn_id, msg)
            except Exception as e:
                # Never crash the socket loop on handler errors; report to client
                try:
                    await ws.send_text(json.dumps({"type": "error", "payload": f"server error: {e}"}))
                except Exception:
                    pass
    except WebSocketDisconnect:
        await hub.disconnect(conn_id)
        rooms.ensure_capacity()

@app.get('/seats')
def seats_status(room: str = Query(DEFAULT_ROOM_ID)):
    """Report which color seats are taken/available (best-effort; race-safe claims still enforced on connect)."""
    try:
        hub = _room_or_404(room)
        taken = list(hub.seat_owners.keys())
        avail = [s for s in COLOR_SEATS if s not in taken]
        # Shuffle available for caller-side random pick variety
        rnd = list(avail)
        random.shuffle(rnd)
        return JSONResponse({'ok': True, 'taken': taken, 'available': avail, 'available_shuffled': rnd})
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)


@app.get('/rooms')
def rooms_list():
    try:
        return JSONResponse({'ok': True, 'rooms': rooms.snapshot()})
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)


@app.get('/rooms/{room_id}')
def room_detail(room_id: str):
    try:
        hub = _room_or_404(room_id)
        return JSONResponse({'ok': True, 'room': hub.summary()})
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)


@app.post('/rooms')
def room_create(payload: Optional[RoomCreatePayload] = None):
    try:
        payload = payload or RoomCreatePayload()
        hub = rooms.create_room(room_id=payload.room_id, label=payload.label)
        return JSONResponse({'ok': True, 'room': hub.summary()})
    except ValueError as ve:
        return JSONResponse({'ok': False, 'error': str(ve)}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)


@app.delete('/rooms/{room_id}')
def room_delete(room_id: str):
    hub = _room_or_404(room_id)
    if hub.clients:
        raise HTTPException(status_code=400, detail="Room still has connected clients.")
    try:
        rooms.delete_room(room_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse({'ok': True})


@app.get("/")
def index():
    index_v3 = os.path.join(STATIC_DIR, 'index_v3.html')
    if os.path.exists(index_v3):
        return FileResponse(index_v3)
    index_path = os.path.join(STATIC_DIR, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Netplay server running</h1><p>No index.html found.</p>")

@app.get('/qr.png')
def qr_png(url: str):
    """Return a QR code PNG for the given URL. Fully offline (no CDN)."""
    if not url or len(url) > 512:
        return JSONResponse({'ok': False, 'error': 'invalid url'}, status_code=400)
    if qrcode is None:
        return JSONResponse({'ok': False, 'error': 'qrcode lib not installed'}, status_code=500)
    try:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        bio = io.BytesIO()
        img.save(bio, format='PNG')
        bio.seek(0)
        return HTMLResponse(bio.getvalue(), media_type='image/png')
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.post('/admin/new-game')
async def new_game(room: str = Query(DEFAULT_ROOM_ID)):
    try:
        hub = _room_or_404(room)
        res = await hub.reset_game()
        return JSONResponse({"ok": True, **res})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post('/admin/new-chess')
async def new_chess(room: str = Query(DEFAULT_ROOM_ID)):
    try:
        hub = _room_or_404(room)
        res = await hub.reset_game_chess()
        return JSONResponse({"ok": True, **res})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post('/admin/save-now')
def save_now(room: str = Query(DEFAULT_ROOM_ID)):
    """Persist the current game to the games/ folder without resetting.
    Returns { ok, saved, file? }.
    """
    try:
        hub = _room_or_404(room)
        res = hub._save_current_game()
        return JSONResponse(res)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

# Profile endpoints (require Supabase JWT)
@app.get('/profile')
def get_profile(request: Request):
    token = _extract_bearer_token(request)
    uid = get_user_id(token)
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid token")
    rows = _run_profile_query("select display_name, country from profiles where user_id = ?", (uid,))
    if not rows:
        return JSONResponse({'ok': False, 'error': 'not set'})
    return JSONResponse({'ok': True, 'display_name': rows[0][0], 'country': rows[0][1]})

@app.post('/profile')
async def set_profile(request: Request):
    token = _extract_bearer_token(request)
    uid = get_user_id(token)
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        payload = await request.json()
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid body")
    raw_name = payload.get('display_name', '')
    clean = _sanitize_display_name(raw_name)
    if len(clean) < 3:
        raise HTTPException(status_code=400, detail="Invalid name")
    country = _sanitize_country_code(payload.get('country')) if payload.get('country') else None
    try:
        _run_profile_query(
            "insert into profiles (user_id, display_name, country) values (?, ?, ?) "
            "on conflict(user_id) do update set display_name=excluded.display_name, "
            "country=coalesce(excluded.country, profiles.country)",
            (uid, clean, country)
        )
    except sqlite3.IntegrityError:
        return JSONResponse({'ok': False, 'error': 'taken'}, status_code=409)
    return JSONResponse({'ok': True, 'display_name': clean, 'country': country})

@app.get('/library/list')
def library_list(room: str = Query(DEFAULT_ROOM_ID)):
    try:
        hub = _room_or_404(room)
        room_dir = os.path.join(GAMES_DIR, hub.storage_slug)
        search_dir = room_dir
        if not os.path.isdir(search_dir) and hub.room_id == DEFAULT_ROOM_ID:
            search_dir = GAMES_DIR
        if not os.path.isdir(search_dir):
            return JSONResponse({'ok': True, 'items': [], 'room': hub.room_id})
        items = []
        for fn in sorted(os.listdir(search_dir)):
            if not fn.lower().endswith('.json'): continue
            fp = os.path.join(search_dir, fn)
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    j = json.load(f)
                items.append({
                    'name': fn,
                    'ended_at': j.get('ended_at'),
                    'moves': len(j.get('moves', [])),
                })
            except Exception:
                items.append({'name': fn, 'ended_at': None, 'moves': None})
        return JSONResponse({'ok': True, 'room': hub.room_id, 'items': items})
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.get('/library/game/{name}')
def library_game(name: str, room: str = Query(DEFAULT_ROOM_ID)):
    try:
        hub = _room_or_404(room)
        safe = os.path.basename(name)
        room_dir = os.path.join(GAMES_DIR, hub.storage_slug)
        path = os.path.join(room_dir, safe)
        if not os.path.exists(path) and hub.room_id == DEFAULT_ROOM_ID:
            legacy = os.path.join(GAMES_DIR, safe)
            if os.path.exists(legacy):
                path = legacy
        if not os.path.exists(path):
            return JSONResponse({'ok': False, 'error': 'not found'}, status_code=404)
        return FileResponse(path, media_type='application/json', filename=safe)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

@app.get('/debug/legal')
def debug_legal(limit: Optional[int] = 10, room: str = Query(DEFAULT_ROOM_ID)):
    try:
        hub = _room_or_404(room)
        lim = int(limit or 10)
        if lim < 1:
            lim = 1
        if lim > 200:
            lim = 200
        out = []
        for i, (sr, sc, er, ec) in enumerate(hub.engine.legal_moves_for_active()):
            if i >= lim:
                break
            out.append({'sr': int(sr), 'sc': int(sc), 'er': int(er), 'ec': int(ec)})
        return JSONResponse({'ok': True, 'count': len(out), 'moves': out})
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)
