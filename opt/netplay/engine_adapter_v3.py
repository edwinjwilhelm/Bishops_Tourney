import os
from typing import Any, Dict, List, Optional, Tuple
import sys
import time

try:
    import chess  # type: ignore
except Exception:  # pragma: no cover - python-chess is required for duel mode
    chess = None

DEFAULT_PIECE_VALUES: Dict[str, int] = {"K": 0, "Q": 9, "R": 5, "B": 3, "N": 3, "P": 1}
DUEL_HOLD_SECONDS = 0  # no duel delay; start immediately
DUEL_INTERACT_RELEASE_SECONDS = 0  # no follow-up hold after interaction

# Ensure pygame can initialize without opening a window
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from tools.engine_loader import EngineHandle, load_engine

# Load the engine module dynamically (supports multiple variants)
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
ENGINE_HANDLE: EngineHandle = load_engine()
engine = ENGINE_HANDLE.module
ENGINE_PATH = getattr(ENGINE_HANDLE, "path", None)
ENGINE_VERSION = getattr(engine, "__FILE_VERSION__", "unknown")
if ENGINE_PATH:
    print(f"[EngineAdapter] Engine path: {ENGINE_PATH} (version={ENGINE_VERSION})")
else:
    print(f"[EngineAdapter] Engine version={ENGINE_VERSION}")
ENGINE_VARIANT = ENGINE_HANDLE.variant
CH_MIN = getattr(engine, "CH_MIN", 2)
CH_MAX = CH_MIN + 7

def reload_engine() -> None:
    """Hot-reload the currently selected engine module from disk."""
    global engine, ENGINE_HANDLE, ENGINE_VARIANT
    ENGINE_HANDLE = load_engine(None, force_reload=True)
    engine = ENGINE_HANDLE.module
    ENGINE_VARIANT = ENGINE_HANDLE.variant
    _refresh_engine_bindings()
    _set_headless_alias()


def _pcolor_to_str(c: Any) -> str:
    return c.name


def _str_to_pcolor(s: str) -> Any:
    return PColor[s.upper()]


def _piece_value(kind: str) -> int:
    """Best-effort mapping of piece kind to material value."""
    try:
        fn = getattr(engine, "piece_value", None)
        if callable(fn):
            val = fn(kind)
            if val is not None:
                return int(val)
    except Exception:
        pass
    try:
        mapping = getattr(engine, "PIECE_VALUES", None)
        if isinstance(mapping, dict) and kind in mapping:
            return int(mapping[kind])
    except Exception:
        pass
    return int(DEFAULT_PIECE_VALUES.get(kind, 0))


def _refresh_engine_bindings() -> None:
    global PColor, Board
    PColor = getattr(engine, "PColor", None)
    Board = getattr(engine, "Board", None)
    if PColor is None or Board is None:
        raise RuntimeError("Loaded engine module is missing PColor/Board definitions required by netplay.")


_refresh_engine_bindings()


class GoldenHeadlessEngine:
    """Headless wrapper around Bishops_Golden.py for server use.

    Contract:
    - State: single Board() instance, turn index, optional forced_turn
    - Validation: only allow moves that are legal for the active color
    - Turn: advance clockwise; if checks created, set a one-move forced response (priority) like app
    - Serialization: JSON-friendly dict with board, alive, moves, and active color
    """

    def __init__(self) -> None:
        # Minimal global state used by consolidated two-player hooks; keep very small
        try:
            # Provide a stub gs so consolidated hooks that reference globals().get('gs') won't crash
            class _StubGS:
                two_stage_active = False
                final_a = None
                final_b = None
                chess_lock = False
                grace_active = False
                grace_turns_remaining = 0
                # Desktop parity: allow White duel boost heuristics in strict duel
                white_duel_boost = True
                # Winner (if determined by the host engine loop); kept for parity
                last_winner = None
                # Half-move count since start; used to detect first-round restrictions
                half_moves = 0
                recent_moves = []
                pos_counts = {}
                entered = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}
                reduced_applied = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}
                elim_flash_color = None
                # Default pawn forward directions used by engine for move gen
                # WHITE/PINK move upwards (-1 row), BLACK/GREY down/right respectively per engine logic
                pawn_dir = {PColor.WHITE: -1, PColor.BLACK: 1, PColor.GREY: 1, PColor.PINK: -1}
                # Corner sanctuary state mirrors desktop GameState defaults
                corner_immune = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}
                corner_promoted = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}
                corner_evict_pending = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}
                corner_in_corner = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}
                # Duel/teleport bookkeeping used by desktop loop
                _tp_consolidated_done = False
                _duel_started = False
                _duel_cleared_board = False
                _finalists_prep_started = False
                _flash_until = 0
                _teleport_after = 0
                _duel_delay_until = 0
                _duel_banner = None
                # Misc flags referenced by UI/logic in engine
                waiting_ready = False
                freeze_advance = False
                player_is_ai = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}
                ai_delay_applied = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}
                _elim_skip_cleanup = set()
            engine.gs = _StubGS()  # type: ignore[attr-defined]
        except Exception:
            pass

        self.board: Any = Board()
        self.turn_i: int = 0  # index into TURN_ORDER
        self.forced_turn: Optional[Any] = None
        self.moves_list: List[Dict[str, Any]] = []
        # Track captured material points by victim color (WHITE/GREY/BLACK/PINK)
        try:
            self.captured_points = {PColor.WHITE: 0, PColor.GREY: 0, PColor.BLACK: 0, PColor.PINK: 0}
        except Exception:
            self.captured_points = {}
        try:
            colors = [engine.PColor.WHITE, engine.PColor.GREY, engine.PColor.BLACK, engine.PColor.PINK]
        except Exception:
            colors = []
        self.swap_available = {col: True for col in colors}
        # Chess-only mode state
        self.chess_mode: bool = False
        self.chess_board: Optional[chess.Board] = None


        self._duel_ready_epoch: int = 0
        self._duel_ready_time: float = 0.0
        self._duel_chess: Optional['chess.Board'] = None
        self._duel_winner: Optional[Any] = None
    def _duel_active(self) -> bool:
        return self._duel_chess is not None

    def _engine_to_chess_square(self, r: int, c: int) -> Optional[int]:
        if chess is None:
            raise RuntimeError('python-chess is required for duel mode')
        if not (2 <= r <= 9 and 2 <= c <= 9):
            return None
        file = c - 2
        rank = 8 - (r - 2)
        if not (0 <= file < 8 and 1 <= rank <= 8):
            return None
        return chess.square(file, rank - 1)

    def _chess_to_engine_rc(self, square: int) -> Tuple[int, int]:
        file = chess.square_file(square)
        rank = chess.square_rank(square) + 1
        r = 2 + (8 - rank)
        c = 2 + file
        return r, c

    def _sync_duel_board(self) -> None:
        if not self._duel_active():
            return
        for r in range(engine.BOARD_SIZE):
            for c in range(engine.BOARD_SIZE):
                piece = self.board.get(r, c)
                if piece and piece.color in (engine.PColor.WHITE, engine.PColor.BLACK):
                    self.board.set(r, c, None)
        if self._duel_chess is None:
            return
        for square in chess.SQUARES:
            piece = self._duel_chess.piece_at(square)
            if piece is None:
                continue
            r, c = self._chess_to_engine_rc(square)
        self._duel_active_last: bool = False

    # ---- Helpers ----
    def _ensure_alive_active(self) -> Any:
        """Return an alive color to move; skip eliminated colors and normalize pointers."""
        try:
            alive = self.alive_colors()
            # Normalize forced turn if it points to a dead color
            if self.forced_turn is not None and self.forced_turn not in alive:
                self.forced_turn = None
            act = self.forced_turn if self.forced_turn is not None else engine.TURN_ORDER[self.turn_i]
            if act in alive:
                return act
            # Advance to next alive color clockwise
            try:
                idx = engine.TURN_ORDER.index(act)
            except Exception:
                idx = 0
            for i in range(1, 5):
                cand = engine.TURN_ORDER[(idx + i) % 4]
                if cand in alive:
                    # Keep baseline turn_i aligned with this alive color
                    try:
                        self.turn_i = engine.TURN_ORDER.index(cand)
                    except Exception:
                        pass
                    return cand
            # Fallback
            return alive[0] if alive else engine.TURN_ORDER[self.turn_i]
        except Exception:
            return self.forced_turn if self.forced_turn is not None else engine.TURN_ORDER[self.turn_i]

    def active_color(self) -> Any:
        if self.chess_mode and self.chess_board is not None:
            return engine.PColor.WHITE if self.chess_board.turn else engine.PColor.BLACK
        return self._ensure_alive_active()

    def alive_colors(self) -> List[Any]:
        if self.chess_mode:
            return [engine.PColor.WHITE, engine.PColor.BLACK]
        alive = self.board.alive_colors()
        try:
            gs = getattr(engine, 'gs', None)
            if gs is not None and bool(getattr(gs, 'two_stage_active', False)) and bool(getattr(gs, 'chess_lock', False)):
                white = getattr(engine.PColor, 'WHITE', None)
                black = getattr(engine.PColor, 'BLACK', None)
                duo = [c for c in (white, black) if c is not None]
                if duo:
                    return duo
        except Exception:
            pass
        return alive

    def serialize_board(self) -> List[List[Optional[Dict[str, str]]]]:
        if self.chess_mode and self.chess_board is not None:
            grid: List[List[Optional[Dict[str, str]]]] = [[None for _ in range(engine.BOARD_SIZE)] for _ in range(engine.BOARD_SIZE)]
            for square in chess.SQUARES:
                piece = self.chess_board.piece_at(square)
                if piece is None:
                    continue
                file = chess.square_file(square)
                rank = chess.square_rank(square)
                # map rank 0(bottom) -> row 9, rank7(top)-> row2
                r = 9 - rank
                c = 2 + file
                color = engine.PColor.WHITE if piece.color else engine.PColor.BLACK
                grid[r][c] = {"kind": piece.symbol().upper(), "color": color.name}
            return grid
        grid: List[List[Optional[Dict[str, str]]]] = []
        for r in range(engine.BOARD_SIZE):
            row: List[Optional[Dict[str, str]]] = []
            for c in range(engine.BOARD_SIZE):
                p = self.board.get(r, c)
                if p is None:
                    row.append(None)
                else:
                    row.append({"kind": p.kind, "color": p.color.name})
            grid.append(row)
        return grid

    def serialize_state(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "turn": self.active_color().name,
            "board": self.serialize_board(),
            "alive": [c.name for c in self.alive_colors()],
            "moves": list(self.moves_list),
        }
        try:
            in_check: List[str] = []
            if not self.chess_mode and hasattr(engine, "king_in_check"):
                for col in self.alive_colors():
                    try:
                        if engine.king_in_check(self.board, col):
                            in_check.append(col.name)
                    except Exception:
                        pass
            out["in_check"] = in_check
        except Exception:
            out["in_check"] = []
        try:
            out['swap_available'] = {col.name: bool(self.swap_available.get(col, False)) for col in getattr(engine, 'TURN_ORDER', [])}
        except Exception:
            out['swap_available'] = {}
        # Echo auto-elimination threshold if present on engine.gs
        try:
            gs_obj = getattr(engine, 'gs', None)
            if gs_obj is not None:
                thr = int(getattr(gs_obj, 'auto_elim_threshold', 0) or 0)
                out['auto_elim_threshold'] = thr
        except Exception:
            pass
        # Include consolidated two-player stage information from engine.gs if available
        try:
            gs = getattr(engine, 'gs', None)
            if gs is not None:
                finals = []
                try:
                    a = getattr(gs, 'final_a', None)
                    b = getattr(gs, 'final_b', None)
                    finals = [a.name if a is not None else None, b.name if b is not None else None]
                except Exception:
                    finals = [None, None]
                entered_map: Dict[str, bool] = {}
                try:
                    ent = getattr(gs, 'entered', {}) or {}
                    for k, v in ent.items():
                        try:
                            # keys may be PColor or strings
                            name = k.name if hasattr(k, 'name') else str(k)
                            entered_map[name] = bool(v)
                        except Exception:
                            pass
                except Exception:
                    entered_map = {}
                chess_lock = bool(getattr(gs, 'chess_lock', False))
                out["two_stage"] = {
                    "active": bool(getattr(gs, 'two_stage_active', False)),
                    "finals": finals,
                    "entered": entered_map,
                    "grace_active": bool(getattr(gs, 'grace_active', False)),
                    "grace_turns_remaining": int(getattr(gs, 'grace_turns_remaining', 0) or 0),
                    "chess_lock": chess_lock,
                }
                if bool(getattr(gs, 'two_stage_active', False)):
                    epoch_val = int(getattr(gs, 'duel_epoch', 0) or 0)
                    prev_active = self._duel_active_last
                    self._duel_active_last = True
                    if epoch_val != self._duel_ready_epoch or not prev_active:
                        self._duel_ready_epoch = epoch_val
                        self._duel_ready_time = time.monotonic() + DUEL_HOLD_SECONDS
                    remaining = max(0.0, self._duel_ready_time - time.monotonic()) if self._duel_ready_time else 0.0
                    wait_ms = int(round(remaining * 1000))
                    out["duel"] = {
                        "active": True,
                        "epoch": epoch_val,
                        "white_origin": "WHITE",
                        "black_origin": "BLACK",
                        "white_origin_ai": False,
                        "black_origin_ai": False,
                        "white_ai": bool(getattr(gs, 'player_is_ai', {}).get(getattr(engine.PColor, 'WHITE'), False)) if hasattr(engine, 'PColor') else False,
                        "black_ai": bool(getattr(gs, 'player_is_ai', {}).get(getattr(engine.PColor, 'BLACK'), False)) if hasattr(engine, 'PColor') else False,
                        "ready": wait_ms <= 0,
                        "wait_ms": wait_ms,
                        "eliminated": ["GREY", "PINK"],
                    }
                else:
                    self._duel_ready_epoch = 0
                    self._duel_ready_time = 0.0
                    self._duel_active_last = False
                    out["duel"] = {"active": False, "ready": True, "wait_ms": 0, "eliminated": []}
        except Exception:
            pass
        return out

    def mark_duel_ready(self) -> None:
        """Release any outstanding duel hold immediately."""
        self._duel_ready_time = time.monotonic() + DUEL_INTERACT_RELEASE_SECONDS

    # ---- Validation ----
    def _swap_moves_for(self, color):
        try:
            available = bool(self.swap_available.get(color, False))
        except Exception:
            available = False
        if not available:
            return []
        try:
            king_pos = self.board.find_king(color)
        except Exception:
            king_pos = None
        if not king_pos:
            return []
        kr, kc = king_pos
        try:
            for rr in range(engine.BOARD_SIZE):
                for cc in range(engine.BOARD_SIZE):
                    piece = self.board.get(rr, cc)
                    if piece and getattr(piece, 'color', None) == color and piece.kind == 'Q':
                        return [(rr, cc, kr, kc)]
        except Exception:
            return []
        return []

    def legal_moves_for_active(self) -> List[Tuple[int, int, int, int]]:
        color = self.active_color()
        moves: List[Tuple[int, int, int, int]] = []
        # Enumerate per piece to tolerate engine variants that yield (er,ec) pairs
        for r in range(engine.BOARD_SIZE):
            for c in range(engine.BOARD_SIZE):
                p = self.board.get(r, c)
                if p is None or p.color != color:
                    continue
                try:
                    base = engine.legal_moves_for_piece(self.board, r, c)
                except Exception:
                    base = []
                for mv in base:
                    try:
                        if isinstance(mv, (list, tuple)) and len(mv) == 4:
                            r0, c0, r1, c1 = mv
                            moves.append((int(r0), int(c0), int(r1), int(c1)))
                        elif isinstance(mv, (list, tuple)) and len(mv) == 2:
                            er, ec = mv
                            moves.append((r, c, int(er), int(ec)))
                    except Exception:
                        continue
        try:
            for swap_move in self._swap_moves_for(color):
                moves.append(tuple(int(x) for x in swap_move))
        except Exception:
            pass

        # Apply two-player constraints like the desktop engine
        try:
            gs = getattr(engine, 'gs', None)
            two_stage = bool(getattr(gs, 'two_stage_active', False))
            chess_lock = bool(getattr(gs, 'chess_lock', False))
            # chess_lock: keep only moves that end inside the 8x8
            if two_stage and chess_lock:
                moves = [(r0, c0, r1, c1) for (r0, c0, r1, c1) in moves if engine.in_chess_area(r1, c1)]
            # must-enter filter is only relevant before the duel when kings must approach the arena
            skip_must_enter = two_stage and chess_lock and color in (getattr(engine.PColor, 'WHITE', None), getattr(engine.PColor, 'BLACK', None))
            if two_stage and not skip_must_enter and hasattr(engine, 'must_enter_filter_for'):
                try:
                    filt = engine.must_enter_filter_for(self.board, color)
                    if callable(filt):
                        moves = list(filt(moves))
                except Exception:
                    pass
        except Exception:
            pass
        return moves

    def is_legal_move(self, sr: int, sc: int, er: int, ec: int) -> bool:
        if self.chess_mode and self.chess_board is not None:
            if not (2 <= sr <= 9 and 2 <= sc <= 9 and 2 <= er <= 9 and 2 <= ec <= 9):
                return False
            file_from, rank_from = sc - 2, 9 - sr
            file_to, rank_to = ec - 2, 9 - er
            try:
                move = chess.Move.from_uci(f"{chr(ord('a')+file_from)}{rank_from+1}{chr(ord('a')+file_to)}{rank_to+1}")
            except Exception:
                return False
            return move in self.chess_board.legal_moves
        color = self.active_color()
        p = self.board.get(sr, sc)
        if p is None or p.color != color:
            return False
        for (r0, c0, r1, c1) in self.legal_moves_for_active():
            if r0 == sr and c0 == sc and r1 == er and c1 == ec:
                return True
        return False

    # ---- Apply move and advance turn ----
    def apply_move(self, seat: str, sr: int, sc: int, er: int, ec: int) -> Dict[str, Any]:
        try:
            seat_color = _str_to_pcolor(seat)
        except Exception:
            return {"ok": False, "error": f"Unknown seat '{seat}'"}
        if hasattr(engine, "is_corner_square") and engine.is_corner_square(er, ec):
            return {"ok": False, "error": "Corner squares are off limits"}
        if self.chess_mode and self.chess_board is not None:
            active = self.active_color()
            if seat_color != active:
                return {"ok": False, "error": f"Not {seat_color.name}'s turn"}
            if not (2 <= sr <= 9 and 2 <= sc <= 9 and 2 <= er <= 9 and 2 <= ec <= 9):
                return {"ok": False, "error": "Move out of bounds"}
            file_from, rank_from = sc - 2, 9 - sr
            file_to, rank_to = ec - 2, 9 - er
            try:
                move = chess.Move.from_uci(f"{chr(ord('a')+file_from)}{rank_from+1}{chr(ord('a')+file_to)}{rank_to+1}")
            except Exception:
                return {"ok": False, "error": "Invalid move format"}
            # Auto-queen promotion
            piece = self.chess_board.piece_at(chess.square(file_from, rank_from))
            if piece and piece.piece_type == chess.PAWN and rank_to in (0, 7):
                move = chess.Move(move.from_square, move.to_square, promotion=chess.QUEEN)
            if move not in self.chess_board.legal_moves:
                return {"ok": False, "error": "Illegal move"}
            pre_target = self.chess_board.piece_at(move.to_square)
            try:
                self.chess_board.push(move)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
            record = {
                "by": seat_color.name,
                "sr": sr, "sc": sc, "er": er, "ec": ec,
                "cap": pre_target.symbol().upper() if pre_target else None,
                "promoted": bool(move.promotion),
            }
            self.moves_list.append(record)
            return {"ok": True}
        active = self.active_color()
        if seat_color != active:
            return {"ok": False, "error": f"Not {seat_color.name}'s turn (active: {getattr(active, 'name', active)})"}

        piece = self.board.get(sr, sc)
        dest_piece = self.board.get(er, ec)
        swap_requested = bool(
            self.swap_available.get(seat_color, False)
            and piece is not None
            and dest_piece is not None
            and getattr(piece, 'color', None) == seat_color
            and getattr(dest_piece, 'color', None) == seat_color
            and getattr(piece, 'kind', None) == 'Q'
            and getattr(dest_piece, 'kind', None) == 'K'
        )

        if swap_requested:
            pre_target = dest_piece
            self.board.set(sr, sc, dest_piece)
            self.board.set(er, ec, piece)
            promoted = False
            self.swap_available[seat_color] = False
        else:
            if not self.is_legal_move(sr, sc, er, ec):
                return {"ok": False, "error": "Illegal move"}
            pre_target = self.board.get(er, ec)
            cap, prev_has, prev_kind, eff = engine.board_do_move(self.board, sr, sc, er, ec, simulate=False)
            promoted = bool(eff.get("promoted")) if isinstance(eff, dict) else False
            self.swap_available[seat_color] = False

        record = {"by": seat_color.name, "sr": sr, "sc": sc, "er": er, "ec": ec}
        if swap_requested:
            record["cap"] = None
            record["promoted"] = False
            record["swap"] = True
        else:
            record["cap"] = (pre_target.kind if pre_target else None)
            record["promoted"] = promoted
        self.moves_list.append(record)

        if pre_target is not None and not swap_requested:
            try:
                val = _piece_value(pre_target.kind)
                try:
                    self.captured_points[pre_target.color] = int(self.captured_points.get(pre_target.color, 0)) + val
                except Exception:
                    pass
            except Exception:
                pass

        victims: List[Any] = []
        for col in self.alive_colors():
            if col == seat_color:
                continue
            try:
                if engine.king_in_check(self.board, col):
                    victims.append(col)
            except Exception:
                pass

        def clockwise_from(color: Any, candidates: List[Any]) -> Optional[Any]:
            if not candidates:
                return None
            idx = engine.TURN_ORDER.index(color)
            for i in range(1, 5):
                nxt = engine.TURN_ORDER[(idx + i) % 4]
                if nxt in candidates:
                    return nxt
            return candidates[0]

        self.forced_turn = clockwise_from(seat_color, victims) if victims else None

        if self.forced_turn is None:
            self.turn_i = (engine.TURN_ORDER.index(seat_color) + 1) % 4
        else:
            self.turn_i = (engine.TURN_ORDER.index(seat_color) + 1) % 4

        try:
            gs = getattr(engine, 'gs', None)
            try:
                engine.activate_two_stage_if_needed(self.board, gs)
            except Exception:
                pass
            try:
                if getattr(engine, 'DUEL_TELEPORT_ON_TWO', False):
                    self._auto_force_duel(gs)
            except Exception:
                pass
            if gs is not None and getattr(gs, 'two_stage_active', False):
                finals = [getattr(gs, 'final_a', None), getattr(gs, 'final_b', None)]
                for col in finals:
                    if col is None:
                        continue
                    entered = False
                    try:
                        for rr in range(engine.BOARD_SIZE):
                            if entered:
                                break
                            for cc in range(engine.BOARD_SIZE):
                                p = self.board.get(rr, cc)
                                if p and p.color == col and engine.in_chess_area(rr, cc):
                                    entered = True
                                    break
                    except Exception:
                        entered = False
                    try:
                        gs.entered[col] = entered
                    except Exception:
                        pass
                try:
                    a, b = finals[0], finals[1]
                    if a is not None and b is not None:
                        if bool(gs.entered.get(a, False)) and bool(gs.entered.get(b, False)) and not getattr(gs, 'grace_active', False):
                            gs.grace_active = True
                            gs.grace_turns_remaining = 2
                except Exception:
                    pass
                try:
                    if hasattr(engine, 'apply_queen_reduction_if_needed'):
                        for col in finals:
                            if col is not None:
                                engine.apply_queen_reduction_if_needed(col)
                except Exception:
                    pass
                try:
                    if not getattr(gs, 'chess_lock', False) and engine.both_fully_migrated_incl_kings(self.board):
                        gs.chess_lock = True
                except Exception:
                    pass
            try:
                two_active = bool(getattr(gs, 'two_stage_active', False))
                thr = int(getattr(gs, 'auto_elim_threshold', 0) or 0)
                if not two_active and thr > 0 and not swap_requested:
                    victim: Optional[Any] = None
                    try:
                        for col, pts in (self.captured_points or {}).items():
                            if col in self.alive_colors() and int(pts) >= thr:
                                victim = col
                                break
                    except Exception:
                        victim = None
                    if victim is not None:
                        self._eliminate_color(victim, reason="auto-elim")
            except Exception:
                pass
        except Exception:
            pass

        if not self._duel_chess:
            try:
                gs = getattr(engine, 'gs', None)
                if not (gs and getattr(gs, 'chess_lock', False)):
                    self._apply_checkmate_eliminations()
            except Exception:
                self._apply_checkmate_eliminations()
        try:
            alive_now = self.alive_colors()
            if self.forced_turn is not None and self.forced_turn not in alive_now:
                self.forced_turn = None
        except Exception:
            pass
        return {"ok": True}


    def _after_duel_seed(self) -> None:
        """Align turn pointer and clear forced-turn once the duel chess board is seeded."""
        self.forced_turn = None
        try:
            white_enum = getattr(engine.PColor, 'WHITE')
        except Exception:
            white_enum = None
        try:
            if white_enum is not None and white_enum in engine.TURN_ORDER:
                self.turn_i = engine.TURN_ORDER.index(white_enum)
            else:
                alive = self.alive_colors()
                if alive:
                    self.turn_i = engine.TURN_ORDER.index(alive[0])
        except Exception:
            self.turn_i = 0
        # Reset captured points to avoid legacy elimination thresholds influencing duel
        try:
            for key in list(self.captured_points.keys()):
                self.captured_points[key] = 0
        except Exception:
            pass
        try:
            gs = getattr(engine, 'gs', None)
            if gs is not None:
                gs.chess_lock = True
        except Exception:
            pass
        try:
            epoch_val = int(getattr(engine.gs, 'duel_epoch', 0) or 0)
        except Exception:
            epoch_val = 0
        self._duel_ready_epoch = epoch_val
        self._duel_ready_time = time.monotonic() + DUEL_HOLD_SECONDS
        self._duel_active_last = True
    def _manual_eliminate(self, color: Any) -> None:
        try:
            for rr in range(engine.BOARD_SIZE):
                for cc in range(engine.BOARD_SIZE):
                    piece = self.board.get(rr, cc)
                    if piece and getattr(piece, "color", None) == color:
                        self.board.set(rr, cc, None)
        except Exception:
            pass

    def _eliminate_color(self, color: Any, *, reason: str = "capture") -> None:
        try:
            elim_fn = getattr(engine, 'eliminate_color', None)
            gs = getattr(engine, 'gs', None)
            if callable(elim_fn):
                handled = bool(elim_fn(self.board, gs, color, reason=reason, flash=False))
                if not handled:
                    self._manual_eliminate(color)
            else:
                self._manual_eliminate(color)
        except Exception:
            self._manual_eliminate(color)
        if self.forced_turn == color:
            self.forced_turn = None
        try:
            alive = self.alive_colors()
            if alive:
                current = engine.TURN_ORDER[self.turn_i]
                if current == color or current not in alive:
                    for _ in range(4):
                        self.turn_i = (self.turn_i + 1) % 4
                        candidate = engine.TURN_ORDER[self.turn_i]
                        if candidate in alive:
                            break
        except Exception:
            pass
        try:
            self.captured_points.pop(color, None)
        except Exception:
            pass

    def _apply_checkmate_eliminations(self) -> None:
        try:
            alive = list(self.alive_colors())
        except Exception:
            alive = []
        pending: List[Any] = []
        for col in alive:
            try:
                if engine.king_in_check(self.board, col):
                    legal = engine.all_legal_moves_for_color(self.board, col)
                    if not legal:
                        pending.append(col)
            except Exception:
                continue
        for col in pending:
            self._eliminate_color(col, reason="checkmate")

    def _auto_force_duel(self, gs: Any) -> None:
        """Teleport into the strict chess duel automatically when two colours remain."""
        if gs is None:
            return
        try:
            alive = self.alive_colors()
        except Exception:
            alive = []
        if len(alive) != 2:
            return
        if getattr(gs, '_tp_consolidated_done', False) or getattr(gs, 'chess_lock', False):
            return
        force_fn = getattr(engine, '_force_duel_now', None)
        if not callable(force_fn):
            return
        try:
            ok = force_fn(self.board, gs)
        except Exception:
            ok = False
        if ok:
            self._after_duel_seed()

    def force_duel(self) -> bool:
        """Expose a manual duel trigger for the server control panel."""
        gs = getattr(engine, 'gs', None)
        if gs is None:
            return False
        try:
            engine.activate_two_stage_if_needed(self.board, gs)
        except Exception:
            pass
        force_fn = getattr(engine, '_force_duel_now', None)
        if not callable(force_fn):
            return False
        try:
            ok = bool(force_fn(self.board, gs))
        except Exception:
            ok = False
        if ok:
            self._after_duel_seed()
        return ok

    def swap_kq(self, seat: str) -> bool:
        """Swap the king and queen for the given seat/colour."""
        try:
            color = _str_to_pcolor(seat)
        except Exception:
            return False
        if color is None:
            return False
        try:
            king_pos = self.board.find_king(color)
        except Exception:
            king_pos = None
        if not king_pos:
            return False
        qr = qc = None
        queen_piece = None
        try:
            for rr in range(engine.BOARD_SIZE):
                for cc in range(engine.BOARD_SIZE):
                    piece = self.board.get(rr, cc)
                    if piece and getattr(piece, 'color', None) == color and piece.kind == 'Q':
                        qr, qc, queen_piece = rr, cc, piece
                        raise StopIteration
        except StopIteration:
            pass
        except Exception:
            queen_piece = None
        if queen_piece is None or qr is None or qc is None:
            return False
        kr, kc = king_pos
        king_piece = self.board.get(kr, kc)
        if king_piece is None:
            return False
        if (kr, kc) == (qr, qc):
            return False
        self.board.set(kr, kc, queen_piece)
        self.board.set(qr, qc, king_piece)
        return True

    # ---- Special resets ----
    def reset_chess_only(self) -> None:
        """Reset the engine to a pure 8×8 WHITE vs BLACK chess setup in the central board."""
        try:
            if hasattr(engine, 'init_chess_only_board') and callable(engine.init_chess_only_board):
                self.board = engine.init_chess_only_board()
            else:
                raise RuntimeError("init_chess_only_board is missing; cannot seed FIDE chess.")
            self.turn_i = 0  # WHITE to move
            self.forced_turn = None
            self.moves_list = []
            self.chess_mode = True
            self.chess_board = chess.Board()
            # Reset captured points only for active colors
            try:
                self.captured_points = {PColor.WHITE:0, PColor.BLACK:0}
            except Exception:
                self.captured_points = {}
        except Exception:
            pass


# Convenience factory for the server
class EggHeadlessEngine:
    """Headless wrapper for the clean-room Bishops_Golden_egg ruleset."""

    def __init__(self) -> None:
        self.game = engine.BishopsGoldenEggGame()
        self.board = self.game.board
        self.moves_list: List[Dict[str, Any]] = []
        self.captured_points: Dict[Any, int] = {color: 0 for color in engine.PColor}
        self.forced_turn: Optional[Any] = None
        self.turn_i: int = 0
        self._sync_turn_index()

    def _sync_turn_index(self) -> None:
        try:
            base_color = self.game.alive[self.game.turn_index]
        except Exception:
            base_color = engine.TURN_ORDER[0]
        try:
            self.turn_i = engine.TURN_ORDER.index(base_color)
        except ValueError:
            self.turn_i = 0
        self.forced_turn = getattr(self.game, "forced_turn", None)

    def active_color(self) -> Any:
        return self.game.active_color()

    def alive_colors(self) -> List[Any]:
        return list(self.game.alive)

    def serialize_board(self) -> List[List[Optional[Dict[str, str]]]]:
        grid: List[List[Optional[Dict[str, str]]]] = []
        size = getattr(engine, "BOARD_SIZE", 12)
        for r in range(size):
            row: List[Optional[Dict[str, str]]] = []
            for c in range(size):
                p = self.board.get(r, c)
                if p is None:
                    row.append(None)
                else:
                    row.append({"kind": p.kind, "color": p.color.name})
            grid.append(row)
        return grid

    def serialize_state(self) -> Dict[str, Any]:
        phase = getattr(self.game, "phase", None)
        phase_name = getattr(phase, "name", "UNKNOWN")
        winner = getattr(self.game, "winner", None)
        out: Dict[str, Any] = {
            "turn": self.active_color().name,
            "board": self.serialize_board(),
            "alive": [c.name for c in self.alive_colors()],
            "moves": list(self.moves_list),
            "phase": phase_name,
            "winner": getattr(winner, "name", None) if winner is not None else None,
        }
        try:
            out["forced_turn"] = getattr(self.forced_turn, "name", None)
        except Exception:
            out["forced_turn"] = None
        # Provide a compatible two_stage block (egg uses DUEL terminology)
        duel_active = (phase_name.upper() == "DUEL")
        out["two_stage"] = {
            "active": duel_active,
            "finals": [c.name for c in self.game.alive],
            "entered": {},
            "grace_active": False,
            "grace_turns_remaining": 0,
            "chess_lock": duel_active,
        }
        return out

    def legal_moves_for_active(self) -> List[Tuple[int, int, int, int]]:
        moves: List[Tuple[int, int, int, int]] = []
        try:
            for mv in self.game.legal_moves():
                if mv.start is None or mv.end is None:
                    continue
                sr, sc = mv.start
                er, ec = mv.end
                moves.append((int(sr), int(sc), int(er), int(ec)))
        except Exception:
            pass
        return moves

    def _lookup_move(self, sr: int, sc: int, er: int, ec: int) -> Optional[Any]:
        try:
            for mv in self.game.legal_moves():
                if mv.start is None or mv.end is None:
                    continue
                if int(mv.start[0]) == sr and int(mv.start[1]) == sc and int(mv.end[0]) == er and int(mv.end[1]) == ec:
                    return mv
        except Exception:
            pass
        return None

    def is_legal_move(self, sr: int, sc: int, er: int, ec: int) -> bool:
        return self._lookup_move(sr, sc, er, ec) is not None

    def apply_move(self, seat: str, sr: int, sc: int, er: int, ec: int) -> Dict[str, Any]:
        try:
            seat_color = _str_to_pcolor(seat)
        except Exception:
            return {"ok": False, "error": f"Unknown seat '{seat}'"}
        if hasattr(engine, "is_corner_square") and engine.is_corner_square(er, ec):
            return {"ok": False, "error": "Corner squares are off limits"}
        active = self.active_color()
        if seat_color != active:
            return {"ok": False, "error": f"Not {seat_color.name}'s turn (active: {getattr(active, 'name', active)})"}

        move = self._lookup_move(sr, sc, er, ec)
        if move is None:
            return {"ok": False, "error": "Illegal move"}

        pre_target = self.board.get(er, ec)
        try:
            self.game.apply_move(move)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        # Re-sync board pointer in case the game replaced it during duel reset
        self.board = self.game.board
        self.moves_list.append({
            "by": seat_color.name,
            "sr": sr,
            "sc": sc,
            "er": er,
            "ec": ec,
            "cap": (pre_target.kind if pre_target else None),
            "promoted": bool(getattr(move, "promotion", None)),
        })

        if pre_target is not None:
            try:
                self.captured_points[pre_target.color] = int(self.captured_points.get(pre_target.color, 0)) + _piece_value(pre_target.kind)
            except Exception:
                pass

        self._sync_turn_index()
        return {"ok": True}

    def swap_kq(self, seat: str) -> bool:
        return False

    def reset_chess_only(self) -> None:
        """Seed a fresh duel (8x8) per egg rules."""
        # For chess-only, use the golden initializer if available; otherwise reset to empty board
        if hasattr(engine, 'init_chess_only_board') and callable(engine.init_chess_only_board):
            self.board = engine.init_chess_only_board()
        else:
            self.board = Board()
        self.game = None
        self.moves_list.clear()
        try:
            self.captured_points = {engine.PColor.WHITE: 0, engine.PColor.BLACK: 0}
        except Exception:
            self.captured_points = {}
        self.forced_turn = None
        self.turn_i = 0
        self.chess_mode = True
        self.chess_board = chess.Board()


def _set_headless_alias() -> None:
    global HeadlessEngine
    if ENGINE_VARIANT == "golden":
        HeadlessEngine = GoldenHeadlessEngine
    elif ENGINE_VARIANT == "egg":
        HeadlessEngine = EggHeadlessEngine
    else:
        raise RuntimeError(f"Unsupported engine variant '{ENGINE_VARIANT}' for netplay headless adapter.")


_set_headless_alias()


def create_engine() -> "HeadlessEngine":
    return HeadlessEngine()
