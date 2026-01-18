import os

import sys

import json

import math

import random

from enum import Enum

from typing import List, Dict, Tuple, Optional, Set

import datetime

import time

import pygame

from collections import deque

import hashlib
import threading

# Bishops: Four-Player Chess  v1.6.4 (Consolidated Two-Player Mode)

# NOTE: Keep window RESIZABLE|SCALED (not true fullscreen) so the

# OS taskbar stays visible and the app remains responsive.

# ============================================================

# =====================  HARD REMINDER  ======================

# DO NOT DELETE proven-good logic. Add features append-only where

# possible; keep prior behaviors intact unless explicitly changed.

# ============================================================



# ====== CONFIG ======

BOARD_SIZE = 12

SQUARE = 56

DEFAULT_SQUARE = 60

LOGICAL_W  = BOARD_SIZE * SQUARE          # 672

LOGICAL_H  = BOARD_SIZE * SQUARE + 44     # 716 (incl. status)

# Scaling and layout safety

SAFE_BOTTOM_MARGIN = 8   # pixels to leave free at bottom (sit closer to taskbar)

# Fine-tuning for initial window geometry (can be adjusted per laptop)

WINDOW_Y_OFFSET_PX = 30      # lower the window from the top by ~30px

EXTRA_WINDOW_HEIGHT_PX = 20  # ~0.2 inches taller at 96 DPI (~19px)

MIN_SQUARE = 36          # do not shrink squares below this for readability



# Right dock (sidebar)

SIDEBAR_W_MIN = 340

TOTAL_W       = LOGICAL_W + SIDEBAR_W_MIN



LIGHT = (240, 217, 181)

DARK  = (181, 136, 99)

HL    = (255, 255, 0)

OUTLINE  = (20, 20, 20)

BANNER_OK = (35, 35, 35)



MOVE_DELAY_MS = 500

ELIM_FLASH_MS = 3000

ELIM_FLASH_RATE_MS = 250



CH_MIN = 2

CH_MAX = 9



SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

ASSET_DIR  = os.path.join(SCRIPT_DIR, "pieces")

SETTINGS_PATH = os.path.join(SCRIPT_DIR, "bishops_settings.json")

WINDOW_ICON_PATH = os.path.join(SCRIPT_DIR, "helmet_icon.png")



VERSION_STR = "Bishops: Four-Player Chess  v1.6.5"



# ====== Feature Flags (ruleset switches) ======

# Keep legacy migration code available but disabled by default for this ruleset.

ENABLE_MIGRATION: bool = False

# New rule: when exactly two players remain, teleport into a standard Chess duel.

DUEL_TELEPORT_ON_TWO: bool = True



# ====== Prose/Technical Rules (reference only; not used by logic) ======

# Paste updated rules into RULES_REFERENCE below. This block is intentionally unused by

# the engine so it won't affect behavior. Keep as documentation within the code file.

RULES_REFERENCE = r"""

Bishops - Master Rules (v3)



This ruleset replaces migration with a direct Chess duel when exactly two players remain.



1) Players and Seats

- Four players: White, Grey, Black, Pink.

- Seat mapping for the final duel (when only two survivors remain):

    - If White or Black survives, they keep their native seat; the other survivor takes the opposite seat.

    - If neither White nor Black survives (e.g., Pink and Grey), then Pink takes the White seat and Grey takes the Black seat.

- White seat moves first in the duel.



2) Survival Phase

- All four players play on the full Bishops board. A total of 128 squares are used and in play.

- Each colour's 2x2 home corner acts as a sanctuary for its king:

    - On the first entry into that corner, any surviving friendly bishops immediately promote to queens, giving that colour three queens total when both bishops were present.

    - All three queens are interchangeable. While the king remains in the sanctuary, immunity applies only if three friendly queens are still on the board. Dropping to one or zero queens (i.e., losing any two of the three) forces the king to evacuate the corner on its next move if a legal exit exists.

    - If no legal exit square exists outside the corner, the king may remain until an exit becomes legal.

- A colour is eliminated immediately if its king is checkmated or captured.

- There is no migration to the 8A-8 area.

- Usual Bishops mechanics apply for multi-player survival unless explicitly overridden elsewhere in these rules.

- The goal is to avoid elimination; play continues until exactly two colors remain.



3) Duel Teleport (trigger)

- Immediately when exactly two players remain, the game teleports to a strict Chess duel on the central 8A-8 board.

- All previous pieces are removed. Each finalist is assigned a standard seat per the mapping above (White/Black).



4) Duel Setup (Standard Chess)

- Each side starts with the full complement of standard chess pieces.

- Placement:

    - Seat mapped to White: back rank RNBQKBNR on rank 1; pawns on rank 2.

    - Seat mapped to Black: back rank rnbqkbnr on rank 8; pawns on rank 7.

- Castling rights: both sides retain full KQ castling rights; en passant follows normal chess rules.

- White moves first in the duel.



5) Duel Play (strict Chess)

- The duel proceeds under standard FIDE chess rules using a chess engine (python-chess) for legality.

- Algebraic notation (SAN) and a-h / 1-8 coordinate overlays may be shown.

- The game ends by checkmate, stalemate, or other standard chess end conditions (as implemented).



6) Force Duel (Chess) control

- The operator control "Force Duel (Chess) Now" can be used at any time to seed the standard 8x8 chess duel with White to move.

- Use it to restore or restart the chess duel regardless of the current four-player state.



7) Migration Status

- Legacy migration mechanics (freezing, teleports, dimming, special promotions) are fully removed for this ruleset and no longer run behind the scenes.



8) Notes and Clarifications

- Seat transforms and per-seat views continue to align the board from each player's perspective in multiplayer; during the duel, White faces up from rank 1 (d1/e1), Black faces down from rank 8 (d8/e8).

- Any prior corner/king sanctuary or special multi-player mechanics are not active during the duel; strict Chess governs.

- The duel setup FEN is: rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1



Appendix

- For tournament directors: this build ships with the survival phase plus the duel rules only; legacy migration has been fully retired for v3.

- For portability (TXT/PDF), this string can be exported together with the program. If PDF is unavailable at runtime, TXT serves as the authoritative rules reference.



This string is for reference only. The game logic does not parse or depend on it.

You can update it anytime; it will be bundled with the program for quick reading.

"""



# ---- Legacy migration stubs (disabled in this ruleset) ----

def both_fully_migrated_incl_kings(board: 'Board') -> bool:

    """[Deprecated] Migration removed. Always return False to disable legacy triggers."""

    return False



def must_enter_filter_for(board, color):

    """[Deprecated] Migration filters removed. Return None (no filtering)."""

    return None



class PColor(Enum):

    WHITE = 0

    GREY  = 1

    BLACK = 2

    PINK  = 3



TURN_ORDER = [PColor.WHITE, PColor.GREY, PColor.BLACK, PColor.PINK]



PLAYER_COLORS = {

    PColor.WHITE: (255, 255, 255),

    PColor.GREY:  (160, 160, 160),

    PColor.BLACK: (0, 0, 0),

    PColor.PINK:  (255, 105, 180),

}

PIECE_VALUES = {'Q':9, 'R':5, 'B':3, 'N':3, 'P':1, 'K':0}



def piece_value(kind: str) -> int:

    """Return a simple material value for a piece kind."""

    return PIECE_VALUES.get(kind, 0)



def square_attacked_by_colors(board: 'Board', r: int, c: int, colors: List[PColor]) -> bool:

    """Return True if any color in 'colors' attacks square (r,c). Wrapper over is_square_attacked."""

    # is_square_attacked exists later in the file; calling it here is fine at runtime.

    return is_square_attacked(board, r, c, colors)



AI_PLAYERS = set()

AI_STRENGTH = "smart"  # "fast" or "smart"

# Extra thinking time for AI during the chess duel (ms)

DUEL_AI_TIME_MS = 10000

# Keep fast AI responsive on Windows by limiting compute per decision and pumping events

FAST_AI_BUDGET_MS = 250



# Duel AI tuning

DUEL_BASE_DEPTH = 3           # minimum search depth in chess duel

DUEL_MAX_DEPTH = 6            # hard ceiling to keep search responsive

DUEL_STRONG_TIME_BONUS_MS = 2000  # additional milliseconds for the stronger side

DUEL_STRONG_DEPTH_BONUS = 1       # extra plies for the stronger side

DUEL_EVAL_STRONG_BIAS = 30        # centipawn bias toward the stronger side

DUEL_CHECK_BONUS = 45

DUEL_MOBILITY_WEIGHT = 4

MATE_SCORE = 100000



# Piece-square tables (white perspective) for duel evaluation (centipawns)

_DUEL_PAWN_TABLE = [

    0,   0,   0,   0,   0,   0,   0,   0,

   50,  50,  50,  50,  50,  50,  50,  50,

   10,  10,  20,  30,  30,  20,  10,  10,

    5,   5,  10,  25,  25,  10,   5,   5,

    0,   0,   0,  20,  20,   0,   0,   0,

    5,  -5, -10,   0,   0, -10,  -5,   5,

    5,  10,  10, -20, -20,  10,  10,   5,

    0,   0,   0,   0,   0,   0,   0,   0,

]

_DUEL_KNIGHT_TABLE = [

  -50, -40, -30, -30, -30, -30, -40, -50,

  -40, -20,   0,   5,   5,   0, -20, -40,

  -30,   5,  10,  15,  15,  10,   5, -30,

  -30,   0,  15,  20,  20,  15,   0, -30,

  -30,   5,  15,  20,  20,  15,   5, -30,

  -30,   0,  10,  15,  15,  10,   0, -30,

  -40, -20,   0,   0,   0,   0, -20, -40,

  -50, -40, -30, -30, -30, -30, -40, -50,

]

_DUEL_BISHOP_TABLE = [

  -20, -10, -10, -10, -10, -10, -10, -20,

  -10,   5,   0,   0,   0,   0,   5, -10,

  -10,  10,  10,  10,  10,  10,  10, -10,

  -10,   0,  10,  10,  10,  10,   0, -10,

  -10,   5,   5,  10,  10,   5,   5, -10,

  -10,   0,   5,  10,  10,   5,   0, -10,

  -10,   0,   0,   0,   0,   0,   0, -10,

  -20, -10, -10, -10, -10, -10, -10, -20,

]

_DUEL_ROOK_TABLE = [

    0,   0,   0,   5,   5,   0,   0,   0,

   -5,   0,   0,   0,   0,   0,   0,  -5,

   -5,   0,   0,   0,   0,   0,   0,  -5,

   -5,   0,   0,   0,   0,   0,   0,  -5,

   -5,   0,   0,   0,   0,   0,   0,  -5,

   -5,   0,   0,   0,   0,   0,   0,  -5,

    5,  10,  10,  10,  10,  10,  10,   5,

    0,   0,   0,   0,   0,   0,   0,   0,

]

_DUEL_QUEEN_TABLE = [

  -20, -10, -10,  -5,  -5, -10, -10, -20,

  -10,   0,   0,   0,   0,   0,   0, -10,

  -10,   0,   5,   5,   5,   5,   0, -10,

   -5,   0,   5,   5,   5,   5,   0,  -5,

    0,   0,   5,   5,   5,   5,   0,  -5,

  -10,   5,   5,   5,   5,   5,   0, -10,

  -10,   0,   5,   0,   0,   0,   0, -10,

  -20, -10, -10,  -5,  -5, -10, -10, -20,

]

_DUEL_KING_TABLE = [

  -30, -40, -40, -50, -50, -40, -40, -30,

  -30, -40, -40, -50, -50, -40, -40, -30,

  -30, -40, -40, -50, -50, -40, -40, -30,

  -30, -40, -40, -50, -50, -40, -40, -30,

  -20, -30, -30, -40, -40, -30, -30, -20,

  -10, -20, -20, -20, -20, -20, -20, -10,

   20,  20,   0,   0,   0,   0,  20,  20,

   20,  30,  10,   0,   0,  10,  30,  20,

]



DUEL_PIECE_VALUES = {

    'P': 100,

    'N': 320,

    'B': 330,

    'R': 500,

    'Q': 900,

    'K': 0,

}



DUEL_PST = {

    'P': _DUEL_PAWN_TABLE,

    'N': _DUEL_KNIGHT_TABLE,

    'B': _DUEL_BISHOP_TABLE,

    'R': _DUEL_ROOK_TABLE,

    'Q': _DUEL_QUEEN_TABLE,

    'K': _DUEL_KING_TABLE,

}



# Console noise off (captures/promotions)

DEBUG = False

def log(msg):

    if DEBUG:

        print(msg)



# ----- Corners as 2x2 rectangles -----

CORNER_RECTS = {

    PColor.GREY:  (0, 0),

    PColor.BLACK: (0, 10),

    PColor.WHITE: (10, 0),

    PColor.PINK:  (10, 10),

}



def king_home_cells(color: PColor):

    r0, c0 = CORNER_RECTS[color]

    return [(r0, c0), (r0, c0+1), (r0+1, c0), (r0+1, c0+1)]



def corner_owner_at(r, c):

    for col, (r0, c0) in CORNER_RECTS.items():

        if r0 <= r <= r0+1 and c0 <= c <= c0+1:

            return col

    return None



def in_chess_area(r: int, c: int) -> bool:

    return CH_MIN <= r <= CH_MAX and CH_MIN <= c <= CH_MAX




def _pieces_of_kind(board: 'Board', color: PColor, kind: str) -> List[Tuple[int, int, 'Piece']]:

    """Return a list of (row, col, piece) tuples for a colour filtered by kind."""

    results: List[Tuple[int, int, 'Piece']] = []

    for rr in range(BOARD_SIZE):

        row = board.grid[rr]

        for cc in range(BOARD_SIZE):

            piece = row[cc]

            if piece and piece.color == color and piece.kind == kind:

                results.append((rr, cc, piece))

    return results



def _is_piece_alive(board: 'Board', piece: 'Piece') -> bool:

    """True if the given piece reference is still present on the board."""

    if piece is None:

        return False

    for rr in range(BOARD_SIZE):

        row = board.grid[rr]

        for cc in range(BOARD_SIZE):

            if row[cc] is piece:

                return True

    return False



def _update_corner_state(board: 'Board', gs_obj: 'GameState', color: PColor) -> None:

    """Recompute corner immunity / evacuation using total queen count once sanctuary is active."""

    if gs_obj is None:

        return

    kp = board.find_king(color)

    in_corner = bool(kp and corner_owner_at(kp[0], kp[1]) == color)

    gs_obj.corner_in_corner[color] = in_corner

    queens = len(_pieces_of_kind(board, color, 'Q'))

    has_three_or_more = queens >= 3

    immunity = in_corner and has_three_or_more

    gs_obj.corner_immune[color] = immunity

    if in_corner and gs_obj.corner_promoted[color] and queens <= 1:

        gs_obj.corner_evict_pending[color] = True

    else:

        gs_obj.corner_evict_pending[color] = False



def _handle_corner_entry(board: 'Board', gs_obj: 'GameState', color: PColor) -> None:

    """Apply guardian promotion the first time a king occupies its home corner."""

    if gs_obj is None:

        return

    if not gs_obj.corner_promoted[color]:

        bishops = _pieces_of_kind(board, color, 'B')

        for _, _, piece in bishops:

            piece.kind = 'Q'

        gs_obj.corner_promoted[color] = True

    _update_corner_state(board, gs_obj, color)




def is_edge_pawn_square(r: int, c: int, col: 'PColor') -> bool:

    """Return True if a pawn of color 'col' on square (r,c) is on an edge of the 8-8 center.

    For WHITE/BLACK, "edge" means the outer files (columns CH_MIN/CH_MAX).

    For GREY/PINK, "edge" means the outer ranks (rows CH_MIN/CH_MAX).

    """

    try:

        if col in (PColor.WHITE, PColor.BLACK):

            return c in (CH_MIN, CH_MAX)

        else:

            return r in (CH_MIN, CH_MAX)

    except Exception:

        return False



# ====== VIEW TRANSFORMS (rotate so chosen seat is at bottom) ======

def _seat_for_view():

    v = str(UI_STATE.get('view_seat', 'AUTO')).upper()

    if v == 'AUTO':

        # active color at bottom

        try:

            act = globals().get('forced_turn') or TURN_ORDER[globals().get('turn_i', 0)]

            return act

        except Exception:

            return None

    try:

        return PColor[v]

    except Exception:

        return None



def _transform_rc_for_view(r: int, c: int, inverse=False) -> Tuple[int,int]:

    seat = _seat_for_view()

    if seat is None:

        return (r, c)

    # Define rotations by seat relative to canonical orientation (WHITE bottom)

    # WHITE: no-op; GREY: rotate 90 CW; BLACK: 180; PINK: 90 CCW

    def rot90(rr, cc):

        return (cc, BOARD_SIZE-1-rr)

    def rot180(rr, cc):

        return (BOARD_SIZE-1-rr, BOARD_SIZE-1-cc)

    def rot270(rr, cc):

        return (BOARD_SIZE-1-cc, rr)

    def apply(rr, cc):

        if seat == PColor.WHITE:

            return (rr, cc)

        if seat == PColor.GREY:

            # GREY (left) to bottom: rotate 90 CCW

            return rot270(rr, cc)

        if seat == PColor.BLACK:

            return rot180(rr, cc)

        if seat == PColor.PINK:

            # PINK (right) to bottom: rotate 90 CW

            return rot90(rr, cc)

        return (rr, cc)

    def apply_inv(rr, cc):

        if seat == PColor.WHITE:

            return (rr, cc)

        if seat == PColor.GREY:

            # inverse of rot270 is rot90

            return rot90(rr, cc)

        if seat == PColor.BLACK:

            return rot180(rr, cc)

        if seat == PColor.PINK:

            # inverse of rot90 is rot270

            return rot270(rr, cc)

        return (rr, cc)

    return apply_inv(r,c) if inverse else apply(r,c)



def rc_to_label(r: int, c: int) -> str:

    """Return an algebraic-like label for 14x14 board.

    Files: a..n (0..13), Ranks: 14..1 (top to bottom).

    Falls back to numeric tuple if out of range.

    """

    files = "abcdefghijklmn"  # 14 columns

    try:

        if 0 <= c < 14 and 0 <= r < 14:

            file = files[c]

            rank = 14 - r

            return f"{file}{rank}"

    except Exception:

        pass

    return f"({r},{c})"



def duel_to_chess_label(r: int, c: int) -> str:

    """Return standard chess coordinate when in duel mode; fallback to rc label otherwise."""

    gs_local = globals().get('gs', None)

    if gs_local and getattr(gs_local, 'chess_lock', False) and _CHESS_OK:

        try:

            import chess

            sq = _rc_to_sq(r, c)

            if sq is not None:

                return chess.square_name(sq)

        except Exception:

            pass

    return rc_to_label(r, c)



def dist_to_chess(r: int, c: int) -> int:

    """Chebyshev/Manhattan hybrid to nearest 8-8 boundary; 0 if already inside."""

    if in_chess_area(r, c):

        return 0

    dr = 0

    if r < CH_MIN: dr = CH_MIN - r

    elif r > CH_MAX: dr = r - CH_MAX

    dc = 0

    if c < CH_MIN: dc = CH_MIN - c

    elif c > CH_MAX: dc = c - CH_MAX

    return dr + dc



UNICODE = {

    'K': {PColor.WHITE:'\u2654', PColor.BLACK:'\u265A', PColor.GREY:'\u2654', PColor.PINK:'\u2654'},

    'Q': {PColor.WHITE:'\u2655', PColor.BLACK:'\u265B', PColor.GREY:'\u2655', PColor.PINK:'\u2655'},

    'R': {PColor.WHITE:'\u2656', PColor.BLACK:'\u265C', PColor.GREY:'\u2656', PColor.PINK:'\u2656'},

    'B': {PColor.WHITE:'\u2657', PColor.BLACK:'\u265D', PColor.GREY:'\u2657', PColor.PINK:'\u2657'},

    'N': {PColor.WHITE:'\u2658', PColor.BLACK:'\u265E', PColor.GREY:'\u2658', PColor.PINK:'\u2658'},

    'P': {PColor.WHITE:'\u2659', PColor.BLACK:'\u265F', PColor.GREY:'\u2659', PColor.PINK:'\u2659'},

}



# ====== START MENU ======

def choose_ai_players():

    # Default during debugging: no automated AI players so human clicks work by default

    return set()



# ====== Settings (persisted across runs) ======

def load_user_settings():

    try:

        if os.path.isfile(SETTINGS_PATH):

            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:

                data = json.load(f)

                if isinstance(data, dict):

                    return data

    except Exception:

        pass

    return {"hold_at_start": False}



def save_user_settings(d: Dict):

    try:

        tmp_path = SETTINGS_PATH + ".tmp"

        with open(tmp_path, 'w', encoding='utf-8') as f:

            json.dump(d, f)

        try:

            os.replace(tmp_path, SETTINGS_PATH)

        except Exception:

            os.rename(tmp_path, SETTINGS_PATH)

    except Exception:

        pass



# ====== MODEL ======

class Piece:

    def __init__(self, kind: str, color: PColor):

        self.kind = kind  # 'K','Q','R','B','N','P'

        self.color = color

        self.has_moved = False

        self.tint_override: Optional[Tuple[int, int, int]] = None



class Board:

    def __init__(self):

        self.grid = [[None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]

        self.king_positions = {PColor.WHITE: None, PColor.GREY: None, PColor.BLACK: None, PColor.PINK: None}

        self._setup()



    def _setup(self):

        back_std = ['R','N','B','Q','K','B','N','R']



        # WHITE (bottom)

        for i, k in enumerate(back_std):

            p = Piece(k, PColor.WHITE)

            self.grid[11][i+2] = p

            if k == 'K':

                log(f"[DEBUG] Placed WHITE king at (11,{i+2}) with color value {p.color} and kind {p.kind}")

        for i in range(8):

            self.grid[10][i+2] = Piece('P', PColor.WHITE)



        # BLACK (top)

        back_black = ['R','N','B','Q','K','B','N','R']

        for i, k in enumerate(back_black):

            p = Piece(k, PColor.BLACK)

            self.grid[0][i+2] = p

            if k == 'K':

                log(f"[DEBUG] Placed BLACK king at (0,{i+2}) with color value {p.color} and kind {p.kind}")

        for i in range(8):

            self.grid[1][i+2] = Piece('P', PColor.BLACK)



        # GREY (left)

        for i, k in enumerate(back_std):

            p = Piece(k, PColor.GREY)

            self.grid[i+2][0] = p

            if k == 'K':

                log(f"[DEBUG] Placed GREY king at ({i+2},0) with color value {p.color} and kind {p.kind}")

        for i in range(8):

            self.grid[i+2][1] = Piece('P', PColor.GREY)



        # PINK (right)

        back_pink = ['R','N','B','Q','K','B','N','R']

        for i, k in enumerate(back_pink):

            p = Piece(k, PColor.PINK)

            self.grid[i+2][11] = p

            if k == 'K':

                log(f"[DEBUG] Placed PINK king at ({i+2},11) with color value {p.color} and kind {p.kind}")

        for i in range(8):

            self.grid[i+2][10] = Piece('P', PColor.PINK)

        # initialize cached king positions

        for col in TURN_ORDER:

            kp = self.find_king(col)

            self.king_positions[col] = kp



    def in_bounds(self, r, c):

        return 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE



    def get(self, r, c):

        return self.grid[r][c] if self.in_bounds(r,c) else None



    def set(self, r, c, p):

        if self.in_bounds(r,c):

            self.grid[r][c] = p

            # maintain king cache

            if p and p.kind == 'K':

                self.king_positions[p.color] = (r,c)

            else:

                # if we overwrote a king position, clear cache for that color and let find_king refresh lazily

                for col, pos in list(self.king_positions.items()):

                    if pos == (r,c) and (p is None or p.kind != 'K'):

                        self.king_positions[col] = None



    def find_king(self, color: PColor):

        # return cached position if present

        pos = self.king_positions.get(color)

        if pos is not None:

            # verify it's still valid

            p = self.get(pos[0], pos[1])

            if p and p.color == color and p.kind == 'K':

                return pos

        # fallback: scan and update cache

        for r in range(BOARD_SIZE):

            for c in range(BOARD_SIZE):

                p = self.get(r,c)

                if p and p.color == color and p.kind == 'K':

                    self.king_positions[color] = (r,c)

                    return (r,c)

        self.king_positions[color] = None

        return None



    def alive_colors(self) -> List[PColor]:

        return [col for col in TURN_ORDER if self.find_king(col) is not None]



# --- Chess-only helpers (pure 8x8 White vs Black) ---

def init_chess_only_board() -> 'Board':

    """Create a board configured for pure 8-8 chess between WHITE and BLACK in the center.



    - Clears all cells

    - Places standard chess back ranks and pawns inside [CH_MIN..CH_MAX] for files and ranks

    - Updates global gs flags (if present) to reflect locked two-player chess mode

    """

    b = Board()

    # Clear everything

    for rr in range(BOARD_SIZE):

        for cc in range(BOARD_SIZE):

            b.set(rr, cc, None)

    # Standard chess back rank order

    back = ['R','N','B','Q','K','B','N','R']

    # Place WHITE at bottom of central 8-8 (rank CH_MAX)

    for i, k in enumerate(back):

        b.set(CH_MAX, CH_MIN + i, Piece(k, PColor.WHITE))

    for i in range(8):

        b.set(CH_MAX - 1, CH_MIN + i, Piece('P', PColor.WHITE))

    # Place BLACK at top of central 8-8 (rank CH_MIN)

    for i, k in enumerate(back):

        b.set(CH_MIN, CH_MIN + i, Piece(k, PColor.BLACK))

    for i in range(8):

        b.set(CH_MIN + 1, CH_MIN + i, Piece('P', PColor.BLACK))



    # Reflect two-player chess-only flags into gs if available

    try:

        gs_obj = globals().get('gs', None)

        if gs_obj is not None:

            gs_obj.two_stage_active = True

            gs_obj.final_a = PColor.WHITE

            gs_obj.final_b = PColor.BLACK

            # Mark both as having entered and reductions applied; lock to 8-8

            if hasattr(gs_obj, 'entered') and isinstance(gs_obj.entered, dict):

                gs_obj.entered[PColor.WHITE] = True

                gs_obj.entered[PColor.BLACK] = True

            if hasattr(gs_obj, 'reduced_applied') and isinstance(gs_obj.reduced_applied, dict):

                gs_obj.reduced_applied[PColor.WHITE] = True

                gs_obj.reduced_applied[PColor.BLACK] = True

            gs_obj.chess_lock = True

            gs_obj.grace_active = False

            gs_obj.grace_turns_remaining = 0

            # Ensure pawn directions are standard

            try:

                gs_obj.pawn_dir[PColor.WHITE] = -1

                gs_obj.pawn_dir[PColor.BLACK] = 1

            except Exception:

                pass

    except Exception:

        pass

    return b



# ====== MOVE GEN (pseudo) ======

def add_slide_moves(board: Board, r, c, piece, dirs, out):

    for dr, dc in dirs:

        nr, nc = r + dr, c + dc

        while board.in_bounds(nr, nc):

            if corner_owner_at(nr, nc) is not None:

                break

            tgt = board.get(nr, nc)

            if tgt:

                if tgt.color != piece.color and tgt.kind != 'K':

                    out.append((nr, nc))

                break

            out.append((nr, nc))

            nr += dr

            nc += dc

def gen_moves(board, r, c):

    moves = []

    p = board.get(r, c)

    if not p:

        return moves

    kind = p.kind

    color = p.color

    if kind == 'N':

        for dr, dc in [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]:

            nr, nc = r+dr, c+dc

            if board.in_bounds(nr,nc):

                if corner_owner_at(nr, nc) is not None:

                    continue

                tgt = board.get(nr,nc)

                if not tgt or (tgt.color != color and tgt.kind != 'K'):

                    moves.append((nr,nc))

    elif kind == 'K':

        for dr in (-1,0,1):

            for dc in (-1,0,1):

                if dr == 0 and dc == 0: continue

                nr, nc = r+dr, c+dc

                if not board.in_bounds(nr,nc): continue

                owner = corner_owner_at(nr, nc)

                if owner is not None and owner != color:

                    continue

                tgt = board.get(nr,nc)

                if not tgt or (tgt.color != color and tgt.kind != 'K'):

                    moves.append((nr,nc))

        # Short-game castling (ON by default): allow 2-step king move along home rank toward a rook

        # Only when not in chess-lock; both king and rook must be unmoved; squares between must be empty;

        # King may not be in check, pass through check, or land in check by any colour.

        try:

            gs_obj = globals().get('gs', None)

            if not (gs_obj and getattr(gs_obj, 'chess_lock', False)):

                if not p.has_moved:

                    # Determine home axis and directions for side/corner per colour

                    # Directions are unit vectors (dr,dc) along the home rank

                    if color == PColor.WHITE:

                        axis = 'row'; idx = 11; side_dir = (0, 1); corner_dir = (0, -1)

                    elif color == PColor.BLACK:

                        axis = 'row'; idx = 0;  side_dir = (0, -1); corner_dir = (0, 1)

                    elif color == PColor.GREY:

                        axis = 'col'; idx = 0;  side_dir = (1, 0);  corner_dir = (-1, 0)

                    else:  # PColor.PINK

                        axis = 'col'; idx = 11; side_dir = (-1, 0); corner_dir = (1, 0)

                    # King must be on its home axis

                    on_home = (axis == 'row' and r == idx) or (axis == 'col' and c == idx)

                    if on_home:

                        def _castle_dir(drc):

                            dr, dc = drc

                            # Target squares for king movement

                            k1r, k1c = r + dr, c + dc

                            k2r, k2c = r + 2*dr, c + 2*dc

                            # Both intermediate squares must be in bounds and empty

                            if not (board.in_bounds(k1r, k1c) and board.in_bounds(k2r, k2c)):

                                return None

                            if board.get(k1r, k1c) or board.get(k2r, k2c):

                                return None

                            # Find the first piece in this direction to verify it's our rook (unmoved)

                            srch_r, srch_c = r + 3*dr, c + 3*dc

                            rook_sq = None

                            while board.in_bounds(srch_r, srch_c):

                                q = board.get(srch_r, srch_c)

                                if q is not None:

                                    rook_sq = (srch_r, srch_c, q)

                                    break

                                srch_r += dr

                                srch_c += dc

                            if not rook_sq:

                                return None

                            rr, rc, rq = rook_sq

                            if not (rq.color == color and rq.kind == 'R' and not rq.has_moved):

                                return None

                            # Can't castle out of, through, or into check (attacked by any colour)

                            # Also disallow entering opponent's protected corner squares

                            # Build attackers list as any other colour with a living king

                            attackers = [col for col in TURN_ORDER if col != color and board.find_king(col) is not None]

                            if king_in_check(board, color):

                                return None

                            # Through square

                            if is_square_attacked(board, k1r, k1c, attackers):

                                return None

                            # Destination square

                            if is_square_attacked(board, k2r, k2c, attackers):

                                return None

                            owner1 = corner_owner_at(k1r, k1c)

                            owner2 = corner_owner_at(k2r, k2c)

                            if (owner1 is not None and owner1 != color) or (owner2 is not None and owner2 != color):

                                return None

                            return (k2r, k2c)

                        for drc in (side_dir, corner_dir):

                            dst = _castle_dir(drc)

                            if dst is not None:

                                moves.append(dst)

        except Exception:

            pass

        try:

            gs_obj = globals().get('gs')

            if gs_obj and gs_obj.corner_evict_pending.get(color, False):

                if corner_owner_at(r, c) == color:

                    exit_moves = [(nr, nc) for (nr, nc) in moves if corner_owner_at(nr, nc) != color]

                    if exit_moves:

                        moves = exit_moves

        except Exception:

            pass

    elif kind == 'R':

        add_slide_moves(board, r, c, p, [(1,0),(-1,0),(0,1),(0,-1)], moves)

    elif kind == 'B':

        add_slide_moves(board, r, c, p, [(1,1),(1,-1),(-1,1),(-1,-1)], moves)

    elif kind == 'Q':

        add_slide_moves(board, r, c, p, [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)], moves)

    elif kind == 'P':

        # Determine pawn forward direction from gs.pawn_dir if present, otherwise use defaults

        gs_obj = globals().get('gs')

        default_dir = {PColor.WHITE: -1, PColor.BLACK: 1, PColor.GREY: 1, PColor.PINK: -1}

        pd = default_dir.get(color, -1)

        if gs_obj is not None:

            pd = gs_obj.pawn_dir.get(color, pd)

        # Map pawn direction to forward vector and capture vectors per color

        if color in (PColor.WHITE, PColor.BLACK):

            fwd = (pd, 0)

            if pd == -1:

                caps = [(-1,-1), (-1,1)]

            else:

                caps = [(1,-1), (1,1)]

        else:

            # GREY and PINK move along files (columns). pd indicates column direction (+1 rightwards, -1 leftwards)

            fwd = (0, pd)

            if pd == 1:

                caps = [(-1,1), (1,1)]

            else:

                caps = [(-1,-1), (1,-1)]

        nr, nc = r + fwd[0], c + fwd[1]

        if color in (PColor.WHITE, PColor.BLACK):

            if board.in_bounds(nr,nc) and corner_owner_at(nr, nc) is None and not board.get(nr,nc):

                moves.append((nr,nc))

                nr2, nc2 = nr + fwd[0], nc + fwd[1]

                if (not p.has_moved and board.in_bounds(nr2,nc2)

                    and corner_owner_at(nr2, nc2) is None and not board.get(nr2,nc2)):

                    moves.append((nr2,nc2))

        else:

            if board.in_bounds(nr,nc) and corner_owner_at(nr, nc) is None and not board.get(nr,nc):

                moves.append((nr,nc))

                nr2, nc2 = nr + fwd[0], nc + fwd[1]

                if (not p.has_moved and board.in_bounds(nr2,nc2)

                    and corner_owner_at(nr2, nc2) is None and not board.get(nr2,nc2)):

                    moves.append((nr2,nc2))

        for dr, dc in caps:

            ar, ac = r + dr, c + dc

            if board.in_bounds(ar,ac) and corner_owner_at(ar, ac) is None:

                tgt = board.get(ar,ac)

                if tgt and tgt.color != color and tgt.kind != 'K':

                    # Edge-pawn capture restriction (first round only):

                    # If BOTH attacker and target are edge pawns (w.r.t. their OWN color orientation),

                    # disallow the capture during the opening round of moves (first 4 plies).

                    gs_obj = globals().get('gs')

                    is_first_round = (gs_obj is not None and getattr(gs_obj, 'half_moves', 0) < 4)

                    if is_first_round and tgt.kind == 'P':

                        attacker_edge = is_edge_pawn_square(r, c, color)

                        target_edge   = is_edge_pawn_square(ar, ac, tgt.color)

                        if attacker_edge and target_edge:

                            # disallow this capture on first round

                            pass

                        else:

                            moves.append((ar,ac))

                    else:

                        moves.append((ar,ac))

    return moves

    if cap and not simulate:

        try:

            log(f"[CAPTURE] {mover.color.name} {mover.kind} x {cap.color.name} {cap.kind} at ({er},{ec})")

        except Exception:

            pass

    # If this was a real move (not simulate), update GameState half-move counter and handle corner rules

    if not simulate:

        gs_obj = globals().get('gs')

        if gs_obj is not None:

            gs_obj.half_moves += 1

        # record recent move for repetition/ping-pong detection

        try:

            if gs_obj is not None:

                gs_obj.recent_moves.append((mover.color if mover else None, sr, sc, er, ec))

        except Exception:

            pass

        # Update position repetition counts and detect threefold repetition

        try:

            if gs_obj is not None:

                key = gs_obj._position_key(board)

                prev = gs_obj.pos_counts.get(key, 0)

                gs_obj.pos_counts[key] = prev + 1

                if gs_obj.pos_counts[key] >= 3:

                    # Threefold repetition reached -> set game over state as draw

                    gs_obj.freeze_advance = True

                    gs_obj.post_move_delay_until = 0

                    gs_obj.elim_flash_color = None

                    # Use a sentinel value to indicate draw (None winner)

                    gs_obj._draw_by_repetition = True

                    log(f"[DRAW] threefold repetition detected (key={key})")

        except Exception:

            pass

        # After a real move, check whether we should activate two-stage migration

        try:

            gs_obj = globals().get('gs')

            if gs_obj is not None:

                activate_two_stage_if_needed(board, gs_obj)

        except Exception:

            # Protect against activation errors during headless tests

            pass

        if gs_obj is not None:

            if mover_is_king and mover and end_corner_owner == mover.color and (start_corner_owner != mover.color):

                _handle_corner_entry(board, gs_obj, mover.color)

            for col in TURN_ORDER:

                _update_corner_state(board, gs_obj, col)

    # Final verification debug

    try:

        if not simulate:

            final_dst = board.get(er, ec)

            final_src = board.get(sr, sc)

            print(f"[DO_MOVE] final verification src={('present' if final_src else 'empty')} dst={(final_dst.kind if final_dst else None, final_dst.color.name if final_dst else None)}")

    except Exception:

        pass

    return cap, prev_has, prev_kind, effects



# ====== TRUE CHECK & LEGAL FILTER ======

def is_square_attacked(board: Board, r: int, c: int, attackers: List[PColor]) -> bool:

    # Pawn attacks

    for col in attackers:

        # Determine pawn capture deltas according to pawn_dir settings

        gs_obj = globals().get('gs')

        default_dir = {PColor.WHITE: -1, PColor.BLACK: 1, PColor.GREY: 1, PColor.PINK: -1}

        pd = default_dir.get(col, -1)

        if gs_obj is not None:

            pd = gs_obj.pawn_dir.get(col, pd)

        if col in (PColor.WHITE, PColor.BLACK):

            if pd == -1:

                deltas = [(-1,-1), (-1,1)]

            else:

                deltas = [(1,-1), (1,1)]

            for dr,dc in deltas:

                rr, cc = r+dr, c+dc

                if board.in_bounds(rr,cc):

                    p = board.get(rr,cc)

                    if p and p.color==col and p.kind=='P' and corner_owner_at(r,c) is None and abs(cc-c)==1:

                        return True

        else:

            # GREY / PINK: column-moving pawns

            if pd == 1:

                deltas = [(-1,1),(1,1)]

            else:

                deltas = [(-1,-1),(1,-1)]

            for dr,dc in deltas:

                rr, cc = r+dr, c+dc

                if board.in_bounds(rr,cc):

                    p = board.get(rr,cc)

                    if p and p.color==col and p.kind=='P' and corner_owner_at(r,c) is None and abs(rr-r)==1:

                        return True



    # Knights

    for dr,dc in [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]:

        rr, cc = r+dr, c+dc

        if board.in_bounds(rr,cc):

            if corner_owner_at(r,c) is not None:

                continue

            p = board.get(rr,cc)

            if p and p.color in attackers and p.kind=='N':

                return True



    # Sliding (rook/queen)

    for dr,dc in [(1,0),(-1,0),(0,1),(0,-1)]:

        rr, cc = r+dr, c+dc

        while board.in_bounds(rr,cc):

            if corner_owner_at(rr,cc) is not None:

                break

            p = board.get(rr,cc)

            if p:

                if p.color in attackers and (p.kind=='R' or p.kind=='Q'):

                    return True

                break

            rr += dr; cc += dc



    # Sliding (bishop/queen)

    for dr,dc in [(1,1),(1,-1),(-1,1),(-1,-1)]:

        rr, cc = r+dr, c+dc

        while board.in_bounds(rr,cc):

            if corner_owner_at(rr,cc) is not None:

                break

            p = board.get(rr,cc)

            if p:

                if p.color in attackers and (p.kind=='B' or p.kind=='Q'):

                    return True

                break

            rr += dr; cc += dc



    # Kings (adjacent)

    for dr in (-1,0,1):

        for dc in (-1,0,1):

            if dr==0 and dc==0: continue

            rr, cc = r+dr, c+dc

            if not board.in_bounds(rr,cc): continue

            if corner_owner_at(r,c) is not None:

                continue

            p = board.get(rr,cc)

            if p and p.color in attackers and p.kind=='K':

                return True



    return False





def king_in_check(board: Board, color: PColor) -> bool:

    kp = board.find_king(color)

    if not kp:

        return False

    gs_obj = globals().get('gs')

    if gs_obj and gs_obj.corner_immune.get(color, False):

        return False

    r, c = kp

    # Fast attacker list using cached king positions

    attackers = []

    for col in TURN_ORDER:

        if col == color: continue

        if board.king_positions.get(col) is not None:

            attackers.append(col)

        else:

            # fallback: check existence

            if board.find_king(col) is not None:

                attackers.append(col)

    return is_square_attacked(board, r, c, attackers)

    loc = board.find_king(color)

    if not loc:

        return False

    r,c = loc

    attackers = [col for col in TURN_ORDER if col != color and board.find_king(col) is not None]

    return is_square_attacked(board, r, c, attackers)



# ====== MOVE APPLY/UNDO (safe wrappers for simulation) ======

def board_do_move(board: Board, sr, sc, er, ec, simulate=False):

    mover = board.get(sr, sc)

    cap   = board.get(er, ec)

    prev_has = mover.has_moved if mover else False

    prev_kind = mover.kind if mover else None

    mover_is_king = (prev_kind == 'K')

    start_corner_owner = corner_owner_at(sr, sc) if mover_is_king else None

    end_corner_owner = corner_owner_at(er, ec) if mover_is_king else None

    effects = {}



    gs_local = globals().get('gs', None)

    chess_lock_active = bool(gs_local and getattr(gs_local, 'chess_lock', False))

    if chess_lock_active and (not _in8(sr, sc) or not _in8(er, ec)):

        if simulate:

            return None, False, None, {}

        raise ValueError(f"Illegal duel move outside 8x8: {(sr, sc)} -> {(er, ec)}")



    # Remove mover from source and place at destination (even during simulation)

    board.set(sr, sc, None)

    if mover:

        board.set(er, ec, mover)

    if mover:

        mover.has_moved = True

        # promotions (auto-queen)

        # New rule: Promote upon reaching the inside edge of the 8-8 chessboard (not the outer 10th rank).

        # Inside edges: rows CH_MIN..CH_MAX. Far-edge mapping per color (relative to starting side):

        #   WHITE  row CH_MIN (far side up); BLACK  row CH_MAX (far side down);

        #   GREY   col CH_MAX (far side right); PINK   col CH_MIN (far side left).

        if mover.kind == 'P':

            promote = False

            try:

                if ((mover.color == PColor.WHITE and er == CH_MIN) or
                    (mover.color == PColor.BLACK and er == CH_MAX) or
                    (mover.color == PColor.GREY  and ec == CH_MAX) or
                    (mover.color == PColor.PINK  and ec == CH_MIN)):

                    promote = True

            except Exception:

                promote = False

            if promote:

                mover.kind = 'Q'

                effects['promoted'] = True

                if mover.color == PColor.WHITE and chess_lock_active:

                    try:

                        mover.tint_override = None

                    except Exception:

                        mover.tint_override = None

                if not simulate: log(f"[PROMOTION] {mover.color.name} PQ at ({er},{ec})")

    # Detect short-game castling (non-engine path): king moves exactly two squares along its home axis

    try:

        if mover and mover.kind == 'K' and not simulate:

            horiz = (sr == er and abs(ec - sc) == 2)

            vert  = (sc == ec and abs(er - sr) == 2)

            if horiz or vert:

                # Determine direction unit (dr,dc)

                dr = 0 if horiz else (1 if er > sr else -1)

                dc = 0 if vert  else (1 if ec > sc else -1)

                # Find the rook on that side: the first piece further along direction must be our rook

                rr, rc = (er + dr, ec + dc)  # one beyond destination

                # Alternatively start search from source + 3*dir to skip k1,k2 squares

                rr, rc = sr + 3*dr, sc + 3*dc

                rook_pos = None

                while board.in_bounds(rr, rc):

                    q = board.get(rr, rc)

                    if q is not None:

                        rook_pos = (rr, rc, q)

                        break

                    rr += dr

                    rc += dc

                if rook_pos:

                    r_sr, r_sc, rq = rook_pos

                    if rq.kind == 'R' and rq.color == mover.color:

                        # Rook lands on the square the king passed over (one step from source in direction)

                        r_er, r_ec = sr + dr, sc + dc

                        board.set(r_sr, r_sc, None)

                        board.set(r_er, r_ec, rq)

                        rq.has_moved = True

    except Exception:

        pass

    if cap and not simulate:

        log(f"[CAPTURE] {mover.color.name} {mover.kind} x {cap.color.name} {cap.kind} at ({er},{ec})")

    # If this was a real move (not simulate), update GameState half-move counter and handle corner rules

    if not simulate:

        gs_obj = globals().get('gs')

        if gs_obj is not None:

            gs_obj.half_moves += 1

        # record recent move for repetition/ping-pong detection

        try:

            if gs_obj is not None:

                gs_obj.recent_moves.append((mover.color if mover else None, sr, sc, er, ec))

        except Exception:

            pass

        # Update position repetition counts and detect threefold repetition

        try:

            if gs_obj is not None:

                key = gs_obj._position_key(board)

                prev = gs_obj.pos_counts.get(key, 0)

                gs_obj.pos_counts[key] = prev + 1

                if gs_obj.pos_counts[key] >= 3:

                    # Threefold repetition reached -> set game over state as draw

                    gs_obj.freeze_advance = True

                    gs_obj.post_move_delay_until = 0

                    gs_obj.elim_flash_color = None

                    # Use a sentinel value to indicate draw (None winner)

                    gs_obj._draw_by_repetition = True

                    log(f"[DRAW] threefold repetition detected (key={key})")

        except Exception:

            pass

        # After a real move, check whether we should activate two-stage migration

        try:

            gs_obj = globals().get('gs')

            if gs_obj is not None:

                activate_two_stage_if_needed(board, gs_obj)

        except Exception:

            # Protect against activation errors during headless tests

            pass


    return cap, prev_has, prev_kind, effects



def board_undo_move(board: Board, sr, sc, er, ec, captured, prev_has_moved, prev_kind, effects=None):

    mover = board.get(er, ec)

    # Restore mover back to source and captured piece back to destination

    board.set(sr, sc, mover)

    board.set(er, ec, captured)

    if mover:

        mover.has_moved = prev_has_moved

        if effects and effects.get('promoted'):

            mover.kind = 'P'

        elif prev_kind:

            mover.kind = prev_kind



# ====== LEGAL MOVE FILTER (uses true check) ======



def legal_moves_for_piece(board: Board, r: int, c: int, active_color: Optional[PColor]=None) -> list:

    """Return all legal moves for the piece at (r, c), filtering out moves that leave king in check.

    `active_color` is optional and accepted for compatibility with wrappers that pass the current active player."""

    p = board.get(r, c)

    if not p:

        return []

    color = p.color

    pseudo = gen_moves(board, r, c)

    out = []

    for (er, ec) in pseudo:

        cap, prev_has, prev_kind, eff = board_do_move(board, r, c, er, ec, simulate=True)

        illegal = king_in_check(board, color)

        board_undo_move(board, r, c, er, ec, cap, prev_has, prev_kind, eff)

        if not illegal:

            out.append((r, c, er, ec))

    return out



def all_legal_moves_for_color(board: Board, color: PColor):

    """Collect all legal moves for a color, normalizing to 4-tuples (sr,sc,er,ec).

    Some wrappers may return (er,ec) pairs; in that case, we expand using the source (r,c).

    """

    moves = []

    for r in range(BOARD_SIZE):

        for c in range(BOARD_SIZE):

            p = board.get(r, c)

            if p is not None and p.color == color:

                plist = legal_moves_for_piece(board, r, c, color)

                if not plist:

                    continue

                # Normalize shape

                first = plist[0]

                if isinstance(first, (list, tuple)) and len(first) == 2:

                    moves.extend([(r, c, er, ec) for (er, ec) in plist])

                else:

                    moves.extend(plist)

    return moves



def net_hanging_penalty(board: Board, mover_after: Piece, to_r: int, to_c: int) -> int:

    """Crude en prise check: penalize landing on an attacked square. Lightweight for speed."""

    if mover_after is None:

        return 0

    me = mover_after.color

    others = [c for c in TURN_ORDER if c != me and board.find_king(c) is not None]

    if not square_attacked_by_colors(board, to_r, to_c, others):

        return 0

    # Basic penalty scaled by piece value, heavier for queens and kings

    base = piece_value(mover_after.kind)

    if mover_after.kind == 'Q':

        base *= 2

    if mover_after.kind == 'K':

        base *= 3

    return - (6 + base)





class _DuelSearchTimeout(Exception):

    """Raised internally when the duel search exceeds its allotted time."""

    pass





def _mirror_square_index(sq: int) -> int:

    """Mirror a 0..63 square index vertically (white <-> black perspective)."""

    return sq ^ 56





def _duel_evaluate_board(cb, root_color, eval_bias):

    """Static evaluation for the duel (python-chess) board, in centipawns relative to root_color."""

    try:

        import chess as _chess

    except Exception:

        return 0



    score = 0

    piece_map = cb.piece_map()

    for sq, piece in piece_map.items():

        symbol = piece.symbol().upper()

        base = DUEL_PIECE_VALUES.get(symbol, 0)

        table = DUEL_PST.get(symbol)

        idx = sq if piece.color == _chess.WHITE else _mirror_square_index(sq)

        if table:

            base += table[idx]

        if piece.color == _chess.WHITE:

            score += base

        else:

            score -= base



    # Mobility/tempo

    mobility = DUEL_MOBILITY_WEIGHT * len(list(cb.legal_moves))

    score += mobility if cb.turn == _chess.WHITE else -mobility



    # Castling rights encourage safety

    if cb.has_kingside_castling_rights(_chess.WHITE) or cb.has_queenside_castling_rights(_chess.WHITE):

        score += 25

    if cb.has_kingside_castling_rights(_chess.BLACK) or cb.has_queenside_castling_rights(_chess.BLACK):

        score -= 25



    # Checks

    if cb.is_check():

        score += -DUEL_CHECK_BONUS if cb.turn == _chess.WHITE else DUEL_CHECK_BONUS



    # Convert to root perspective (white positive)

    if root_color == _chess.WHITE:

        result = score

    else:

        result = -score



    return result + eval_bias





def _duel_order_moves(cb, moves, pv_move):

    """Order moves using captures/checks/promotions and previous PV move."""

    scored = []

    for mv in moves:

        score = 0

        if pv_move is not None and mv == pv_move:

            score += 10000



        if cb.is_capture(mv):

            captured = cb.piece_at(mv.to_square)

            if captured is None and cb.is_en_passant(mv):

                captured_value = DUEL_PIECE_VALUES.get('P', 100)

            else:

                captured_value = DUEL_PIECE_VALUES.get(captured.symbol().upper(), 0) if captured else 0

            attacker = DUEL_PIECE_VALUES.get(cb.piece_at(mv.from_square).symbol().upper(), 0)

            score += 500 + captured_value - attacker



        if mv.promotion:

            promo_symbol = {1: 'P', 2: 'N', 3: 'B', 4: 'R', 5: 'Q', 6: 'K'}.get(mv.promotion, 'Q')

            score += 800 + DUEL_PIECE_VALUES.get(promo_symbol, 0)



        if cb.gives_check(mv):

            score += 80



        if cb.is_castling(mv):

            score += 60



        scored.append((score, mv))



    scored.sort(key=lambda item: item[0], reverse=True)

    return [mv for _, mv in scored]





def choose_duel_move(board: Board, color: PColor, base_time_ms: int):

    """Stronger duel search using python-chess copy of the board."""

    if not _CHESS_OK:

        return None

    gs_obj = globals().get('gs')

    if not gs_obj or not getattr(gs_obj, 'chess_lock', False):

        return None

    cb = getattr(gs_obj, 'chess_board', None)

    if cb is None:

        return None



    import chess  # safe: _CHESS_OK ensured import



    cb = cb.copy(stack=False)

    root_color = chess.WHITE if color == PColor.WHITE else chess.BLACK

    depth_bonus = getattr(gs_obj, 'duel_depth_bonus', {}).get(color, 0)

    time_bonus = getattr(gs_obj, 'duel_time_bonus', {}).get(color, 0)

    eval_bias_map = getattr(gs_obj, 'duel_eval_bias', {})

    eval_bias = eval_bias_map.get(color, 0)



    max_depth = min(DUEL_MAX_DEPTH, DUEL_BASE_DEPTH + max(0, depth_bonus))

    time_budget_ms = max(400, base_time_ms + max(0, time_bonus))

    deadline = time.perf_counter() + (time_budget_ms / 1000.0)



    # Immediate outcome checks

    if cb.is_game_over():

        moves = list(cb.legal_moves)

        if not moves:

            return None

        mv = random.choice(moves)

        sr, sc = _sq_to_rc(mv.from_square)

        er, ec = _sq_to_rc(mv.to_square)

        return (sr, sc, er, ec)



    best_move = None

    best_value = -MATE_SCORE

    pv_move = None



    def negamax(depth, alpha, beta, pv_hint):

        if time.perf_counter() >= deadline:

            raise _DuelSearchTimeout()



        if cb.is_checkmate():

            return -MATE_SCORE + depth, None

        if cb.is_stalemate() or cb.is_insufficient_material() or cb.can_claim_fifty_moves() or cb.can_claim_threefold_repetition():

            return 0, None

        if depth == 0:

            return _duel_evaluate_board(cb, root_color, eval_bias), None



        legal = list(cb.legal_moves)

        if not legal:

            return _duel_evaluate_board(cb, root_color, eval_bias), None



        ordered = _duel_order_moves(cb, legal, pv_hint)

        value = -MATE_SCORE

        best = None



        next_hint = pv_hint

        for idx, mv in enumerate(ordered):

            cb.push(mv)

            try:

                child_value, _ = negamax(depth - 1, -beta, -alpha, mv if idx == 0 else None)

            except _DuelSearchTimeout:

                cb.pop()

                raise

            child_value = -child_value

            cb.pop()



            if child_value > value:

                value = child_value

                best = mv

            alpha = max(alpha, value)

            if alpha >= beta:

                break



        return value, best



    for depth in range(1, max_depth + 1):

        try:

            value, move = negamax(depth, -MATE_SCORE, MATE_SCORE, pv_move)

        except _DuelSearchTimeout:

            break

        if move is not None:

            best_value = value

            best_move = move

            pv_move = move



    if best_move is None:

        moves = list(cb.legal_moves)

        if not moves:

            return None

        best_move = random.choice(moves)



    sr, sc = _sq_to_rc(best_move.from_square)

    er, ec = _sq_to_rc(best_move.to_square)

    return (sr, sc, er, ec)

def eval_board(board: Board, me: PColor, two_stage=False) -> int:

    score = 0

    for r in range(BOARD_SIZE):

        for c in range(BOARD_SIZE):

            p = board.get(r,c)

            if not p: continue

            val = PIECE_VALUES[p.kind]

            score += val if p.color == me else -int(val*0.3)

            # Mild global incentive to be in the 8-8 during two-stage

            if two_stage:

                if p.color == me:

                    score += 2 if in_chess_area(r,c) else -2

    # centralization bias (stronger in two-stage)

    central = 0

    for r in range(CH_MIN, CH_MAX+1):

        for c in range(CH_MIN, CH_MAX+1):

            p = board.get(r,c)

            if p:

                central += (2 if two_stage else 1) * (1 if p.color==me else -1)

    score += central

    if king_in_check(board, me):

        score -= 3

    # Duel-specific king attack pressure (helps drive checkmates faster)

    try:

        gs_obj = globals().get('gs', None)

        chess_locked = bool(gs_obj and getattr(gs_obj, 'chess_lock', False))

        white_boost = bool(gs_obj and getattr(gs_obj, 'white_duel_boost', False))

        if two_stage and chess_locked:

            # Focus on the opposing seat only (strict chess)

            opp = PColor.BLACK if me == PColor.WHITE else PColor.WHITE

            kp = board.find_king(opp)

            if kp is not None:

                kr, kc = kp

                # Count attacked ring squares around opponent king

                ring = 0

                for dr in (-1, 0, 1):

                    for dc in (-1, 0, 1):

                        if dr == 0 and dc == 0:

                            continue

                        rr, cc = kr+dr, kc+dc

                        if 0 <= rr < BOARD_SIZE and 0 <= cc < BOARD_SIZE:

                            if square_attacked_by_colors(board, rr, cc, [me]):

                                ring += 1

                # Direct check bonus and ring pressure bonus

                atk_w = 4

                ring_w = 2

                if white_boost and me == PColor.WHITE:

                    atk_w = 8

                    ring_w = 4

                if king_in_check(board, opp):

                    score += atk_w

                score += ring * ring_w

    except Exception:

        pass

    return int(score)



def _alive_next_color(board: Board, color: PColor) -> PColor:

    idx = TURN_ORDER.index(color)

    for i in range(1, 5):

        nxt = TURN_ORDER[(idx + i) % 4]

        if board.find_king(nxt) is not None:

            return nxt

    return color



def activate_two_stage_if_needed(board: Board, gs):

    """Detect when only two colors remain and activate two-stage migration.

    This function mutates board and gs in-place.

    """

    alive = board.alive_colors()

    if len(alive) != 2:

        return False

    # Already active?

    if gs.two_stage_active:

        return True

    gs.two_stage_active = True

    # Record finalists for downstream logic

    try:

        gs.final_a, gs.final_b = alive[0], alive[1]

    except Exception:

        gs.final_a = gs.final_b = None

    # Apply migration cleanup; chess_lock will be set later once both fully migrated

    perform_two_stage_migration(board, gs, alive)

    return True



def _remove_color_pieces(board: Board, color: PColor) -> bool:
    removed = False
    for rr in range(BOARD_SIZE):
        for cc in range(BOARD_SIZE):
            piece = board.get(rr, cc)
            if piece and piece.color == color:
                board.set(rr, cc, None)
                removed = True
    if removed:
        try:
            board.king_positions[color] = None  # type: ignore[attr-defined]
        except Exception:
            pass
    return removed


def eliminate_color(board: 'Board', gs_obj: Optional['GameState'], color: PColor, *, reason: str = "capture", flash: bool = False) -> bool:
    """Remove all pieces for a colour and update game-state bookkeeping."""
    if color not in TURN_ORDER:
        return False
    king_pos = None
    try:
        king_pos = board.find_king(color)
    except Exception:
        king_pos = None
    if king_pos is None:
        found = False
        for rr in range(BOARD_SIZE):
            for cc in range(BOARD_SIZE):
                p = board.get(rr, cc)
                if p and p.color == color:
                    found = True
                    break
            if found:
                break
        if not found and not flash:
            return False
    flashed = False
    if flash and gs_obj is not None:
        try:
            gs_obj.start_elim_flash(color, ELIM_FLASH_MS)  # type: ignore[attr-defined]
            flashed = True
        except Exception:
            flashed = False
    removed = _remove_color_pieces(board, color)
    if gs_obj is not None:
        try:
            if hasattr(gs_obj, 'corner_immune'):
                gs_obj.corner_immune[color] = False
            if hasattr(gs_obj, 'corner_promoted'):
                gs_obj.corner_promoted[color] = False
            if hasattr(gs_obj, 'corner_evict_pending'):
                gs_obj.corner_evict_pending[color] = False
            if hasattr(gs_obj, 'corner_in_corner'):
                gs_obj.corner_in_corner[color] = False
            if hasattr(gs_obj, 'entered'):
                gs_obj.entered[color] = False
            if hasattr(gs_obj, 'reduced_applied'):
                gs_obj.reduced_applied[color] = False
            if hasattr(gs_obj, 'player_is_ai'):
                gs_obj.player_is_ai[color] = False
        except Exception:
            pass
        try:
            if hasattr(gs_obj, '_pending_cleanup'):
                gs_obj._pending_cleanup = False
            if flashed and hasattr(gs_obj, '_elim_skip_cleanup'):
                gs_obj._elim_skip_cleanup.add(color)
            else:
                if hasattr(gs_obj, 'elim_flash_color'):
                    gs_obj.elim_flash_color = None
                if hasattr(gs_obj, '_last_flash_color'):
                    gs_obj._last_flash_color = None
        except Exception:
            pass
    try:
        if _CHESS_OK and gs_obj is not None and getattr(gs_obj, 'chess_board', None) is not None:
            gs_obj.chess_board = _setup_chess_board_from_golden(board, gs_obj)
    except Exception:
        pass
    return removed or flashed


def perform_two_stage_migration(board: Board, gs, alive_colors):

    """Apply migration rules as we enter two-player endgame:

    - Remove any piece (except kings) that is outside the central 8-8 chess area.

    - Adjust pawn_dir if finalists are not opposite across the board (i.e., diagonal neighbors).

    Note: We do NOT toggle gs.reduced_applied flags here; those are reserved for

    queen-reduction-on-entry logic handled elsewhere when a finalist first enters 8-8.

    """

    # Remove non-king pieces outside 8x8

    for rr in range(BOARD_SIZE):

        for cc in range(BOARD_SIZE):

            p = board.get(rr, cc)

            if p and p.kind != 'K' and not in_chess_area(rr, cc):

                board.set(rr, cc, None)

    # Determine diagonal/opposite pairing: use TURN_ORDER indices

    a, b = alive_colors[0], alive_colors[1]

    idx_a = TURN_ORDER.index(a); idx_b = TURN_ORDER.index(b)

    # Opposite if (idx_a + 2) % 4 == idx_b

    if (idx_a + 2) % 4 == idx_b:

        # Opponents across the board  treat as classical chess pairing; no pawn_dir flip

        pass

    else:

        # Diagonal pairing: perform pawn direction flip for the player who is to the right of the other

        # Define "to the right" as next in TURN_ORDER from a to b

        # Determine which player is to the right: the one with index (idx_other + 1) mod 4

        # We'll flip pawn_dir for the player whose index equals (other_idx + 1) % 4

        # Simple approach: flip both pawn_dir entries to match symmetry

        gs.pawn_dir[a] = -gs.pawn_dir[a]

        gs.pawn_dir[b] = -gs.pawn_dir[b]

    # Note: seat shift (moving players to vacated seats) is complex relative to piece ownership; we skip physical seat remapping.

    # We intentionally do NOT set gs.reduced_applied here; queen reduction is applied when a side first "enters" the 8-8.



def _approach_terms(board: Board, sr, sc, er, ec) -> Tuple[int,int]:

    """Heuristic for migration: (approach_delta, end_outside_penalty)."""

    mover = board.get(sr, sc)

    start_d = dist_to_chess(sr, sc)

    end_d   = dist_to_chess(er, ec)

    improve = start_d - end_d

    kfactor = 3 if mover and mover.kind == 'K' else 1

    approach = kfactor * improve              # prefer reducing distance, esp. for kings

    end_pen  = - (3 if mover and mover.kind == 'K' else 1) * (1 if end_d > 0 else 0)  # penalize ending outside

    return approach, end_pen



def choose_ai_move_fast(board: Board, color: PColor, two_stage: bool, must_enter_filter=None, grace_block_fn=None, opponent: Optional[PColor]=None):

    legal = all_legal_moves_for_color(board, color)

    if not legal: return None

    # Migration filters removed in v2; keep legal as-is before pre-lock checks

    gs_obj = globals().get('gs')

    if gs_obj:

        # Pre-lock stay-inside: if this color has entered, keep moves inside 8-8

        try:

            if two_stage and color in (gs_obj.final_a, gs_obj.final_b) and gs_obj.entered.get(color, False) and not getattr(gs_obj, 'chess_lock', False):

                legal = [(sr,sc,er,ec) for (sr,sc,er,ec) in legal if in_chess_area(er,ec)]

            # Legacy migration no-exit rule removed in v2

        except Exception:

            pass

        if getattr(gs_obj, 'chess_lock', False):

            legal = [(sr,sc,er,ec) for (sr,sc,er,ec) in legal if in_chess_area(er,ec)]

    if two_stage and grace_block_fn:

        non_check = [m for m in legal if not grace_block_fn(m, opponent)]

        legal = non_check if non_check else legal

    if not legal: return None

    best, best_score = [], -10**9

    start_ts = pygame.time.get_ticks()

    pump_counter = 0

    # Precompute a cheap mobility estimate (gen_moves counts) to order moves: prefer captures and higher approach

    def move_order_key(m):

        sr,sc,er,ec = m

        tgt = board.get(er,ec)

        capv = PIECE_VALUES.get(tgt.kind, 0) if tgt and tgt.color != color else 0

        app, pen = _approach_terms(board, sr, sc, er, ec) if two_stage else (0,0)

        # mobility after (cheap): number of pseudo-moves from the landing square for the mover

        mover = board.get(sr,sc)

        cheap_mob = 0

        if mover:

            # estimate: number of gen_moves for the moved piece at destination (cheap, pseudo)

            cap, ph, pk, eff = board_do_move(board, sr, sc, er, ec, simulate=True)

            moved = board.get(er,ec)

            cheap_mob = len(gen_moves(board, er, ec)) if moved else 0

            board_undo_move(board, sr, sc, er, ec, cap, ph, pk, eff)

        # sort by (capture value, approach, mobility)

        return (capv, app, cheap_mob)



    legal.sort(key=move_order_key, reverse=True)



    # Determine left-neighbor target only in non two-stage play

    target_left = None

    if not two_stage:

        try:

            target_left = _alive_next_color(board, color)

        except Exception:

            target_left = None



    for (sr,sc,er,ec) in legal:

        # Budget guard and occasional pump to keep window responsive

        now = pygame.time.get_ticks()

        if now - start_ts > FAST_AI_BUDGET_MS:

            break

        pump_counter += 1

        if (pump_counter % 10) == 0:

            try:

                pygame.event.pump()

            except Exception:

                pass



        cap, ph, pk, eff = board_do_move(board, sr, sc, er, ec, simulate=True)

        score = eval_board(board, color, two_stage=two_stage)

        moved = board.get(er,ec)

        mover_before = board.get(er,ec)  # after simulate, piece is at er,ec

        # Duel-aware development incentives: encourage first bishop/pawn moves

        if two_stage and mover_before:

            try:

                # Reward moving an unmoved bishop or pawn early in duel

                if mover_before.kind == 'B' and not getattr(mover_before, 'has_moved', False):

                    score += 6

                if mover_before.kind == 'P' and not getattr(mover_before, 'has_moved', False):

                    score += 2

            except Exception:

                pass

        if cap and cap.color != color:

            cap_val = PIECE_VALUES.get(cap.kind, 0)

            # Extra weight if capturing the immediate-left target in 3-player stage

            if (not two_stage) and target_left is not None and cap.color == target_left:

                score += cap_val * 10  # prioritize dismantling the target

            else:

                score += cap_val * 8

        # Target-aware check bonus in 3-player stage (prefer checking the left neighbor)

        if (not two_stage) and target_left is not None:

            try:

                gives_check_target = king_in_check(board, target_left)

                if gives_check_target:

                    score += 14

                # Lightly discourage giving check to the non-target rival (can waste tempo)

                others = [c for c in TURN_ORDER if c not in (color, target_left) and board.find_king(c) is not None]

                for oc in others:

                    if king_in_check(board, oc):

                        score -= 4

                        break

            except Exception:

                pass

        # Cheap mobility tie-break: moves available for the moved piece at destination

        try:

            cheap_mob = len(gen_moves(board, er, ec)) if moved else 0

            score += cheap_mob * 0.5

        except Exception:

            pass

        # Penalize simple ping-pong (move and immediate reverse) observed in recent moves

        gs_obj = globals().get('gs')

        if gs_obj is not None:

            # Check last move: if opponent just moved from er,ec -> sr,sc then this move is a direct reversal

            if len(gs_obj.recent_moves) >= 1:

                last = gs_obj.recent_moves[-1]

                if last and last[1] == er and last[2] == ec and last[3] == sr and last[4] == sc:

                    # discourage immediate reversal strongly

                    score -= 12

            # Also check for short back-and-forth loop: A->B then B->A earlier

            if len(gs_obj.recent_moves) >= 3:

                a = gs_obj.recent_moves[-1]

                b = gs_obj.recent_moves[-2]

                c = gs_obj.recent_moves[-3]

                # if pattern (you move X->Y, opponent Y->X) then penalize continuing the loop

                if a and b and c:

                    if b[1] == er and b[2] == ec and b[3] == sr and b[4] == sc and c[1] == sr and c[2] == sc and c[3] == er and c[4] == ec:

                        score -= 8

        # Reward pawn forward moves (encourage pawn progress into center/8x8)

        moved_piece = moved

        if moved_piece and moved_piece.kind == 'P':

            # reward forward displacement towards chess area

            start_dist = dist_to_chess(sr, sc)

            end_dist = dist_to_chess(er, ec)

            dp = start_dist - end_dist

            score += max(0, dp) * 3

        # Safety/positional heuristics

        # Landing in enemy fire? penalize (stronger penalty)

        score += net_hanging_penalty(board, moved, er, ec) * 2

        # Over-aggressive queen advances in early game and duel

        if moved and moved.kind == 'Q':

            dr = abs(er - sr); dc = abs(ec - sc); leap = max(dr, dc)

            score -= 6 if leap >= 3 else 0

            # In duel, lightly discourage non-capturing queen shuffles

            if two_stage and not cap:

                score -= 4

        # Prefer minor piece development toward the 8x8 and center

        if moved and moved.kind in ('N','B'):

            score += 4 + (3 if two_stage and moved.kind == 'B' else 0)

        # migration heuristics

        app, pen = _approach_terms(board, sr, sc, er, ec)

        cent = 2 if in_chess_area(er,ec) and two_stage else (1 if in_chess_area(er,ec) else 0)

        score += (app*2 + pen*2 + cent*2) if two_stage else 0

        # small randomness to break ties deterministically (but varied by move)

        score += random.random() * 0.001

        # Deprioritize moves that create a threefold repetition (if avoidable)

        gs_obj = globals().get('gs')

        makes_threefold = False

        if gs_obj is not None:

            try:

                # compute position key after simulated move

                k = gs_obj._position_key(board)

                if gs_obj.pos_counts.get(k, 0) + 1 >= 3:

                    makes_threefold = True

            except Exception:

                makes_threefold = False

        if makes_threefold:

            score -= 100  # strong penalty to avoid threefold repeats

        # Undo the simulated move before proceeding

        board_undo_move(board, sr, sc, er, ec, cap, ph, pk, eff)

        if score > best_score: best_score, best = score, [(sr,sc,er,ec)]

        elif abs(score - best_score) < 1e-6: best.append((sr,sc,er,ec))

    return random.choice(best) if best else None



def choose_ai_move_smart(board: Board, color: PColor, two_stage: bool, must_enter_filter=None, grace_block_fn=None, opponent: Optional[PColor]=None, time_ms: int = 1200):

    best_move = None

    best_val = -10**9

    start = pygame.time.get_ticks()

    deadline = start + max(200, time_ms)

    me = color



    def time_up(): return pygame.time.get_ticks() >= deadline



    def search(side: PColor, depth: int, alpha: int, beta: int) -> int:

        if time_up(): return eval_board(board, me, two_stage=two_stage)

        if depth <= 0: return eval_board(board, me, two_stage=two_stage)

        moves = all_legal_moves_for_color(board, side)

        if two_stage and must_enter_filter:

            moves = must_enter_filter(moves)

        gs_obj = globals().get('gs')

        if gs_obj:

            # Pre-lock stay-inside for this side if they've entered

            try:

                if two_stage and side in (gs_obj.final_a, gs_obj.final_b) and gs_obj.entered.get(side, False) and not getattr(gs_obj, 'chess_lock', False):

                    moves = [(sr,sc,er,ec) for (sr,sc,er,ec) in moves if in_chess_area(er,ec)]

                # Pre-lock no-exit per piece

                if two_stage and side in (gs_obj.final_a, gs_obj.final_b) and not getattr(gs_obj, 'chess_lock', False):

                    kept = []

                    for (sr,sc,er,ec) in moves:

                        if in_chess_area(sr,sc) and not in_chess_area(er,ec):

                            continue

                        kept.append((sr,sc,er,ec))

                    moves = kept

            except Exception:

                pass

            if getattr(gs_obj, 'chess_lock', False):

                moves = [(sr,sc,er,ec) for (sr,sc,er,ec) in moves if in_chess_area(er,ec)]

        if two_stage and grace_block_fn:

            non_check = [m for m in moves if not grace_block_fn(m, opponent if side==me else me)]

            moves = non_check if non_check else moves

        if not moves: return eval_board(board, me, two_stage=two_stage)

        def mkey(m):

            return moves

        gs_obj = globals().get('gs')

        if gs_obj and getattr(gs_obj, 'chess_lock', False):

            moves = [(sr,sc,er,ec) for (sr,sc,er,ec) in moves if in_chess_area(er,ec)]

        if two_stage and grace_block_fn:

            non_check = [m for m in moves if not grace_block_fn(m, opponent)]

            moves = non_check if non_check else moves

        if not moves: return None

        # Determine left-neighbor target only in non two-stage play

        target_left = None

        if not two_stage:

            try:

                target_left = _alive_next_color(board, me)

            except Exception:

                target_left = None



        def mkey(m):

            sr,sc,er,ec = m

            tgtp = board.get(er, ec)

            capv = PIECE_VALUES.get(tgtp.kind, 0) if tgtp and tgtp.color != me else 0

            # Target-aware capture priority boost in 3-player stage

            if (not two_stage) and target_left is not None and tgtp and tgtp.color == target_left:

                capv += 4

            app, pen = _approach_terms(board, sr, sc, er, ec) if two_stage else (0,0)

            cent = 2 if in_chess_area(er,ec) and two_stage else (1 if in_chess_area(er,ec) else 0)

            # Rough proximity to center stays as weak tie-breaker

            return (capv, cent, app, -dist_to_chess(er,ec), -abs( (er-6)**2 + (ec-6)**2 ))

        moves.sort(key=mkey, reverse=True)

        nxt = _alive_next_color(board, me)

        cand_move = None; cand_val = -10**9

        for (sr,sc,er,ec) in moves:

            if time_up(): break

            cap, ph, pk, eff = board_do_move(board, sr,sc,er,ec, simulate=True)

            val = search(nxt, depth-1, -10**9, 10**9)

            # 3-player target-aware bonus: checking left-neighbor is valuable; checking the third wheel is less so

            if (not two_stage) and target_left is not None:

                try:

                    if king_in_check(board, target_left):

                        val += 12

                    # discourage checking the non-target rival a bit to reduce wasted tempo

                    others = [c for c in TURN_ORDER if c not in (me, target_left) and board.find_king(c) is not None]

                    for oc in others:

                        if king_in_check(board, oc):

                            val -= 3

                            break

                except Exception:

                    pass

            board_undo_move(board, sr,sc,er,ec, cap, ph, pk, eff)

            if val > cand_val: cand_val, cand_move = val, (sr,sc,er,ec)

        if cand_move is not None: best_move, best_val = cand_move, cand_val

    # if time_up(): break  # Removed: not inside a loop

    if best_move is None:

        return choose_ai_move_fast(board, me, two_stage, must_enter_filter, grace_block_fn, opponent)

    return best_move



def choose_ai_move(board: Board, color: PColor, two_stage: bool, must_enter_filter=None, grace_block_fn=None, opponent: Optional[PColor]=None):

    if AI_STRENGTH == "smart":

        # If we're in chess-lock duel mode, give a bigger time budget

        gs_obj = globals().get('gs')

        duel_ms = DUEL_AI_TIME_MS if (gs_obj and getattr(gs_obj, 'chess_lock', False)) else 1200

        # Temporary boost: extra time for White in duel when enabled

        try:

            if gs_obj and getattr(gs_obj, 'chess_lock', False) and getattr(gs_obj, 'white_duel_boost', False) and color == PColor.WHITE:

                duel_ms = int(duel_ms * 1.5)

        except Exception:

            pass

        if gs_obj and getattr(gs_obj, 'chess_lock', False):

            duel_move = choose_duel_move(board, color, duel_ms)

            if duel_move:

                return duel_move

        return choose_ai_move_smart(board, color, two_stage, must_enter_filter, grace_block_fn, opponent, time_ms=duel_ms)

    else:

        return choose_ai_move_fast(board, color, two_stage, must_enter_filter, grace_block_fn, opponent)



# ====== IMAGE LOADING / RECOLORING ======

_image_cache = {}

_base_white  = {}

_missing_any_image = False



def load_base_white(kind):

    path = os.path.join(ASSET_DIR, f"white_{kind}.png")

    if not os.path.exists(path):

        return None

    try:

        surf = pygame.image.load(path)
        try:
            surf = surf.convert_alpha()
        except pygame.error:
            pass

    except Exception:

        return None

    max_w = max_h = SQUARE - 6

    return pygame.transform.smoothscale(surf, (max_w, max_h))



def tinted_piece(color: PColor, kind: str, custom_rgb: Optional[Tuple[int, int, int]] = None):

    global _missing_any_image

    key_color = ('custom', tuple(int(v) for v in custom_rgb)) if custom_rgb is not None else color

    key = (key_color, kind, SQUARE)

    if key in _image_cache:

        return _image_cache[key]

    if kind not in _base_white:

        _base_white[kind] = load_base_white(kind)

    base = _base_white[kind]

    if base is None:

        _missing_any_image = True

        return None

    tint = pygame.Surface(base.get_size(), flags=pygame.SRCALPHA)

    if custom_rgb is not None:

        r, g, b = (int(max(0, min(255, v))) for v in custom_rgb)

    else:

        r, g, b = PLAYER_COLORS[color]

    tint.fill((r, g, b, 255))

    out = base.copy()

    out.blit(tint, (0,0), special_flags=pygame.BLEND_RGBA_MULT)

    _image_cache[key] = out

    return out



# ====== WINDOW ======

def _compute_scaling():

    """Compute SQUARE and window size that fit on current display, preserving layout.

    Leaves a safe bottom margin to avoid overlapping Windows taskbar when not auto-hidden.

    """

    global SQUARE, LOGICAL_W, LOGICAL_H, TOTAL_W

    try:

        info = pygame.display.Info()

        screen_w, screen_h = int(info.current_w), int(info.current_h)

    except Exception:

        # Fallback to a conservative 1366x768 if display info not available yet

        screen_w, screen_h = 1366, 768

    # Aim for the original visual size first, then reduce only if needed to fit.

    desired_square = DEFAULT_SQUARE

    # Compute desired window size with desired square

    desired_logical_w = BOARD_SIZE * desired_square

    desired_logical_h = BOARD_SIZE * desired_square + 44

    desired_total_w   = desired_logical_w + SIDEBAR_W_MIN



    # Available bounds (with safe margins)

    avail_w = max(640, screen_w - 20)  # small horizontal padding

    avail_h = max(480, screen_h - SAFE_BOTTOM_MARGIN)



    if desired_total_w <= avail_w and desired_logical_h <= avail_h:

        sq = desired_square

    else:

        # Determine the largest square that fits both width and height constraints

        max_square_w = (avail_w - SIDEBAR_W_MIN) // BOARD_SIZE

        max_square_h = (avail_h - 44) // BOARD_SIZE  # leave status bar space

        sq = max(MIN_SQUARE, min(max_square_w, max_square_h))

    # Apply

    SQUARE = int(sq)

    LOGICAL_W  = BOARD_SIZE * SQUARE

    LOGICAL_H  = BOARD_SIZE * SQUARE + 44 + EXTRA_WINDOW_HEIGHT_PX

    TOTAL_W    = LOGICAL_W + SIDEBAR_W_MIN

    return TOTAL_W, LOGICAL_H



def _clear_caches_on_scale_change():

    """Clear caches that depend on SQUARE so images and layout re-render correctly."""

    try:

        _image_cache.clear()

    except Exception:

        pass



_WINDOW_ICON_SURFACE = None
_WINDOW_ICON_DISABLED = False


def ensure_window_icon():

    """Load and apply the custom window icon once; ignore failures silently."""

    global _WINDOW_ICON_SURFACE, _WINDOW_ICON_DISABLED

    if _WINDOW_ICON_DISABLED:

        return

    if _WINDOW_ICON_SURFACE is None:

        if not os.path.exists(WINDOW_ICON_PATH):

            _WINDOW_ICON_DISABLED = True

            return

        try:

            surf = pygame.image.load(WINDOW_ICON_PATH)

            try:

                surf = surf.convert_alpha()

            except pygame.error:

                pass

            _WINDOW_ICON_SURFACE = surf

        except Exception:

            _WINDOW_ICON_DISABLED = True

            _WINDOW_ICON_SURFACE = None

            return

    try:

        pygame.display.set_icon(_WINDOW_ICON_SURFACE)

    except Exception:

        pass


def _launch_async(func, *args, **kwargs):

    """Run `func` in a daemon thread; swallow thread start failures."""

    try:

        threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True).start()

    except Exception:

        pass


def _open_with_default_app(target: str) -> bool:
    """Best-effort attempt to open a path with the user's default OS handler."""
    target = os.path.normpath(target)

    try:
        if os.name == 'nt':
            try:
                import ctypes
                ShellExecuteW = ctypes.windll.shell32.ShellExecuteW
                SW_SHOWNORMAL = 1
                res = ShellExecuteW(None, 'open', target, None, None, SW_SHOWNORMAL)
                if res and res > 32:
                    return True
            except Exception:
                pass
            try:
                os.startfile(target)
                return True
            except Exception:
                pass
            try:
                import subprocess
                subprocess.Popen(['explorer.exe', target],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                return True
            except Exception:
                pass
            try:
                import subprocess
                subprocess.Popen(['cmd', '/c', 'start', '', target],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                return True
            except Exception:
                pass
            try:
                import subprocess
                subprocess.Popen(
                    [
                        'powershell.exe',
                        '-NoProfile',
                        '-WindowStyle',
                        'Hidden',
                        '-Command',
                        ("Start-Process -FilePath explorer.exe -ArgumentList @(" +
                         repr(target).replace('\\\\', '\\\\') + ")")
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
            except Exception:
                pass
            try:
                import subprocess
                subprocess.Popen(
                    f'start "" "{target}"',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
            except Exception:
                pass
        else:
            import subprocess
            opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
            subprocess.Popen([opener, target],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return True
    except Exception:
        pass
    try:
        import pathlib
        import webbrowser
        uri = pathlib.Path(target).resolve().as_uri()
        if webbrowser.open(uri, new=1):
            return True
    except Exception:
        pass
    return False


def _load_library_entries(folder: str) -> List[Dict[str, object]]:
    """Return saved game metadata sorted newest-first."""
    entries: List[Dict[str, object]] = []
    meta_map: Dict[str, Dict[str, object]] = {}
    idx_path = os.path.join(folder, 'index.json')
    if os.path.exists(idx_path):
        try:
            with open(idx_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict) and item.get('file'):
                        meta_map[str(item['file'])] = item
        except Exception as exc:
            print(f"[LIBRARY] failed to load index.json: {exc}")
    try:
        file_names = [
            fn for fn in os.listdir(folder)
            if fn.lower().endswith('.pgn.txt')
        ]
    except Exception as exc:
        print(f"[LIBRARY] failed to list games folder: {exc}")
        file_names = []
    file_names.sort(reverse=True)
    from datetime import datetime
    for fname in file_names:
        path = os.path.join(folder, fname)
        info: Dict[str, object] = {
            'file': fname,
            'path': path,
            'exists': os.path.exists(path),
            'moves': None,
            'winner': None,
            'timestamp': None,
            'display_ts': '',
        }
        meta = meta_map.get(fname, {})
        if isinstance(meta, dict):
            info['moves'] = meta.get('moves')
            info['winner'] = meta.get('winner')
            info['timestamp'] = meta.get('timestamp')
        ts_raw = info.get('timestamp')
        ts_display = ''
        try:
            if ts_raw:
                dt_obj = datetime.strptime(str(ts_raw), '%Y-%m-%d_%H-%M-%S')
                ts_display = dt_obj.strftime('%b %d, %Y %H:%M')
        except Exception:
            ts_display = ''
        if not ts_display:
            try:
                stat = os.stat(path)
                dt_obj = datetime.fromtimestamp(stat.st_mtime)
                ts_display = dt_obj.strftime('%b %d, %Y %H:%M')
            except Exception:
                ts_display = ''
        info['display_ts'] = ts_display
        try:
            info['size'] = os.path.getsize(path)
        except Exception:
            info['size'] = None
        entries.append(info)
    return entries


def activate_library_overlay(folder: str) -> None:
    """Populate UI state with an in-game library listing overlay."""
    try:
        os.makedirs(folder, exist_ok=True)
        entries = _load_library_entries(folder)
        try:
            print(f"[LIBRARY] overlay activated: {len(entries)} entries from {folder}")
        except Exception:
            pass
        UI_STATE['library_overlay'] = {
            'folder': folder,
            'entries': entries,
            'generated': pygame.time.get_ticks() if pygame.get_init() else 0,
        }
        UI_STATE['library_overlay_scroll'] = 0
        UI_STATE.pop('library_overlay_rect', None)
        UI_STATE.pop('library_overlay_max_scroll', None)
    except Exception as exc:
        print(f"[LIBRARY] overlay activation failed: {exc}")
        try:
            show_toast("Could not load games library.", ms=2200)
        except Exception:
            pass


def _build_library_html(folder: str) -> Optional[str]:
    """Generate a light HTML view of saved games for use as a fallback."""
    try:
        entries = _load_library_entries(folder)
        lines = [
            "<!doctype html>",
            "<meta charset='utf-8'>",
            "<title>Saved Games Library</title>",
            "<style>",
            "body{font-family:Segoe UI,Tahoma,sans-serif;background:#111;color:#eee;padding:20px;}",
            "h1{font-size:22px;margin-bottom:12px;}",
            "a{color:#7fdcff;text-decoration:none;}",
            "a:hover{text-decoration:underline;}",
            "table{border-collapse:collapse;width:100%;max-width:720px;}",
            "th,td{border-bottom:1px solid #2c2c2c;padding:6px 8px;text-align:left;}",
            "tr:hover{background:#1f1f1f;}",
            ".muted{color:#9a9a9a;font-size:13px;margin-top:18px;}",
            "</style>",
            "<h1>Saved Games</h1>",
        ]
        if not entries:
            lines.append("<p>No saved games yet. Finish a match to populate this list.</p>")
        else:
            lines.append("<table>")
            lines.append("<tr><th>File</th><th>Moves</th><th>Result</th><th>Recorded</th></tr>")
            for entry in entries:
                fname = entry.get('file', '')
                moves = entry.get('moves', '')
                winner = entry.get('winner', '')
                ts_disp = entry.get('display_ts', '')
                href = str(fname).replace("'", "%27")
                lines.append(
                    f"<tr><td><a href='{href}'>{fname}</a></td>"
                    f"<td>{moves or ''}</td><td>{winner or ''}</td><td>{ts_disp or ''}</td></tr>"
                )
            lines.append("</table>")
        lines.append(
            "<p class='muted'>Files open in your default editor. "
            "You can copy them directly from this page or via the file explorer.</p>"
        )
        html_path = os.path.join(folder, 'library_index.html')
        with open(html_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(lines))
        return html_path
    except Exception as exc:
        print(f"[LIBRARY] failed to build HTML fallback: {exc}")
    return None


def save_game_record_if_ready(entries, winner_name: Optional[str] = None, duel_mode: bool = False) -> bool:
    """Persist the supplied move list if it meets the minimum length requirement."""
    try:
        cleaned = [str(e) for e in entries if e]
        min_moves = 2 if duel_mode else 4
        if len(cleaned) < min_moves:
            return False
        games_dir = os.path.join(SCRIPT_DIR, 'games')
        os.makedirs(games_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        idx_path = os.path.join(games_dir, 'index.json')
        index_entries = []
        if os.path.exists(idx_path):
            try:
                with open(idx_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        index_entries = data
            except Exception:
                index_entries = []
        txt_path = os.path.join(games_dir, f'game_{ts}.pgn.txt')
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(cleaned))
        meta = {'file': os.path.basename(txt_path), 'timestamp': ts, 'moves': len(cleaned)}
        if winner_name:
            meta['winner'] = winner_name
        index_entries.append(meta)
        try:
            with open(idx_path, 'w', encoding='utf-8') as f:
                json.dump(index_entries, f, indent=2)
        except Exception:
            pass
        return True
    except Exception:
        return False


def open_games_library_async():

    """Open the games directory in the OS file browser without blocking the UI."""

    def _task():

        try:

            folder = os.path.join(SCRIPT_DIR, 'games')

            os.makedirs(folder, exist_ok=True)

            opened = _open_with_default_app(folder)
            try:
                print(f"[LIBRARY] _open_with_default_app returned {opened}")
            except Exception:
                pass

            if not opened:
                html_path = _build_library_html(folder)
                if html_path:
                    try:
                        import webbrowser
                        import pathlib
                        webbrowser.open(pathlib.Path(html_path).resolve().as_uri(), new=1)
                        opened = True
                        print("[LIBRARY] opened HTML fallback for games library")
                    except Exception as exc:
                        print(f"[LIBRARY] failed to launch HTML fallback: {exc}")
                if not opened:
                    try:
                        show_toast("Games folder could not be opened automatically.", ms=2200)
                        UI_STATE['library_path'] = folder
                        print(f"[LIBRARY] Unable to open games folder: {folder}")
                    except Exception:
                        pass
            else:
                try:
                    print('[LIBRARY] games folder opened via default handler')
                except Exception:
                    pass

        except Exception:

            pass

    _launch_async(_task)


def export_rules_and_open_async():

    """Export the rules reference (if the helper exists) and open the resulting PDF or folder."""

    def _task():

        out_dir = os.path.join(SCRIPT_DIR, 'docs')

        try:

            os.makedirs(out_dir, exist_ok=True)

        except Exception:

            pass

        tool = os.path.join(SCRIPT_DIR, 'tools', 'export_rules.py')

        if not os.path.exists(tool):

            alt = os.path.join(os.path.dirname(SCRIPT_DIR), 'tools', 'export_rules.py')

            if os.path.exists(alt):

                tool = alt

            else:

                tool = None

        if tool is not None:

            try:

                import subprocess

                subprocess.run([sys.executable or 'python', tool, '--out', out_dir, '--quiet'],

                               cwd=os.path.dirname(tool), check=False,

                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            except Exception:

                pass

        pdf_path = os.path.join(out_dir, 'rules.pdf')

        txt_path = os.path.join(out_dir, 'rules.txt')

        target = pdf_path if os.path.exists(pdf_path) else txt_path if os.path.exists(txt_path) else out_dir

        _open_with_default_app(target)

    _launch_async(_task)


def pick_initial_window():

    # Compute initial sizing that fits current screen

    w, h = _compute_scaling()

    # Enable double buffering to reduce flicker on Windows when resizing/maximizing

    flags = pygame.RESIZABLE | pygame.DOUBLEBUF

    try:

        # Position the window slightly lower from the top edge

        os.environ['SDL_VIDEO_WINDOW_POS'] = f"20,{WINDOW_Y_OFFSET_PX}"

    except Exception:

        pass

    scr = pygame.display.set_mode((w, h), flags)

    try:

        drv = pygame.display.get_driver()

        print(f"[WINDOW] video driver={drv} size={scr.get_size()} flags={flags}")

    except Exception:

        pass

    ensure_window_icon()

    return scr



# ====== Sidebar UI ======

_sidebar_font_cache = {}

UI_RECTS: Dict[str, pygame.Rect] = {}

UI_STATE: Dict[str, object] = {}



def get_sidebar_font(size=18, bold=False):

    key = (size, bold)

    if key not in _sidebar_font_cache:

        _sidebar_font_cache[key] = pygame.font.SysFont("Arial", size, bold=bold)

    return _sidebar_font_cache[key]



def draw_button(screen, rect: pygame.Rect, label: str, active: bool=True, font_size: int=18, key: Optional[str]=None):

    k = key if key is not None else label

    pressed = UI_STATE.get(f'pressed_{k}', False) if UI_STATE is not None else False

    hovered = UI_STATE.get(f'hover_{k}', False) if UI_STATE is not None else False

    # pressed visual slightly darker and offset

    r = rect.move(0, 2) if pressed else rect

    # base colors

    bg_base = (58,58,66) if active else (35,35,40)

    fg = (235,235,235) if active else (160,160,160)

    # hover lighten

    if hovered and active:

        bg = (min(bg_base[0]+12, 255), min(bg_base[1]+12, 255), min(bg_base[2]+12, 255))

    else:

        bg = bg_base

    # pressed darken

    if pressed and active:

        bg = (max(bg[0]-16, 0), max(bg[1]-16, 0), max(bg[2]-16, 0))

    pygame.draw.rect(screen, bg, r, border_radius=8)

    border_col = (128,128,150) if hovered else (98,98,110)

    pygame.draw.rect(screen, border_col, r, 1, border_radius=8)

    font = get_sidebar_font(font_size, True)

    surf = font.render(label, True, fg)

    text_rect = surf.get_rect(center=r.center)

    if pressed:

        text_rect = text_rect.move(0, 1)

    screen.blit(surf, text_rect)



def draw_sidebar(screen, moves_list, scroll_offset, show_material, captured_points, auto_elim_enabled, two_stage, grace_active, game_over: bool=False):

    win_w, _ = screen.get_size()

    w  = max(SIDEBAR_W_MIN, win_w - LOGICAL_W)

    x0 = LOGICAL_W

    rect = pygame.Rect(x0, 0, w, LOGICAL_H)



    pygame.draw.rect(screen, (25,25,28), rect)

    pygame.draw.line(screen, (70,70,70), (x0, 0), (x0, LOGICAL_H), 2)



    title_font = get_sidebar_font(22, True)

    header = title_font.render("Move List", True, (220,220,220))

    screen.blit(header, (x0 + 12, 10))



    btn_h = 36

    gaps = 12

    cols = 3

    btn_w = (w - 24 - (cols-1)*gaps) // cols  # uniform button width



    # Play Again + end-state buttons when game is over (full-width)

    base_x = x0 + 12

    if game_over:

        try:

            gs_local = globals().get('gs', None)

            wcol = getattr(gs_local, 'last_winner', None)

        except Exception:

            gs_local = None

            wcol = None

        y_btn = 10 + 34

        if wcol is not None:

            label = f"Checkmate by {wcol.name.title()}"

            r_mate = pygame.Rect(base_x, y_btn, btn_w, btn_h)

            draw_button(screen, r_mate, label, active=False, font_size=17, key='btn_checkmate_by')

            UI_RECTS['btn_checkmate_by'] = r_mate

            y_btn += btn_h + 8

        else:

            UI_RECTS.pop('btn_checkmate_by', None)

    else:

        y_btn = 10

        UI_RECTS.pop('btn_checkmate_by', None)



    # ---- Controls grid ----

    try:

        gs_local = globals().get('gs', None)

        waiting = bool(getattr(gs_local, 'waiting_ready', False))

    except Exception:

        waiting = False



    # Row 1: Mode / AI / Material

    r_mode = pygame.Rect(x0 + 12 + (btn_w+gaps)*0, y_btn + 34, btn_w, btn_h)

    r_ai   = pygame.Rect(x0 + 12 + (btn_w+gaps)*1, y_btn + 34, btn_w, btn_h)

    r_mat  = pygame.Rect(x0 + 12 + (btn_w+gaps)*2, y_btn + 34, btn_w, btn_h)

    mode_lbl = f"Mode: {UI_STATE.get('mode', 'LONG')}"

    draw_button(screen, r_mode, mode_lbl, font_size=18, key='btn_mode')

    # Optional: Scaled rendering toggle to reduce flicker on resize for some GPUs

    try:

        scaled_on = bool(UI_STATE.get('scaled_mode', False))

        # Place Scaled toggle below Row 1 (mode/ai/material)

        r_scaled = pygame.Rect(base_x, y_btn + 34 + btn_h + 8, btn_w, btn_h)

        draw_button(screen, r_scaled, f"Scaled Mode: {'On' if scaled_on else 'Off'}", font_size=18, key='btn_scaled')

        UI_RECTS['btn_scaled'] = r_scaled

        # Shift subsequent rows down to accommodate the new button

        y_row2 = y_btn + 34 + btn_h + 8 + btn_h + 8

    except Exception:

        UI_RECTS.pop('btn_scaled', None)

    draw_button(screen, r_ai, f"AI: {AI_STRENGTH.upper() if hasattr(AI_STRENGTH,'upper') else str(AI_STRENGTH).upper()}", font_size=18, key='btn_ai')

    draw_button(screen, r_mat, f"Material: {'On' if show_material else 'Off'}", font_size=18, key='btn_material')

    # Overwrite button rects each draw to match current layout (prevents stale overlay artifacts on resize)

    UI_RECTS['btn_mode'] = r_mode

    UI_RECTS['btn_ai']   = r_ai

    UI_RECTS['btn_material'] = r_mat



    # Row 2: Back / Resume / Forward

    # y_row2 may have been updated above if Scaled button was placed

    y_row2 = locals().get('y_row2', y_btn + 34 + btn_h + 8)

    r_back   = pygame.Rect(x0 + 12 + (btn_w+gaps)*0, y_row2, btn_w, btn_h)

    r_resume = pygame.Rect(x0 + 12 + (btn_w+gaps)*1, y_row2, btn_w, btn_h)

    r_fwd    = pygame.Rect(x0 + 12 + (btn_w+gaps)*2, y_row2, btn_w, btn_h)

    draw_button(screen, r_back, " Back", font_size=18, key='btn_back')

    draw_button(screen, r_resume, " Resume", font_size=18, key='btn_resume')

    draw_button(screen, r_fwd, " Forward", font_size=18, key='btn_fwd')

    UI_RECTS['btn_back']   = r_back

    UI_RECTS['btn_resume'] = r_resume

    UI_RECTS['btn_fwd']    = r_fwd



    # Row 3: Auto-Elim / View / Export

    y_row3 = y_row2 + btn_h + 8

    # Build Auto-Elim label based on threshold in gs

    try:

        thresh = int(getattr(globals().get('gs', None), 'auto_elim_threshold', 18))

    except Exception:

        thresh = 18

    if two_stage:

        auto_label = f"Auto-Elim {thresh if thresh>0 else 'Off'}: (Suppressed)"

    else:

        auto_label = f"Auto-Elim {thresh if thresh>0 else 'Off'}"

    r_auto  = pygame.Rect(x0 + 12 + (btn_w+gaps)*0, y_row3, btn_w, btn_h)

    r_view  = pygame.Rect(x0 + 12 + (btn_w+gaps)*1, y_row3, btn_w, btn_h)

    r_expo  = pygame.Rect(x0 + 12 + (btn_w+gaps)*2, y_row3, btn_w, btn_h)

    draw_button(screen, r_auto, auto_label, active=not two_stage, font_size=18, key='btn_autoelim')

    # Show if the view is currently locked (single human seat)

    try:

        gs_local = globals().get('gs', None)

        humans_now = [c for c in TURN_ORDER if gs_local and not getattr(gs_local, 'player_is_ai', {}).get(c, False)]

        locked = (len(humans_now) == 1)

    except Exception:

        locked = False

    view_lbl = f"View: {UI_STATE.get('view_seat','AUTO')}{' (locked)' if locked else ''}"

    draw_button(screen, r_view, view_lbl, font_size=18, key='btn_view')

    draw_button(screen, r_expo, "Export .txt", font_size=18, key='btn_export')

    UI_RECTS['btn_autoelim'] = r_auto

    UI_RECTS['btn_view']     = r_view

    UI_RECTS['btn_export']   = r_expo



    # Coordinates (a1h8) toggle  default OFF

    y_row3b = y_row3 + btn_h + 8

    r_coords = pygame.Rect(base_x, y_row3b, btn_w, btn_h)

    coords_on = bool(UI_STATE.get('show_coords', False))

    draw_button(screen, r_coords, f"Coordinates: {'On' if coords_on else 'Off'}", font_size=18, key='btn_coords')

    UI_RECTS['btn_coords'] = r_coords

    y_row4 = y_row3b + btn_h + 8



    # Row 4: Logs toggle + Rules (PDF)

    r_logs = pygame.Rect(base_x, y_row4, btn_w, btn_h)

    r_rules = pygame.Rect(base_x + (btn_w + gaps), y_row4, btn_w, btn_h)

    r_library = pygame.Rect(base_x + (btn_w + gaps) * 2, y_row4, btn_w, btn_h)

    logs_on = globals().get('VERBOSE_DEBUG', False)

    draw_button(screen, r_logs, f"Logs: {'On' if logs_on else 'Off'}", font_size=18, key='btn_logs')

    UI_RECTS['btn_logs'] = r_logs

    draw_button(screen, r_rules, "Rules (PDF)", font_size=18, key='btn_rules_pdf')

    UI_RECTS['btn_rules_pdf'] = r_rules

    draw_button(screen, r_library, "Open Games Library", font_size=16, key='btn_open_library')

    UI_RECTS['btn_open_library'] = r_library



    y = y_row4 + btn_h + 12



    # Force Duel Now button (full width)  always visible until duel is seeded

    try:
        r_force = pygame.Rect(base_x, y, btn_w, btn_h)
        draw_button(screen, r_force, "Force Duel (Chess) Now", font_size=18, key='btn_force_duel')
        UI_RECTS['btn_force_duel'] = r_force
        y += btn_h + 8
    except Exception:
        UI_RECTS.pop('btn_force_duel', None)



    # Hold-at-Start toggle (full width)

    try:

        gs_local = globals().get('gs', None)

        hold_on = False if gs_local is None else bool(getattr(gs_local, 'hold_at_start', False))

    except Exception:

        hold_on = True

    ready_gap = 6
    half_w = int((btn_w - ready_gap) / 2)

    r_hold = pygame.Rect(base_x, y, half_w, btn_h)
    r_ready = pygame.Rect(r_hold.right + ready_gap, y, half_w, btn_h)

    draw_button(screen, r_hold, f"Hold at Start: {'On' if hold_on else 'Off'}", font_size=18, key='btn_holdstart')

    UI_RECTS['btn_holdstart'] = r_hold

    draw_button(screen, r_ready, "Ready to Play", active=waiting, font_size=18, key='btn_ready')

    if waiting:
        UI_RECTS['btn_ready'] = r_ready
    else:
        UI_RECTS.pop('btn_ready', None)

    y += btn_h + 8



    # New Game button (full width) with confirm-once behavior

    r_new = pygame.Rect(base_x, y, btn_w, btn_h)

    try:

        now_ticks = pygame.time.get_ticks()

        confirm_until = int(UI_STATE.get('confirm_newgame_until', 0) or 0)

        if confirm_until > 0 and now_ticks < confirm_until:

            new_label = "Confirm New Game"

        else:

            new_label = "New Game"

            # clear expired confirmation window

            if confirm_until > 0 and now_ticks >= confirm_until:

                UI_STATE['confirm_newgame_until'] = 0

    except Exception:

        new_label = "New Game"

    draw_button(screen, r_new, new_label, font_size=18, key='btn_newgame')

    UI_RECTS['btn_newgame'] = r_new

    y += btn_h + 12



    # Two-player info line (minimal)

    if two_stage:

        try:

            gs_local = globals().get('gs', None)

            locked = bool(gs_local and getattr(gs_local, 'chess_lock', False))

        except Exception:

            locked = False

    msg = "Duel mode pending..." if not locked else "Chess duel: Standard chess"

    # Hide 'Checks deferred' during teleport rules to avoid confusion

    if grace_active and not DUEL_TELEPORT_ON_TWO:

        msg += " - Checks deferred"

    surf = get_sidebar_font(16, True).render(msg, True, (230,230,180))

    screen.blit(surf, (x0 + 12, y))

    y += 22

    if locked:

        surf_lock = get_sidebar_font(15, True).render("Chess lock: ON", True, (180,220,255))

        screen.blit(surf_lock, (x0 + 12, y))

        y += 20

    pygame.draw.line(screen, (80,80,60), (x0+12, y), (x0+w-12, y), 1)

    y += 8



    # Material scoreboard line

    if show_material:

        parts = []

        for col in [PColor.WHITE, PColor.GREY, PColor.BLACK, PColor.PINK]:

            val = captured_points.get(col, 0) if captured_points else 0

            fg = PLAYER_COLORS[col] if col != PColor.BLACK else (255,255,255)

            tag = get_sidebar_font(16, False).render(f"{col.name[0]}:{val}", True, fg)

            screen.blit(tag, (x0 + 14 + len(parts)*54, y))

            parts.append(tag)

        y += 22

        pygame.draw.line(screen, (60,60,60), (x0+12, y), (x0+w-12, y), 1)

        y += 8



        # Per-seat AI/Human toggles

        toggle_w = 90

        toggle_h = 28

        gap = 8

        # layout 2x2 small toggles

        base_x = x0 + 12

        base_y = y

        colors = [PColor.WHITE, PColor.GREY, PColor.BLACK, PColor.PINK]

        for i, col in enumerate(colors):

            tx = base_x + (i%2) * (toggle_w + gap)

            ty = base_y + (i//2) * (toggle_h + gap)

            key = f'toggle_{col.name.lower()}'

            lbl = f"{col.name[:4]}: {'AI' if globals().get('gs') and getattr(globals().get('gs'),'player_is_ai',{}).get(col, False) else 'HUM'}"

            r = pygame.Rect(tx, ty, toggle_w, toggle_h)

            UI_RECTS[key] = r

            draw_button(screen, r, lbl, active=True, font_size=14, key=key)

        y += 2*(toggle_h + gap) + 8



    else:

        # Even when material line is hidden, still show per-seat toggles below header

        toggle_w = 90

        toggle_h = 28

        gap = 8

        base_x = x0 + 12

        base_y = y

        colors = [PColor.WHITE, PColor.GREY, PColor.BLACK, PColor.PINK]

        for i, col in enumerate(colors):

            tx = base_x + (i%2) * (toggle_w + gap)

            ty = base_y + (i//2) * (toggle_h + gap)

            key = f'toggle_{col.name.lower()}'

            lbl = f"{col.name[:4]}: {'AI' if globals().get('gs') and getattr(globals().get('gs'),'player_is_ai',{}).get(col, False) else 'HUM'}"

            r = pygame.Rect(tx, ty, toggle_w, toggle_h)

            UI_RECTS[key] = r

            draw_button(screen, r, lbl, active=True, font_size=14, key=key)

        y += 2*(toggle_h + gap) + 8



    # Move list area

    list_top = y

    list_bottom = LOGICAL_H - 10

    line_h = 20

    visible = max(0, (list_bottom - list_top)//line_h)

    start_idx = max(0, len(moves_list) - visible - scroll_offset)

    end_idx = max(0, len(moves_list) - scroll_offset)

    view = moves_list[start_idx:end_idx]

    # Also show algebraic notation for each move

    for i, text in enumerate(view):

        ty = list_top + i*line_h

        col = (235,235,235) if i % 2 == 0 else (200,200,200)

        # Try to parse move_no, color, piece, sr, sc, er, ec, captured, promoted from text

        # Fallback: just show the text

        try:

            # moves_list is built using format_move_entry, so we can reconstruct the info

            # Example: '12. WHITE: Q d1h5 x=Q'

            import re

            m = re.match(r"(\d+)\. (\w+): (\w) (\w+)[-](\w+)( x)?( =Q)?", text)

            if m:

                move_no = int(m.group(1))

                color = m.group(2)

                piece = m.group(3)

                # We don't have sr,sc,er,ec directly, so skip if not available

                # Just show the original text

                surf = get_sidebar_font(16).render(text, True, col)

                screen.blit(surf, (x0 + 12, ty))

            else:

                surf = get_sidebar_font(16).render(text, True, col)

                screen.blit(surf, (x0 + 12, ty))

        except Exception:

            surf = get_sidebar_font(16).render(text, True, col)

            screen.blit(surf, (x0 + 12, ty))

        # Now, if we have the move data, show algebraic notation below

        # Instead, let's store algebraic moves in parallel and show them

        if hasattr(screen, '_algebraic_moves'):

            if start_idx + i < len(screen._algebraic_moves):

                alg = screen._algebraic_moves[start_idx + i]

                surf2 = get_sidebar_font(14).render(alg, True, (180,180,255))

                screen.blit(surf2, (x0 + 32, ty+14))



# ====== RENDERING ======

def draw_resign_pill(screen, center_x, center_y, label, bg_rgba, fg_rgb):

    pill_font = pygame.font.SysFont("Arial", 18, bold=True)

    text_surf = pill_font.render(label, True, fg_rgb)

    w = text_surf.get_width() + 14

    h = text_surf.get_height() + 6

    max_w = 2*SQUARE - 24

    if w > max_w: w = max_w

    rect = pygame.Rect(0,0,w,h)

    rect.center = (center_x, center_y)

    bg = pygame.Surface((w,h), pygame.SRCALPHA)

    bg.fill(bg_rgba)

    pygame.draw.rect(screen, (220,220,220), rect, 1, border_radius=h//2)

    screen.blit(bg, rect)

    screen.blit(text_surf, text_surf.get_rect(center=rect.center))



def show_toast(msg: str, ms: int = 1500):

    try:

        UI_STATE['toast_text'] = str(msg)

        import pygame as _pg

        UI_STATE['toast_until'] = _pg.time.get_ticks() + int(ms)

    except Exception:

        UI_STATE['toast_text'] = str(msg)

        UI_STATE['toast_until'] = 0



def draw_board(screen, board: Board, selected, moves, font, turn_color, banner_text=None,

               resign_hover: Optional[PColor]=None, ui_state_text: Optional[str]=None,

               flash_color: Optional[PColor]=None, flash_on: bool = True):

    # squares

    for r in range(BOARD_SIZE):

        for c in range(BOARD_SIZE):

            rr, cc = _transform_rc_for_view(r, c)

            color = LIGHT if (r+c)%2==0 else DARK

            pygame.draw.rect(screen, color, (cc*SQUARE, rr*SQUARE, SQUARE, SQUARE))



    # chess 8x8 frame

    pygame.draw.rect(screen, (40,120,40), (CH_MIN*SQUARE, CH_MIN*SQUARE, 8*SQUARE, 8*SQUARE), 5)



    # Pulse the 8-8 border if any finalist king is still outside (two-player stage)

    try:

        gs_local = globals().get('gs')

        if gs_local and getattr(gs_local, 'two_stage_active', False):

            finals = (getattr(gs_local, 'final_a', None), getattr(gs_local, 'final_b', None))

            needs_entry = False

            for col in finals:

                if col is None:

                    continue

                kp = board.find_king(col)

                if kp and not in_chess_area(kp[0], kp[1]):

                    needs_entry = True

                    break

            if needs_entry:

                t = pygame.time.get_ticks() * 0.006  # pulse speed

                amp = (math.sin(t) + 1.0) * 0.5      # 0..1

                alpha = int(80 + 120 * amp)          # 80..200

                overlay = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)

                col = (255, 215, 0, alpha)  # golden pulse

                pygame.draw.rect(overlay, col, (CH_MIN*SQUARE, CH_MIN*SQUARE, 8*SQUARE, 8*SQUARE), 6)

                screen.blit(overlay, (0,0))

    except Exception:

        pass



    # corner fills (per-cell draw to stay correct under rotation)

    for pcol, (r0, c0) in CORNER_RECTS.items():

        fill_col = (*PLAYER_COLORS[pcol],)

        transformed_cells = []

        for dr in (0, 1):

            for dc in (0, 1):

                rr, cc = _transform_rc_for_view(r0 + dr, c0 + dc)

                transformed_cells.append((rr, cc))

                pygame.draw.rect(screen, fill_col, (cc * SQUARE, rr * SQUARE, SQUARE, SQUARE))

        # outline around the 2x2 block

        try:

            min_r = min(rr for rr, _ in transformed_cells)

            min_c = min(cc for _, cc in transformed_cells)

            pygame.draw.rect(screen, (40, 40, 40), (min_c * SQUARE, min_r * SQUARE, 2 * SQUARE, 2 * SQUARE), 2)

        except Exception:

            pass



    # selection + legal moves

    if selected:

        sr,sc = _transform_rc_for_view(*selected)

        pygame.draw.rect(screen, HL, (sc*SQUARE, sr*SQUARE, SQUARE, SQUARE), 3)

    for m in moves:

        try:

            # moves may be either (r,c) or (sr,sc,er,ec); prefer destination if available

            if isinstance(m, (list, tuple)) and len(m) >= 2:

                mr, mc = (m[-2], m[-1]) if len(m) >= 2 and len(m) != 2 else (m[0], m[1])

                mr, mc = _transform_rc_for_view(mr, mc)

            else:

                # Fallback: try to unpack as two values

                mr, mc = _transform_rc_for_view(*m)

        except Exception:

            # If anything unexpected, skip drawing this move

            continue

        pygame.draw.rect(screen, (100,200,100), (mc*SQUARE+8, mr*SQUARE+8, SQUARE-16, SQUARE-16), 2)



    # Hovered legal target emphasis (slight glow) if mouse over a legal destination

    try:

        hover_sq = UI_STATE.get('hover_square')

        if hover_sq is not None and moves:

            hr, hc = hover_sq

            # normalize moves to list of (r,c)

            ms = []

            for m in moves:

                if isinstance(m, (list, tuple)) and len(m) == 2:

                    ms.append(tuple(m))

                elif isinstance(m, (list, tuple)) and len(m) >= 4:

                    ms.append((m[-2], m[-1]))

            if (hr, hc) in ms:

                glow = pygame.Surface((SQUARE, SQUARE), pygame.SRCALPHA)

                glow.fill((100, 220, 140, 60))

                screen.blit(glow, (hc*SQUARE, hr*SQUARE))

                pygame.draw.rect(screen, (120,240,160), (hc*SQUARE+4, hr*SQUARE+4, SQUARE-8, SQUARE-8), 2)

    except Exception:

        pass



    # pieces (respect flashing elimination)

    for r in range(BOARD_SIZE):

        for c in range(BOARD_SIZE):

            p = board.get(r,c)

            if not p: continue

            if flash_color is not None and p.color == flash_color and not flash_on:

                continue  # hidden this frame for flashing

            rr, cc = _transform_rc_for_view(r, c)

            cx, cy = cc*SQUARE + SQUARE//2, rr*SQUARE + SQUARE//2

            override = getattr(p, 'tint_override', None)

            img = tinted_piece(p.color, p.kind, override)

            if img is not None:

                screen.blit(img, img.get_rect(center=(cx, cy)))

            else:

                base_color = (255, 255, 255) if p.color == PColor.WHITE else (40, 40, 40)
                outline_color = (20, 20, 20) if p.color == PColor.WHITE else (235, 235, 235)
                rect = pygame.Rect(0, 0, SQUARE - 8, SQUARE - 8)
                rect.center = (cx, cy)
                pygame.draw.rect(screen, base_color, rect, border_radius=6)
                pygame.draw.rect(screen, outline_color, rect, 2, border_radius=6)

                label_color = (20, 20, 20) if p.color == PColor.WHITE else (235, 235, 235)
                glyph = font.render(p.kind, True, label_color)
                screen.blit(glyph, glyph.get_rect(center=(cx, cy)))



    # Highlight kings that are currently in check (blinking red overlay)

    try:

        check_positions: List[Tuple[PColor, Tuple[int, int]]] = []

        for col in board.alive_colors():

            try:

                if king_in_check(board, col):

                    kp = board.find_king(col)

                    if kp:

                        check_positions.append((col, kp))

            except Exception:

                continue

        if check_positions:

            blink_on = (pygame.time.get_ticks() // 240) % 2 == 0

            if blink_on:

                for col, (kr, kc) in check_positions:

                    rr, cc = _transform_rc_for_view(kr, kc)

                    overlay = pygame.Surface((SQUARE, SQUARE), pygame.SRCALPHA)

                    overlay.fill((255, 60, 60, 140))

                    screen.blit(overlay, (cc * SQUARE, rr * SQUARE))

                    pygame.draw.rect(screen, (210, 40, 40), (cc * SQUARE, rr * SQUARE, SQUARE, SQUARE), 3)

    except Exception:

        pass



    # King locator overlay (optional): draw colored rings on all living kings

    try:

        if UI_STATE.get('king_locator', False):

            for col in board.alive_colors():

                kpos = board.find_king(col)

                if not kpos:

                    continue

                kr, kc = kpos

                rr, cc = _transform_rc_for_view(kr, kc)

                cx, cy = cc * SQUARE + SQUARE // 2, rr * SQUARE + SQUARE // 2

                ring = pygame.Surface((SQUARE, SQUARE), pygame.SRCALPHA)

                clr = (*PLAYER_COLORS[col], 220)

                pygame.draw.circle(ring, clr, (SQUARE//2, SQUARE//2), SQUARE//2 - 4, 4)

                screen.blit(ring, (cc * SQUARE, rr * SQUARE))

                # small label to indicate outside/inside

                try:

                    labf = get_sidebar_font(12, False)

                except Exception:

                    labf = None

                if labf:

                    txt = 'K' if in_chess_area(kr, kc) else 'K-'

                    lab = labf.render(txt, True, (20,20,20))

                    screen.blit(lab, (cc * SQUARE + 4, rr * SQUARE + 2))

    except Exception:

        pass



    # Gentle guidance arrows for kings outside 8-8 in two-player mode (disabled by default)

    try:

        if not UI_STATE.get('show_guidance_arrows', False):

            UI_STATE['kings_must_enter'] = False

        else:

            gs_local = globals().get('gs')

            kings_reminder = False

            if gs_local and getattr(gs_local, 'two_stage_active', False):

                finalists = (getattr(gs_local, 'final_a', None), getattr(gs_local, 'final_b', None))

                for col in finalists:

                    if col is None: continue

                    kpos = board.find_king(col)

                    if not kpos: continue

                    kr, kc = kpos

                    if not in_chess_area(kr, kc):

                        kings_reminder = True

                        # nearest entry square: clamp to edge

                        tr = min(max(kr, CH_MIN), CH_MAX)

                        tc = min(max(kc, CH_MIN), CH_MAX)

                        sx, sy = kc*SQUARE + SQUARE//2, kr*SQUARE + SQUARE//2

                        ex, ey = tc*SQUARE + SQUARE//2, tr*SQUARE + SQUARE//2

                        # draw a small arrow line with head

                        col_rgba = (*PLAYER_COLORS[col], 160)

                        try:

                            overlay = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)

                            pygame.draw.line(overlay, col_rgba, (sx, sy), (ex, ey), 3)

                            # arrow head

                            dx, dy = ex - sx, ey - sy

                            L = max(1, (dx*dx + dy*dy) ** 0.5)

                            ux, uy = dx / L, dy / L

                            hx, hy = ex - ux*10, ey - uy*10

                            pygame.draw.circle(overlay, col_rgba, (int(ex), int(ey)), 4)

                            pygame.draw.line(overlay, col_rgba, (int(hx - uy*6), int(hy + ux*6)), (ex, ey), 3)

                            pygame.draw.line(overlay, col_rgba, (int(hx + uy*6), int(hy - ux*6)), (ex, ey), 3)

                            screen.blit(overlay, (0,0))

                        except Exception:

                            pass

            UI_STATE['kings_must_enter'] = kings_reminder

    except Exception:

        pass



    # Draw ghost/dragging piece if active (global drag state)

    try:

        gd = globals()

        if gd.get('dragging') and gd.get('drag_start') and gd.get('drag_mouse_pos'):

            ds = gd.get('drag_start')

            dr, dc = ds

            gp = board.get(dr, dc)

            if gp:

                gx, gy = gd.get('drag_mouse_pos')

                override = getattr(gp, 'tint_override', None)

                gimg = tinted_piece(gp.color, gp.kind, override)

                if gimg is not None:

                    # create translucent copy

                    ghost = gimg.copy()

                    try:

                        ghost.set_alpha(160)

                    except Exception:

                        # fallback: create surface with alpha

                        pass

                    screen.blit(ghost, ghost.get_rect(center=(gx, gy)))

    except Exception:

        pass



    # resign pills inside each corner (computed dynamically for current view)

    for pcol, (r0, c0) in CORNER_RECTS.items():

        # Compute transformed bounding rect of the 2x2 corner cells

        cells = [_transform_rc_for_view(r0 + dr, c0 + dc) for dr in (0, 1) for dc in (0, 1)]

        min_r = min(rr for rr, _ in cells)

        min_c = min(cc for _, cc in cells)

        rect = pygame.Rect(min_c * SQUARE, min_r * SQUARE, 2 * SQUARE, 2 * SQUARE)

        # Store a slightly inset rect for hit-testing in UI_RECTS so clicks follow rotation

        try:

            hit_rect = rect.inflate(-16, -16)

            UI_RECTS[f"resign_{pcol.name.lower()}"] = hit_rect

        except Exception:

            pass

        cx, cy = rect.centerx, rect.centery

        if pcol == PColor.BLACK:   bg, fg = (0,0,0,210), (255,255,255)

        elif pcol == PColor.WHITE: bg, fg = (255,255,255,210), (0,0,0)

        elif pcol == PColor.GREY:  bg, fg = (160,160,160,210), (0,0,0)

        else:                      bg, fg = (255,105,180,210), (0,0,0)

        draw_resign_pill(screen, cx, cy, "RESIGN", bg, fg)



    # status bar

    bar = pygame.Rect(0, BOARD_SIZE*SQUARE, LOGICAL_W, 44)

    pygame.draw.rect(screen, BANNER_OK, bar)

    status_font = pygame.font.SysFont("Arial", 20, bold=True)

    left_text = f"Turn: {turn_color.name}"

    if banner_text:   left_text += f" | {banner_text}"

    if ui_state_text: left_text += f" | {ui_state_text}"

    # Human-visible prompt: King must enter when in two-player and any finalist king is outside 8-8

    try:

        gs_local = globals().get('gs')

        if gs_local and getattr(gs_local, 'two_stage_active', False):

            finals = (getattr(gs_local, 'final_a', None), getattr(gs_local, 'final_b', None))

            needs_entry = []

            for col in finals:

                if col is None:

                    continue

                kp = board.find_king(col)

                if kp and not in_chess_area(kp[0], kp[1]):

                    needs_entry.append(col.name)

            if needs_entry:

                who = ','.join(needs_entry)

                left_text += f" | King must enter: {who}"

    except Exception:

        pass

    txt_color = PLAYER_COLORS[turn_color] if turn_color != PColor.BLACK else (255,255,255)

    txt = status_font.render(left_text, True, txt_color)

    screen.blit(txt, (10, BOARD_SIZE*SQUARE + 8))



    # Ephemeral toast: centered near the top of the board area

    try:

        tmsg = UI_STATE.get('toast_text')

        tuntil = int(UI_STATE.get('toast_until', 0) or 0)

        import pygame as _pg

        now = _pg.time.get_ticks()

        if tmsg and (tuntil == 0 or now < tuntil):

            pad = 10

            tf = get_sidebar_font(18, True)

            ts = tf.render(str(tmsg), True, (255,255,255))

            tw, th = ts.get_width(), ts.get_height()

            cx = LOGICAL_W // 2

            cy = 18 + th // 2

            bg = _pg.Surface((tw + pad*2, th + pad*2), _pg.SRCALPHA)

            bg.fill((0,0,0,170))

            bg_rect = bg.get_rect(center=(cx, cy))

            screen.blit(bg, bg_rect)

            screen.blit(ts, ts.get_rect(center=(cx, cy)))

        elif tmsg and now >= tuntil:

            UI_STATE['toast_text'] = None

            UI_STATE['toast_until'] = 0

    except Exception:

        pass


    # Visual emphasis when chess lock engaged and everyone is inside: dim outside area, keep 8-8 bright

    gs_obj = globals().get('gs')

    try:

        if gs_obj and getattr(gs_obj, "chess_lock", False) and len(board.alive_colors()) > 1:

            # Only dim outside when both finalist kings are inside 8-8

            finals = (getattr(gs_obj, 'final_a', None), getattr(gs_obj, 'final_b', None))

            def _king_inside(col):

                if col is None:

                    return False

                kp = board.find_king(col)

                return bool(kp) and in_chess_area(kp[0], kp[1])

            both_inside = _king_inside(finals[0]) and _king_inside(finals[1])

            if both_inside:

                # Create a semi-transparent veil and cut a fully transparent hole over the 8-8

                dim = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)

                dim.fill((0,0,0,140))

                # Make the center 8-8 area fully transparent on the dim surface

                dim.fill((0,0,0,0), rect=(CH_MIN*SQUARE, CH_MIN*SQUARE, 8*SQUARE, 8*SQUARE))

                # Blit with normal alpha so the 8-8 stays bright and visible

                screen.blit(dim, (0,0))

    except Exception:

        pass



    # AI debug HUD overlay (top-right)

    try:

        if globals().get('AI_DEBUG_HUD', False):

            hud_font = pygame.font.SysFont("Consolas", 18)

            lines = ["AI HUD"]

            # current target for 3-player stage

            try:

                if not getattr(globals().get('gs'), 'two_stage_active', False):

                    me = turn_color

                    tgt = _alive_next_color(board, me)

                    if tgt:

                        lines.append(f"left-target: {tgt.name}")

            except Exception:

                pass

            # last AI notes

            try:

                notes = globals().get('ai_debug_text', []) or []

                for ln in notes[:6]:

                    lines.append(str(ln))

            except Exception:

                pass

            if len(lines) > 1:

                pad = 8

                tw = 0; th = 0; line_surfs = []

                for i, t in enumerate(lines):

                    srf = hud_font.render(t, True, (20,20,20) if i==0 else (34,34,34))

                    line_surfs.append(srf)

                    tw = max(tw, srf.get_width())

                    th += srf.get_height() + (4 if i>0 else 2)

                bx = LOGICAL_W - (tw + pad*2) - 12

                by = 12

                panel = pygame.Surface((tw + pad*2, th + pad*2), pygame.SRCALPHA)

                pygame.draw.rect(panel, (245,245,245,220), panel.get_rect(), border_radius=8)

                y = pad

                for i, srf in enumerate(line_surfs):

                    panel.blit(srf, (pad, y))

                    y += srf.get_height() + (4 if i>0 else 2)

                screen.blit(panel, (bx, by))

    except Exception:

        pass

    draw_library_overlay(screen)


def draw_library_overlay(screen) -> None:

    """Render an in-game overlay listing saved games when requested."""

    overlay = UI_STATE.get('library_overlay')

    import pygame as _pg


    if not overlay:

        for key in list(UI_RECTS.keys()):

            if key.startswith('library_entry_') or key.startswith('library_overlay_'):

                UI_RECTS.pop(key, None)

        UI_STATE.pop('library_overlay_rect', None)

        UI_STATE.pop('library_overlay_max_scroll', None)

        UI_STATE.pop('library_overlay_scroll', None)

        UI_STATE.pop('library_overlay_last_drawn', None)

        return


    entries = overlay.get('entries') or []

    debug_id = overlay.get('generated')
    if UI_STATE.get('library_overlay_last_drawn') != debug_id:
        try:
            print(f"[LIBRARY] drawing overlay frame with {len(entries)} entries")
        except Exception:
            pass
        UI_STATE['library_overlay_last_drawn'] = debug_id

    screen_w, screen_h = screen.get_size()
    sidebar_w = max(0, screen_w - LOGICAL_W)
    margin = 12

    if sidebar_w > (margin * 2) + 220:
        usable_sidebar = sidebar_w - margin * 2
        width = max(260, min(520, usable_sidebar))
        offset = (usable_sidebar - width) // 2
        x = LOGICAL_W + margin + max(0, offset)
    else:
        width = min(520, LOGICAL_W - 60)
        x = max(20, (LOGICAL_W - width) // 2)

    height = min(420, max(280, screen_h - margin * 2))
    if height > screen_h - margin * 2:
        height = max(240, screen_h - margin * 2)
    y = margin

    panel_rect = _pg.Rect(x, y, width, height)

    UI_STATE['library_overlay_rect'] = panel_rect


    surface = _pg.Surface((width, height), _pg.SRCALPHA)

    surface.fill((12, 12, 12, 238))


    for key in list(UI_RECTS.keys()):

        if key.startswith('library_entry_') or key.startswith('library_overlay_'):

            UI_RECTS.pop(key, None)


    title_font = get_sidebar_font(20, True)

    body_font = get_sidebar_font(16)

    small_font = get_sidebar_font(14)


    surface.blit(title_font.render("Saved Games Library", True, (245, 245, 245)), (20, 16))

    folder = overlay.get('folder', '')

    surface.blit(small_font.render(folder, True, (180, 180, 180)), (20, 40))


    close_rect = _pg.Rect(width - 36, 16, 20, 20)

    _pg.draw.rect(surface, (200, 80, 80), close_rect, border_radius=4)

    surface.blit(body_font.render("X", True, (20, 20, 20)), close_rect.move(4, -2))

    UI_RECTS['library_overlay_close'] = _pg.Rect(panel_rect.x + close_rect.x,

                                                 panel_rect.y + close_rect.y,

                                                 close_rect.width,

                                                 close_rect.height)


    header_y = 70

    surface.blit(small_font.render("Click a row to open that saved game.", True, (200, 200, 200)), (20, header_y))


    list_top = header_y + 24

    row_height = 26

    visible_rows = max(4, (height - list_top - 60) // row_height)


    scroll = int(UI_STATE.get('library_overlay_scroll', 0) or 0)

    max_scroll = max(0, len(entries) - visible_rows)

    scroll = max(0, min(max_scroll, scroll))

    UI_STATE['library_overlay_scroll'] = scroll

    UI_STATE['library_overlay_max_scroll'] = max_scroll


    mouse_pos = _pg.mouse.get_pos()


    columns = [

        (20, "File"),

        (int(width * 0.55), "Moves"),

        (int(width * 0.70), "Result"),

        (int(width * 0.83), "Recorded"),

    ]


    for col_x, label in columns:

        surface.blit(small_font.render(label, True, (160, 200, 220)), (col_x, list_top))

    _pg.draw.line(surface, (60, 60, 60), (16, list_top + 18), (width - 16, list_top + 18))


    start_index = scroll

    visible = entries[start_index:start_index + visible_rows]


    y_cursor = list_top + 26

    for idx, entry in enumerate(visible):

        abs_index = start_index + idx

        row_rect = _pg.Rect(16, y_cursor - 4, width - 32, row_height)

        global_rect = _pg.Rect(panel_rect.x + row_rect.x, panel_rect.y + row_rect.y, row_rect.width, row_rect.height)

        hovered = global_rect.collidepoint(mouse_pos)

        _pg.draw.rect(surface, (40, 40, 60, 140) if hovered else (22, 22, 30, 120), row_rect, border_radius=4)


        file_text = body_font.render(str(entry.get('file', '')), True, (240, 240, 240))

        surface.blit(file_text, (columns[0][0], y_cursor))


        moves_val = entry.get('moves')

        surface.blit(body_font.render(str(moves_val) if moves_val not in (None, '') else "-", True, (210, 210, 210)),

                     (columns[1][0], y_cursor))


        winner = entry.get('winner') or "-"

        surface.blit(body_font.render(str(winner), True, (210, 210, 210)), (columns[2][0], y_cursor))


        ts_disp = entry.get('display_ts') or "-"

        surface.blit(body_font.render(str(ts_disp), True, (200, 200, 200)), (columns[3][0], y_cursor))


        UI_RECTS[f'library_entry_{abs_index}'] = global_rect

        y_cursor += row_height


    if not entries:

        surface.blit(body_font.render("No saved games yet.", True, (210, 210, 210)),

                     (20, list_top + 30))


    if max_scroll > 0:

        pager_text = small_font.render(f"Showing {start_index + 1}-{min(start_index + visible_rows, len(entries))} "

                                       f"of {len(entries)}  (scroll to see more)", True, (180, 180, 180))

        surface.blit(pager_text, (20, height - 44))

    else:

        surface.blit(small_font.render(f"Total saved games: {len(entries)}", True, (180, 180, 180)),

                     (20, height - 44))


    surface.blit(small_font.render("Close or press the Library button again to hide.", True, (170, 170, 170)), (20, height - 24))


    screen.blit(surface, panel_rect)



# ====== ASSET CHECK ======

def verify_assets():

    msgs = [f"ASSET_DIR = {ASSET_DIR}", f"Folder exists: {os.path.isdir(ASSET_DIR)}"]

    missing = []

    if os.path.isdir(ASSET_DIR):

        try:

            listing = sorted(os.listdir(ASSET_DIR))

            msgs.append("Folder contents: " + (", ".join(listing) if listing else "(empty)"))

            expected = ["white_K.png","white_Q.png","white_R.png","white_B.png","white_N.png","white_P.png"]

            for name in expected:

                if name not in listing: missing.append(name)

        except Exception as e:

            msgs.append(f"(Error listing folder: {e})")

    summary = f"Found {6-len(missing)}/6 piece images."

    if missing: summary += " Missing: " + ", ".join(missing)

    msgs.append(summary)

    return "\n".join(msgs), missing



# ====== Move list & material tracking ======

class MaterialTracker:

    def __init__(self):

        self.captured_points = {PColor.WHITE:0, PColor.GREY:0, PColor.BLACK:0, PColor.PINK:0}

    def on_capture(self, victim: Piece):

        if victim: self.captured_points[victim.color] += PIECE_VALUES.get(victim.kind, 0)

    def should_eliminate(self, board: Board, threshold: int = 18):

        alive = board.alive_colors()

        if len(alive) <= 2: return None

        thr = max(0, int(threshold))

        if thr <= 0:

            return None

        for col, pts in self.captured_points.items():

            if col in alive and pts >= thr:

                return col

        return None



def format_move_entry(move_no: int, color: PColor, piece_letter: str, sr, sc, er, ec, captured: Optional[Piece], promoted: bool):

    """Render a move line in simple coordinate style by default (e.g., a2-a3).

    We keep capture and promotion markers to retain key info.

    """

    cap = " x" if captured else ""

    promo = " =Q" if promoted else ""

    gs_local = globals().get('gs', None)

    duel_mode = bool(gs_local and getattr(gs_local, 'chess_lock', False))

    label_fn = duel_to_chess_label if duel_mode else rc_to_label

    display_name = color.name

    if duel_mode:

        if color == PColor.WHITE:

            display_name = getattr(gs_local, 'duel_white_name', 'White')

        elif color == PColor.BLACK:

            display_name = getattr(gs_local, 'duel_black_name', 'Black')

    return f"{move_no}. {display_name}: {label_fn(sr,sc)}-{label_fn(er,ec)}{cap}{promo}"



def format_move_algebraic(move_no: int, color: PColor, piece_letter: str, sr, sc, er, ec, captured: Optional['Piece'], promoted: bool):

    """Compatibility wrapper: we format moves like format_move_entry.

    This function exists because several call sites still use the older name.

    """

    return format_move_entry(move_no, color, piece_letter, sr, sc, er, ec, captured, promoted)



# ====== GAME STATE ======

class GameState:

    turn_counter = 0

    def __init__(self):

        self.post_move_delay_until = 0

        self.freeze_advance = False

        # When two-player finals first activate, we pause progression once for inspection

        self.two_stage_pause = False

        self.elim_flash_color: Optional[PColor] = None

        self.elim_flash_until = 0

        self.elim_flash_next_toggle = 0

        self.elim_flash_on = True

        self._last_flash_color = None

        self._pending_cleanup = False
        self._elim_skip_cleanup: Set[PColor] = set()

        # Pre-game options

        self.hold_at_start = False

        # Hold is off by default; game begins immediately unless toggled

        self.waiting_ready = False

        # Two-player stage

        self.two_stage_active = False

        self.final_a: Optional[PColor] = None

        self.final_b: Optional[PColor] = None

        self.entered = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}

        self.reduced_applied = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}

        self.grace_active = False

        self.grace_turns_remaining = 0

        self.chess_lock = False

        # Auto-elimination score threshold: 0=Off, 18 or 30 supported

        self.auto_elim_threshold = 18

        # Track number of half-moves since start to implement "first round" rules

        self.half_moves = 0

        # Per-color corner immunity flag (True while king sits in sanctuary with >=3 queens alive)

        self.corner_immune = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}

        # Track per-colour guardian promotions and evacuation requirements

        self.corner_promoted = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}

        self.corner_evict_pending = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}

        self.corner_in_corner = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}

        # Pawn movement direction per color: 1 for forward increasing row/col, -1 for decreasing

        # For WHITE/BLACK we use row-based direction; for GREY/PINK use col-based direction

        self.pawn_dir = {

            PColor.WHITE: -1,  # default: WHITE moves up (decreasing row)

            PColor.BLACK: 1,   # BLACK moves down

            PColor.GREY: 1,    # GREY moves right (increasing col)

            PColor.PINK: -1,   # PINK moves left

        }

        self.duel_white_origin: PColor = PColor.WHITE

        self.duel_black_origin: PColor = PColor.BLACK

        self.duel_white_name: str = "White"

        self.duel_black_name: str = "Black"

        self._pending_duel_move_log: Optional[str] = None

        self._reset_moves_for_duel: bool = False

        # Recent move history (tuples of (color, sr, sc, er, ec))  used by AI to avoid ping-pong

        self.recent_moves = deque(maxlen=64)

        # Position repetition counts: map from position_key -> int

        self.pos_counts: Dict[int, int] = {}

        # per-color human/AI toggles (default: use choose_ai_players())

        self.player_is_ai: Dict[PColor, bool] = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}

        # Per-color flag to mark that we already applied the pre-AI delay for this turn

        self.ai_delay_applied: Dict[PColor, bool] = {PColor.WHITE: False, PColor.GREY: False, PColor.BLACK: False, PColor.PINK: False}

        # Draw state flags

        self._draw_by_repetition = False

        # Last winner for post-game UI (None means draw)

        self.last_winner = None

        # Temporary: boost White strength in duel to encourage faster mate

        self.white_duel_boost = True



    def _position_key(self, board: 'Board') -> int:

        """Compute a simple stable hash for the current board position ignoring move clocks.

        We use a deterministic hashlib.sha1 over piece placements and turn order.

        """

        s = []

        for r in range(BOARD_SIZE):

            for c in range(BOARD_SIZE):

                p = board.get(r, c)

                if p:

                    s.append(f"{r},{c},{p.kind},{p.color.value},{int(p.has_moved)};")

        # include two-stage flags and pawn_dir to reflect rule-affecting state

        s.append(f"two_stage:{int(self.two_stage_active)};")

        s.append(f"pawn_dir:{','.join(str(self.pawn_dir[col]) for col in TURN_ORDER)};")

        # turn counter parity influences repetition (whose move it is)

        s.append(f"turnpar:{GameState.turn_counter % 2};")

        key = hashlib.sha1(''.join(s).encode('utf-8')).hexdigest()

        # return an integer for compact storage

        return int(key[:16], 16)



    def start_move_delay(self, ms: int):

        now = pygame.time.get_ticks()

        self.post_move_delay_until = max(self.post_move_delay_until, now + ms)

        self.freeze_advance = True



    def start_elim_flash(self, color: PColor, ms_total: int):

        now = pygame.time.get_ticks()

        self.elim_flash_color = color

        self.elim_flash_until = now + ms_total

        self.elim_flash_next_toggle = now + ELIM_FLASH_RATE_MS

        self.elim_flash_on = False

        self.freeze_advance = True

        self._last_flash_color = color



    def update_timers(self):

        now = pygame.time.get_ticks()

        if self.elim_flash_color is not None:

            if now >= self.elim_flash_next_toggle:

                self.elim_flash_on = not self.elim_flash_on

                self.elim_flash_next_toggle = now + ELIM_FLASH_RATE_MS

            if now >= self.elim_flash_until:

                self.elim_flash_color = None

                self.elim_flash_on = True

                self._pending_cleanup = True

        if self.post_move_delay_until and now >= self.post_move_delay_until:

            self.post_move_delay_until = 0

        self.freeze_advance = bool(self.elim_flash_color is not None or self.post_move_delay_until)



# ====== MAIN ======

def main():

    # Initialize pygame modules before using display or fonts

    try:

        pygame.init()

        pygame.font.init()

    except Exception:

        pass

    # === Pure snapshot helpers (from archive) ===

    def dump_board(b: Board):

        items = []

        for rr in range(BOARD_SIZE):

            for cc in range(BOARD_SIZE):

                p = b.get(rr, cc)

                if p:

                    items.append((rr, cc, p.kind, p.color.value, p.has_moved))

        return items



    def load_board(items):

        nb = Board()

        for rr in range(BOARD_SIZE):

            for cc in range(BOARD_SIZE):

                nb.set(rr, cc, None)

        for (rr, cc, kind, colv, moved) in items:

            q = Piece(kind, PColor(colv))

            q.has_moved = bool(moved)

            nb.set(rr, cc, q)

        return nb



    def gs_to_dict(g: GameState):

        return {

            "post_move_delay_until": 0,

            "freeze_advance": False,

            "elim_flash_color": (g.elim_flash_color.value if g.elim_flash_color is not None else None),

            "elim_flash_until": 0,

            "elim_flash_next_toggle": 0,

            "elim_flash_on": True,

            "_last_flash_color": (g._last_flash_color.value if g._last_flash_color is not None else None),

            "_pending_cleanup": g._pending_cleanup,

            "two_stage_active": g.two_stage_active,

            "final_a": (g.final_a.value if g.final_a is not None else None),

            "final_b": (g.final_b.value if g.final_b is not None else None),

            "entered": {k.value: v for k, v in g.entered.items()},

            "reduced_applied": {k.value: v for k, v in g.reduced_applied.items()},

            "grace_active": g.grace_active,

            "grace_turns_remaining": g.grace_turns_remaining,

            "chess_lock": g.chess_lock,

            "hold_at_start": getattr(g, 'hold_at_start', False),

            "waiting_ready": getattr(g, 'waiting_ready', False),

            "auto_elim_threshold": int(getattr(g, 'auto_elim_threshold', 18)),

            "_draw_by_repetition": bool(getattr(g, '_draw_by_repetition', False)),

        }



    def gs_from_dict(d):

        g = GameState()

        g.post_move_delay_until = 0

        g.freeze_advance = False

        g.elim_flash_color = (PColor(d["elim_flash_color"]) if d["elim_flash_color"] is not None else None)

        g.elim_flash_until = 0

        g.elim_flash_next_toggle = 0

        g.elim_flash_on = True

        g._last_flash_color = (PColor(d["_last_flash_color"]) if d["_last_flash_color"] is not None else None)

        g._pending_cleanup = d["_pending_cleanup"]

        g.two_stage_active = d["two_stage_active"]

        g.final_a = (PColor(d["final_a"]) if d["final_a"] is not None else None)

        g.final_b = (PColor(d["final_b"]) if d["final_b"] is not None else None)

        g.entered = {PColor(int(k)): bool(v) for k, v in d["entered"].items()}

        g.reduced_applied = {PColor(int(k)): bool(v) for k, v in d["reduced_applied"].items()}

        g.grace_active = d["grace_active"]

        g.grace_turns_remaining = d["grace_turns_remaining"]

        g.chess_lock = d["chess_lock"]

        g.hold_at_start = bool(d.get("hold_at_start", False))

        g.waiting_ready = bool(d.get("waiting_ready", False))

        g.auto_elim_threshold = int(d.get("auto_elim_threshold", 18))

        try:

            g._draw_by_repetition = bool(d.get("_draw_by_repetition", False))

        except Exception:

            g._draw_by_repetition = False

        return g



    def mat_to_dict(m: MaterialTracker):

        return {k.value: v for k, v in m.captured_points.items()}



    def mat_from_dict(dct):

        m = MaterialTracker()

        for col in [PColor.WHITE, PColor.GREY, PColor.BLACK, PColor.PINK]:

            m.captured_points[col] = int(dct.get(col.value, 0))

        return m



    def make_snapshot():

        return {

            "board": dump_board(board),

            "turn_i": turn_i,

            "forced_turn": (forced_turn.value if forced_turn is not None else None),

            "gs": gs_to_dict(gs),

            "player_is_ai": {k.value: int(v) for k,v in gs.player_is_ai.items()},

            "mat": mat_to_dict(mat),

            "moves_list": list(moves_list),

            "turn_counter": GameState.turn_counter,

        }



    def restore_snapshot(snap):

        # Restore all game state in place (do not reassign board)

        for rr in range(BOARD_SIZE):

            for cc in range(BOARD_SIZE):

                board.set(rr, cc, None)

        for (rr, cc, kind, colv, moved) in snap["board"]:

            q = Piece(kind, PColor(colv))

            q.has_moved = bool(moved)

            board.set(rr, cc, q)

        # Update turn and forced_turn

        nonlocal turn_i, forced_turn

        turn_i = snap["turn_i"]

        forced_turn = (PColor(snap["forced_turn"]) if snap["forced_turn"] is not None else None)

        # Update gs and mat in place

        gsd = gs_from_dict(snap["gs"])

        # Copy over only attributes that exist on the current GameState to avoid

        # AttributeError when new fields were added since the snapshot was taken.

        for attr in vars(gs):

            if hasattr(gsd, attr):

                setattr(gs, attr, getattr(gsd, attr))

        # Initialize any newly introduced attributes to safe defaults if absent in snapshot

        for attr, default in (

            ("_finalists_prep_started", False),

            ("_flash_until", None),

            ("_teleport_after", 0),

            ("_duel_cleared_board", False),

            ("_duel_delay_until", 0),

            ("_duel_started", False),

            ("_duel_banner", ""),

            ("_tp_consolidated_done", False),

            ("freeze_advance", False),

            ("two_stage_pause", False),

        ):

            if not hasattr(gs, attr):

                try:

                    setattr(gs, attr, default)

                except Exception:

                    pass

        # restore player_is_ai map

        if 'player_is_ai' in snap:

            for k,v in snap['player_is_ai'].items():

                gs.player_is_ai[PColor(int(k))] = bool(int(v))

        # reflect into AI_PLAYERS global

        global AI_PLAYERS

        AI_PLAYERS = {c for c, flag in gs.player_is_ai.items() if flag}

        md = mat_from_dict(snap["mat"])

        for attr in vars(mat):

            setattr(mat, attr, getattr(md, attr))

        moves_list[:] = snap["moves_list"]

        GameState.turn_counter = snap["turn_counter"]

    # NOTE: DO NOT draw the board or sidebar here (before the main loop)!

    # Drawing here (e.g., screen.fill, draw_board, draw_sidebar, pygame.display.flip)

    # will cause the sidebar to double up briefly after resizing or maximizing.

    # Only draw inside the main game loop, after all events are handled.

    global AI_PLAYERS, AI_STRENGTH, gs



    # Default: no automated AI players so human clicks work by default

    AI_PLAYERS = set()



    year = datetime.datetime.now().year

    caption = f'Copyright 2016-{year} Edwin John Wilhelm "Bishops, The Game" v1.6.5'

    screen = pick_initial_window()

    pygame.display.set_caption(caption)

    # Fallback chain: try Arial Unicode MS, then Arial, then default

    try:

        font = pygame.font.SysFont("Arial Unicode MS", 42)

    except Exception:

        try:

            font = pygame.font.SysFont("Arial", 42)

        except Exception:

            font = pygame.font.Font(None, 42)



    try:

        banner = f"Build: {__FILE_VERSION__}"

    except NameError:

        banner = "Build: (no version marker)"



    verify_text, _ = verify_assets()

    print(verify_text)

    # Always clear any headless plan before entering the interactive loop
    try:
        globals()['HEADLESS_SCRIPT'] = None
        globals()['HEADLESS_RESULTS'] = None
        globals()['HEADLESS_ENABLED'] = False
    except Exception:
        pass

    # Load persisted user settings

    try:

        _settings = load_user_settings()

    except Exception:

        _settings = {"hold_at_start": False}



    def _advance_turn_index(idx: int) -> int:
        alive = set(board.alive_colors())
        if not alive:
            return idx
        span = len(TURN_ORDER)
        for _ in range(span):
            col = TURN_ORDER[idx % span]
            if col in alive:
                return idx % span
            idx = (idx + 1) % span
        return idx % span

    board = Board()

    selected = None

    moves = []

    # Drag-and-drop state for mouse control

    dragging = False

    drag_start = None  # (r,c)

    drag_mouse_pos = (0, 0)

    drag_legal_targets = []



    turn_i = 0

    forced_turn: Optional[PColor] = None

    ui_state_text = None



    # Deprecated static resign rects; draw_board will populate UI_RECTS['resign_*'] per frame

    resign_rects = {}



    history = []

    future = []

    replay_mode = False

    gs = GameState()

    # Apply loaded settings to gs

    try:

        gs.hold_at_start = bool(_settings.get("hold_at_start", False))

        if gs.hold_at_start:

            gs.hold_at_start = False

        gs.waiting_ready = False

        # Restore auto-elim threshold if present

        try:

            gs.auto_elim_threshold = int(_settings.get("auto_elim_threshold", 18))

        except Exception:

            gs.auto_elim_threshold = 18

    except Exception:

        pass

    # Default pre-AI delay in ms to allow human to take control (10 seconds)

    gs_pre_ai_delay_ms = 500

    # initialize player_is_ai defaults from choose_ai_players()

    defaults = choose_ai_players()

    for col in TURN_ORDER:

        gs.player_is_ai[col] = (col in defaults)

    # reflect into AI_PLAYERS global

    AI_PLAYERS = {c for c, flag in gs.player_is_ai.items() if flag}



    moves_list: List[str] = []

    sidebar_scroll = 0

    show_material = True

    auto_elim_enabled = True

    mat = MaterialTracker()





    running = True

    clock = pygame.time.Clock()

    replay_mode = False  # Always start in normal mode

    # Require an explicit Ready press before the first move so the board stays idle
    try:
        gs.waiting_ready = True
        gs.freeze_advance = True
        banner = "Press Ready to begin; toggle seats to AI if desired."
    except Exception:
        gs.waiting_ready = True
        gs.freeze_advance = True



    # One-time draw guard: draw the initial frame at the top of the loop (not before)

    first_frame_drawn = False

    # Resize debounce: coalesce rapid VIDEORESIZE events

    resize_pending = False

    resize_last_event_ms = 0

    RESIZE_DEBOUNCE_MS = 200



    # Optional: force duel at startup via CLI (testing aid)

    try:

        if '--force-duel' in sys.argv[1:]:

            # Bypass detection and seed duel immediately

            if _force_duel_now(board, gs) and getattr(gs, '_duel_started', False):
                _prepare_forced_duel_reset()

            print('[CLI] --force-duel requested')

    except Exception:

        pass



    # Avoid any pre-loop draw; first draw will occur inside the main loop to prevent double-render artifacts on sidebar



    def do_copy_moves():

        text = "\n".join(moves_list) if moves_list else "(no moves yet)"

        try:

            if not pygame.scrap.get_init():

                pygame.scrap.init()

            pygame.scrap.put(pygame.SCRAP_TEXT, text.encode('utf-8'))

            return True, "Copied moves to clipboard."

        except Exception:

            try:

                import pyperclip

                pyperclip.copy(text)

                return True, "Copied moves to clipboard."

            except Exception:

                return False, "Clipboard not available."



    def do_export_moves():

        fname = os.path.join(SCRIPT_DIR, "bishops_moves.txt")

        try:

            with open(fname, "w", encoding="utf-8") as f:

                f.write("\n".join(moves_list))

            return True, f"Saved {os.path.basename(fname)}"

        except Exception as e:

            return False, f"Save failed: {e}"



    def _prepare_forced_duel_reset():
        nonlocal turn_i, forced_turn, selected, moves, dragging, drag_start, drag_legal_targets
        nonlocal history, future, replay_mode, sidebar_scroll, game_over, auto_elim_enabled, mat, moves_list, show_material
        turn_i = TURN_ORDER.index(PColor.WHITE)
        turn_i = _advance_turn_index(turn_i)
        forced_turn = None
        selected = None
        moves = []
        dragging = False
        drag_start = None
        drag_legal_targets = []
        history.clear()
        future.clear()
        replay_mode = False
        sidebar_scroll = 0
        moves_list.clear()
        game_over = False
        auto_elim_enabled = False
        show_material = True
        mat = MaterialTracker()
        UI_STATE['view_seat'] = 'AUTO'


    def clockwise_from(color: PColor, candidates: List[PColor]) -> Optional[PColor]:

        if not candidates:

            return None

        idx = TURN_ORDER.index(color)

        for i in range(1, 5):

            nxt = TURN_ORDER[(idx + i) % 4]

            if nxt in candidates:

                return nxt

        return candidates[0]



    def ensure_two_stage_state():

        """

        Enter two-player stage as soon as there are effectively 2 colors:

        - exactly two kings alive, OR

        - two kings alive + one color currently flashing elimination (treated as gone).

        """

        alive_real = board.alive_colors()

        flashing = gs.elim_flash_color

        alive_effective = [c for c in alive_real if c != flashing]

        is_two = (len(alive_effective) == 2)

        if is_two and not gs.two_stage_active:

            gs.two_stage_active = True

            gs.final_a, gs.final_b = alive_effective[0], alive_effective[1]

            # Apply one-time migration cleanup and pairing adjustments

            try:

                perform_two_stage_migration(board, gs, [gs.final_a, gs.final_b])

            except Exception:

                pass

            # Mark entered if any piece already sits inside the 8-8

            for col in alive_effective:

                gs.entered[col] = any(

                    (board.get(r,c) and board.get(r,c).color == col and in_chess_area(r,c))

                    for r in range(BOARD_SIZE) for c in range(BOARD_SIZE)

                )

            # Duel-teleport rules: do not enable grace during prep; we'll teleport instead

            if DUEL_TELEPORT_ON_TWO:

                gs.grace_active = False

                gs.grace_turns_remaining = 0

            else:

                # Legacy behavior: enable grace only after BOTH have a piece inside 8-8

                if gs.entered[gs.final_a] and gs.entered[gs.final_b]:

                    gs.grace_active = True

                    gs.grace_turns_remaining = 2  # two plies: one non-checking move for each side



        elif not is_two and gs.two_stage_active:

            # Safety reset if state changes unexpectedly

            gs.two_stage_active = False

            gs.final_a = gs.final_b = None

            for k in gs.entered: gs.entered[k] = False

            for k in gs.reduced_applied: gs.reduced_applied[k] = False

            gs.grace_active = False

            gs.grace_turns_remaining = 0

            gs.chess_lock = False



    def two_stage_opponent(me: PColor) -> Optional[PColor]:

        if not gs.two_stage_active: return None

        return gs.final_b if me == gs.final_a else gs.final_a



    def grace_blocks_check_for(color: PColor):

        """Return a predicate move -> bool telling whether a move gives *intentional* check (to be avoided during grace)."""

        opp = two_stage_opponent(color)

        if opp is None:

            return lambda m, _: False

        def gives_check(m, opponent_color):

            if not gs.two_stage_active or not gs.grace_active:

                return False

            sr,sc,er,ec = m

            cap, ph, pk, eff = board_do_move(board, sr,sc,er,ec, simulate=True)

            chk = king_in_check(board, opponent_color)

            board_undo_move(board, sr,sc,er,ec, cap, ph, pk, eff)

            return chk

        return gives_check



    def apply_queen_reduction_if_needed(color: PColor):

        """On first entry to the 8-8 for this color during two-stage, reduce QB per rules."""

        if not gs.two_stage_active or gs.reduced_applied[color]:

            return None

        if not gs.entered[color]:

            return None

        q_locs = []

        for r in range(BOARD_SIZE):

            for c in range(BOARD_SIZE):

                p = board.get(r,c)

                if p and p.color == color and p.kind == 'Q':

                    q_locs.append((r,c))

        if len(q_locs) >= 3:

            q_locs.sort(key=lambda rc: abs(5.5-rc[0]) + abs(5.5-rc[1]), reverse=True)

            pick = q_locs[:2]

        elif len(q_locs) == 2:

            pick = q_locs

        else:

            pick = []

        for (r,c) in pick:

            p = board.get(r,c)

            if p and p.kind == 'Q':

                p.kind = 'B'

        if pick:

            gs.reduced_applied[color] = True

            return pick

        return None



    game_over = False

    # Debug fallback: force a visible, dependency-free checkerboard background each frame

    DEBUG_FORCE_VISIBLE = False

    # Optional debug mode: auto-select a clicked friendly piece even if it has no legal moves.

    # This helps debug selection/highlighting problems on systems where move-gen or filters

    # may be incorrectly rejecting moves. Set to True to enable.

    AUTO_SELECT_DEBUG = False

    # Reduce noisy heartbeat prints when False

    HEARTBEAT = False

    # Global verbose debug gate to silence diagnostic prints in normal play

    VERBOSE_DEBUG = False

    # Compact console move logs; when True, prints a single-line algebraic per move instead of tuple coords

    COMPACT_CONSOLE = True

    # AI HUD: show left-neighbor target and last AI reasoning overlay (toggle with F9)

    AI_DEBUG_HUD = False

    ai_debug_text = []  # last-frame details

    # Visual click indicator: milliseconds to show after a click

    CLICK_INDICATOR_MS = 400

    click_indicator = None  # tuple (mx, my, until_ms)

    # Subtle move pulse animation: dict with 'square': (r,c) and 'until' ms timestamp

    move_pulse = None



    HEADLESS_STATE_KEY = "_HEADLESS_STATE"



    def _headless_env():

        return {

            "UI_STATE": UI_STATE,

            "UI_RECTS": UI_RECTS,

            "gs": gs,

            "board": board,

            "moves_list": moves_list,

            "history": history,

            "future": future,

            "replay_mode": replay_mode,

            "show_material": show_material,

            "auto_elim_threshold": getattr(gs, 'auto_elim_threshold', None),

            "AI_STRENGTH": AI_STRENGTH,

            "game_over": game_over,

            "VERBOSE_DEBUG": VERBOSE_DEBUG,

            "ticks": pygame.time.get_ticks(),

            "sidebar_scroll": sidebar_scroll,

            "turn_counter": GameState.turn_counter,

            "active_color": (TURN_ORDER[turn_i] if forced_turn is None else forced_turn),

        }



    def _apply_headless_mutations(mutations):

        nonlocal show_material, game_over, replay_mode, ui_state_text, sidebar_scroll, VERBOSE_DEBUG

        global AI_PLAYERS

        if not mutations:

            return

        for key, value in mutations.items():

            if key.startswith('gs.'):

                setattr(gs, key[3:], value)

            elif key.startswith('UI_STATE.'):

                UI_STATE[key[9:]] = value

            elif key == 'show_material':

                show_material = bool(value)

            elif key == 'game_over':

                game_over = bool(value)

            elif key == 'replay_mode':

                replay_mode = bool(value)

            elif key == 'ui_state_text':

                ui_state_text = value

            elif key == 'sidebar_scroll':

                sidebar_scroll = int(value)

            elif key == 'moves_list':

                moves_list[:] = list(value)

            elif key == 'history':

                if value == 'clear':

                    history.clear()

                elif value == 'snapshot':

                    history.append(make_snapshot())

                elif isinstance(value, list):

                    history[:] = value

            elif key == 'future':

                if value == 'clear':

                    future.clear()

                elif value == 'snapshot':

                    future.append(make_snapshot())

                elif isinstance(value, list):

                    future[:] = value

            elif key == 'VERBOSE_DEBUG':

                VERBOSE_DEBUG = bool(value)

            elif key == 'gs.player_is_ai':

                if isinstance(value, dict):

                    for cname, flag in value.items():

                        col = cname if isinstance(cname, PColor) else PColor[str(cname).upper()]

                        gs.player_is_ai[col] = bool(flag)

                    global AI_PLAYERS

                    AI_PLAYERS = {c for c, flag in gs.player_is_ai.items() if flag}

            elif key == 'gs.waiting_ready':

                gs.waiting_ready = bool(value)

            elif key == 'gs.hold_at_start':

                gs.hold_at_start = bool(value)

            elif key == 'gs.last_winner':

                gs.last_winner = value

            elif key == 'moves_list_append':

                moves_list.append(value)



    def _square_center(r: int, c: int) -> Tuple[int, int]:

        """Return screen pixel center for canonical (r,c) considering current view."""

        vr, vc = _transform_rc_for_view(r, c)

        return (vc * SQUARE + SQUARE // 2, vr * SQUARE + SQUARE // 2)



    def _post_board_move(move: Tuple[int, int, int, int]) -> None:

        """Inject mouse events to execute a board move (sr,sc,er,ec)."""

        sr, sc, er, ec = move

        fx, fy = _square_center(sr, sc)

        tx, ty = _square_center(er, ec)

        for event_type, pos in (

            (pygame.MOUSEBUTTONDOWN, (fx, fy)),

            (pygame.MOUSEBUTTONUP, (fx, fy)),

            (pygame.MOUSEBUTTONDOWN, (tx, ty)),

            (pygame.MOUSEBUTTONUP, (tx, ty)),

        ):

            pygame.event.post(pygame.event.Event(event_type, {'pos': pos, 'button': 1}))



    def _find_first_legal_move() -> Optional[Tuple[int, int, int, int]]:

        """Locate a simple legal move for the current active color."""

        active_color = TURN_ORDER[turn_i] if forced_turn is None else forced_turn

        fallback: Optional[Tuple[int, int, int, int]] = None

        for rr in range(BOARD_SIZE):

            for cc in range(BOARD_SIZE):

                piece = board.get(rr, cc)

                if not piece or piece.color != active_color:

                    continue

                try:

                    moves_raw = legal_moves_for_piece(board, rr, cc, active_color)

                except Exception:

                    continue

                if not moves_raw:

                    continue

                for mv in moves_raw:

                    if isinstance(mv, (list, tuple)):

                        if len(mv) >= 4:

                            sr, sc, er, ec = mv[0], mv[1], mv[2], mv[3]

                        elif len(mv) == 2:

                            sr, sc, er, ec = rr, cc, mv[0], mv[1]

                        else:

                            continue

                        move_tuple = (sr, sc, er, ec)

                        if in_chess_area(sr, sc) and in_chess_area(er, ec):

                            return move_tuple

                        if fallback is None:

                            fallback = move_tuple

        return fallback



    def _process_headless_script():

        nonlocal running, show_material, game_over, replay_mode, ui_state_text, sidebar_scroll, VERBOSE_DEBUG

        script = globals().get('HEADLESS_SCRIPT')

        if not script:

            return

        state = globals().get(HEADLESS_STATE_KEY)

        if state is None:

            state = {'index': 0, 'stage': None, 'wait_until': 0, 'capture': None, 'fails': [], 'log': [], 'pending_move': None}

            globals()[HEADLESS_STATE_KEY] = state

        if state.get('done'):

            return

        if state['stage'] == 'prewait':

            if pygame.time.get_ticks() < state['wait_until']:

                return

            state['stage'] = None

        if state['index'] >= len(script):

            state['done'] = True

            globals()['HEADLESS_RESULTS'] = {'fails': list(state['fails']), 'log': list(state['log'])}

            globals()['HEADLESS_SCRIPT'] = None

            running = False

            return

        step = script[state['index']]

        name = step.get('name', step.get('button', f'step{state["index"]}'))

        if state['stage'] is None:

            _apply_headless_mutations(step.get('set'))

            env = _headless_env()

            try:

                screen.fill((24, 40, 64))

                active_col = TURN_ORDER[turn_i] if forced_turn is None else forced_turn

                draw_board(screen, board, selected, moves, font, active_col,

                           banner_text=banner, ui_state_text=ui_state_text,

                           flash_color=gs.elim_flash_color, flash_on=gs.elim_flash_on)

                draw_sidebar(screen, moves_list, sidebar_scroll, show_material, mat.captured_points,

                             auto_elim_enabled, gs.two_stage_active, gs.grace_active, game_over)

                pygame.display.flip()

            except Exception:

                pass

            wait_for = step.get('wait_for')

            if callable(wait_for):

                try:

                    if not wait_for(env):

                        state['stage'] = 'prewait'

                        state['wait_until'] = pygame.time.get_ticks() + int(step.get('wait_for_ms', 120))

                        state['capture'] = None

                        return

                except Exception:

                    pass

            button_key = step.get('button')

            has_board_move = bool(step.get('auto_move') or step.get('move'))

            rect = UI_RECTS.get(button_key) if button_key else None

            if not has_board_move and rect is None:

                state['fails'].append(f"{name}: button not available")

                state['index'] += 1

                state['stage'] = None

                state['capture'] = None

                return

            capture_fn = step.get('capture')

            capture_val = None

            if callable(capture_fn):

                try:

                    capture_val = capture_fn(env)

                except Exception as exc:

                    state['fails'].append(f"{name}: capture failed ({exc})")

            state['capture'] = capture_val

            pending_move: Optional[Tuple[int, int, int, int]] = None

            if step.get('auto_move'):

                pending_move = _find_first_legal_move()

                if pending_move is None:

                    state['fails'].append(f"{name}: no legal move available")

                    state['index'] += 1

                    state['stage'] = None

                    state['capture'] = None

                    return

            elif step.get('move'):

                mv_spec = step['move']

                if isinstance(mv_spec, dict):

                    fr = mv_spec.get('from')

                    to = mv_spec.get('to')

                    if fr and to:

                        pending_move = (int(fr[0]), int(fr[1]), int(to[0]), int(to[1]))

                elif isinstance(mv_spec, (list, tuple)) and len(mv_spec) == 4:

                    pending_move = (int(mv_spec[0]), int(mv_spec[1]), int(mv_spec[2]), int(mv_spec[3]))

                if pending_move is None:

                    state['fails'].append(f"{name}: invalid move specification")

                    state['index'] += 1

                    state['stage'] = None

                    state['capture'] = None

                    return

            if pending_move:

                sr, sc, er, ec = pending_move

                if not (0 <= sr < BOARD_SIZE and 0 <= sc < BOARD_SIZE and 0 <= er < BOARD_SIZE and 0 <= ec < BOARD_SIZE):

                    state['fails'].append(f"{name}: move out of bounds {pending_move}")

                    state['index'] += 1

                    state['stage'] = None

                    state['capture'] = None

                    return

            state['pending_move'] = pending_move

            if pending_move:

                try:

                    gs.freeze_advance = False

                    gs.post_move_delay_until = 0

                    gs.two_stage_pause = False

                    gs.waiting_ready = False

                    setattr(gs, '_duel_delay_until', None)

                except Exception:

                    pass

                _post_board_move(pending_move)

                wait_ms = step.get('wait_ms', 280)

            else:

                pos = step.get('pos') or (rect.center if rect else (LOGICAL_W // 2, LOGICAL_H // 2))

                for et in step.get('events', ['down', 'up']):

                    if et == 'down':

                        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': pos, 'button': 1}))

                    elif et == 'up':

                        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, {'pos': pos, 'button': 1}))

                wait_ms = step.get('wait_ms', 160)

            state['wait_until'] = pygame.time.get_ticks() + int(wait_ms)

            state['stage'] = 'wait'

        else:

            if pygame.time.get_ticks() < state['wait_until']:

                return

            env = _headless_env()

            capture_val = state.get('capture')

            check_fn = step.get('check')

            ok = True

            msg = None

            pending_for_log = state.get('pending_move')

            if callable(check_fn):

                try:

                    res = check_fn(env, capture_val)

                except Exception as exc:

                    ok = False

                    msg = f"check exception {exc}"

                else:

                    if isinstance(res, tuple):

                        ok, msg = res

                    elif isinstance(res, bool):

                        ok = res

                        msg = None if ok else 'check returned False'

                    else:

                        ok = bool(res)

                        msg = None if ok else str(res)

            if ok:

                state['log'].append(f"{name} ok")

            else:

                detail = msg or 'check failed'

                if pending_for_log:

                    detail = f"{detail} (move {pending_for_log})"

                state['fails'].append(f"{name}: {detail}")

            if step.get('set_after'):

                _apply_headless_mutations(step['set_after'])

            state['stage'] = None

            state['capture'] = None

            state['pending_move'] = None

            state['index'] += 1



    def play_move_sound(captured: bool=False):

        """Play a tiny tone on move (higher for capture). Uses winsound on Windows; otherwise no-op."""

        try:

            import sys

            if sys.platform.startswith('win'):

                import winsound

                freq = 880 if captured else 660

                dur = 80

                try:

                    winsound.Beep(freq, dur)

                except RuntimeError:

                    pass

        except Exception:

            pass

    while running:

        # First-frame render to avoid initial black window. Done once to prevent sidebar doubling.

        if not first_frame_drawn:

            try:

                screen.fill((24, 40, 64))

                draw_board(screen, board, selected, moves, font, TURN_ORDER[turn_i] if forced_turn is None else forced_turn,

                           banner_text=banner, ui_state_text=ui_state_text,

                           flash_color=gs.elim_flash_color, flash_on=gs.elim_flash_on)

                draw_sidebar(screen, moves_list, sidebar_scroll, show_material, mat.captured_points, auto_elim_enabled, gs.two_stage_active, gs.grace_active, game_over)

                pygame.display.flip()

                pygame.event.pump()

            except Exception:

                pass

            first_frame_drawn = True

        duel_log_entry = getattr(gs, '_pending_duel_move_log', None)

        if duel_log_entry:

            if getattr(gs, '_reset_moves_for_duel', False):

                moves_list.clear()

                sidebar_scroll = 0

                gs._reset_moves_for_duel = False

            moves_list.append(duel_log_entry)

            gs._pending_duel_move_log = None

        if globals().get('HEADLESS_ENABLED', False):
            _process_headless_script()

        if getattr(gs, '_duel_turn_reset', False):

            _prepare_forced_duel_reset()

            gs._duel_turn_reset = False

        # heartbeat log to confirm main loop active

        try:

            if HEARTBEAT and pygame.time.get_ticks() % 3000 < 60:

                print(f"[HEARTBEAT] t={pygame.time.get_ticks()}ms")

        except Exception:

            pass

        # Simple visible fallback draw (before any game drawing) to ensure window isn't black

        if DEBUG_FORCE_VISIBLE:

            try:

                # Use bright colors so it's obvious

                for rr in range(BOARD_SIZE):

                    for cc in range(BOARD_SIZE):

                        col = (180, 180, 200) if (rr+cc) % 2 == 0 else (120, 120, 140)

                        pygame.draw.rect(screen, col, (cc*SQUARE, rr*SQUARE, SQUARE, SQUARE))

                # draw simple border for chess area

                pygame.draw.rect(screen, (30, 90, 30), (CH_MIN*SQUARE, CH_MIN*SQUARE, 8*SQUARE, 8*SQUARE), 4)

            except Exception:

                # if drawing fallback fails, ignore and continue (we'll still attempt regular draw)

                pass

        if game_over:

            # Winner overlay and sidebar drawn, no further move logic

            gs.freeze_advance = True

            gs.post_move_delay_until = 0

            gs.elim_flash_color = None

            gs.chess_lock = True



            # Render board + sidebar first

            try:

                screen.fill((24, 40, 64))

                active_col = TURN_ORDER[turn_i] if forced_turn is None else forced_turn

                draw_board(screen, board, selected, moves, font, active_col,

                           banner_text=banner, ui_state_text=ui_state_text,

                           flash_color=None, flash_on=True)

                draw_sidebar(screen, moves_list, sidebar_scroll, show_material, mat.captured_points,

                             auto_elim_enabled, gs.two_stage_active, gs.grace_active, game_over)

                # Winner/draw overlay

                alive_kings = board.alive_colors()

                duel_active = bool(getattr(gs, 'two_stage_active', False) and getattr(gs, 'chess_lock', False))

                if len(alive_kings) == 1:

                    winner = alive_kings[0]

                    W, H = screen.get_size()

                    veil = pygame.Surface((W, H), pygame.SRCALPHA)

                    veil.fill((0,0,0,90))

                    screen.blit(veil, (0,0))

                    title_font = pygame.font.SysFont("Arial", 40, bold=True)

                    info_font  = pygame.font.SysFont("Arial", 26, bold=True)

                    sub_font   = pygame.font.SysFont("Arial", 22, bold=False)

                    player_names = getattr(gs, 'player_names', {}) if hasattr(gs, 'player_names') else {}

                    def _name_for(color):

                        if color is None:

                            return "?"

                        return player_names.get(color.name, color.name.title())

                    winner_rgb = PLAYER_COLORS[winner] if winner != PColor.BLACK else (255,255,255)

                    title_text = title_font.render(f"Winner: {_name_for(winner)}", True, winner_rgb)

                    title_rect = title_text.get_rect(center=(W//2, H//2 - 28))

                    screen.blit(title_text, title_rect)

                    y_cursor = title_rect.bottom + 18

                    if duel_active:

                        finalists = []

                        for attr in ('_finalists_a', '_finalists_b'):

                            col = getattr(gs, attr, None)

                            if col and col not in finalists:

                                finalists.append(col)

                        if finalists:

                            segments = []

                            for idx, col in enumerate(finalists):

                                col_rgb = PLAYER_COLORS.get(col, (230,230,230))

                                segments.append(info_font.render(_name_for(col), True, col_rgb))

                                if idx == 0 and len(finalists) > 1:

                                    segments.append(info_font.render(" vs ", True, (240,240,240)))

                            total_w = sum(surf.get_width() for surf in segments)

                            x_pos = (W - total_w) // 2

                            for surf in segments:

                                screen.blit(surf, (x_pos, y_cursor))

                                x_pos += surf.get_width()

                            y_cursor += info_font.get_height() + 18

                    sub_text = sub_font.render("Press ESC to quit / Play Again in sidebar", True, (230,230,230))

                    sub_rect = sub_text.get_rect(center=(W//2, y_cursor))

                    screen.blit(sub_text, sub_rect)

                elif getattr(gs, '_draw_by_repetition', False):

                    W, H = screen.get_size()

                    veil = pygame.Surface((W, H), pygame.SRCALPHA)

                    veil.fill((0,0,0,90))

                    screen.blit(veil, (0,0))

                    title = pygame.font.SysFont("Arial", 40, bold=True)

                    sub   = pygame.font.SysFont("Arial", 22, bold=False)

                    msg1 = "Draw by repetition"

                    msg2 = "Press ESC to quit  Play Again in sidebar"

                    t1 = title.render(msg1, True, (240,240,240))

                    t2 = sub.render(msg2, True, (230,230,230))

                    screen.blit(t1, t1.get_rect(center=(W//2, H//2 - 12)))

                    screen.blit(t2, t2.get_rect(center=(W//2, H//2 + 24)))

            except Exception:

                pass

        # Two-player activation pause overlay: render once until user resumes

        try:

            if getattr(gs, 'two_stage_pause', False):

                # Render board + sidebar first (already done at loop end), here draw a veil + message

                W, H = screen.get_size()

                veil = pygame.Surface((W, H), pygame.SRCALPHA)

                veil.fill((0,0,0,110))

                screen.blit(veil, (0,0))

                title = pygame.font.SysFont("Arial", 36, bold=True)

                sub   = pygame.font.SysFont("Arial", 22, bold=False)

                a = getattr(gs, 'final_a', None)

                b = getattr(gs, 'final_b', None)

                who = f"{a.name} vs {b.name}" if a and b else "Two-player finals"

                t1 = title.render(f"Two-player activated: {who}", True, (235,235,210))

                t2 = sub.render("Press  Resume to continue (inspection pause)", True, (230,230,230))

                screen.blit(t1, t1.get_rect(center=(W//2, H//2 - 12)))

                screen.blit(t2, t2.get_rect(center=(W//2, H//2 + 20)))

        except Exception:

            pass



            # Unified minimal event handling for QUIT/ESC and Play Again

            evs = pygame.event.get()

            for ev in evs:

                if ev.type == pygame.QUIT:

                    running = False

                    break

                if ev.type == pygame.KEYDOWN:

                    try:

                        if ev.key == pygame.K_ESCAPE:

                            running = False

                            break

                        # F8: Force immediate Duel Now (manual two-player activation)

                        if ev.key == pygame.K_F8:

                            try:

                                ok = _force_duel_now(board, gs)

                                if ok and getattr(gs, '_duel_started', False):

                                    _prepare_forced_duel_reset()

                                    banner = "Forced: Duel (Chess) Now - White to move"

                                    ui_state_text = "Duel phase (forced)"

                                else:

                                    banner = "Force Duel (Chess) failed to start"

                            except Exception as _e:

                                banner = f"Force Duel (Chess) failed: {_e}"

                        # L: Toggle king locator overlay

                        if ev.key == pygame.K_l:

                            try:

                                cur = bool(UI_STATE.get('king_locator', False))

                                UI_STATE['king_locator'] = not cur

                                banner = f"King markers: {'On' if UI_STATE['king_locator'] else 'Off'}"

                            except Exception:

                                pass

                    except Exception:

                        pass

                if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:

                    try:

                        # Force Duel Now click handler

                        if 'btn_force_duel' in UI_RECTS:

                            mx, my = ev.pos

                            if UI_RECTS['btn_force_duel'].collidepoint(mx, my):

                                try:

                                    pre_reset_moves = list(moves_list)

                                except Exception:

                                    pre_reset_moves = []

                                try:

                                    ok = _force_duel_now(board, gs)

                                    if ok and getattr(gs, '_duel_started', False):

                                        _prepare_forced_duel_reset()

                                        banner = "Forced: Duel (Chess) Now - White to move"

                                        ui_state_text = "Duel phase (forced)"

                                        try:

                                            show_toast("Duel forced")

                                        except Exception:

                                            pass

                                    else:

                                        banner = "Force Duel (Chess) failed to start"

                                except Exception as _e:

                                    banner = f"Force Duel (Chess) failed: {_e}"

                                try:

                                    winner_name = None

                                    alive = board.alive_colors()

                                    if len(alive) == 1:

                                        winner_name = alive[0].name

                                    elif getattr(gs, '_draw_by_repetition', False):

                                        winner_name = 'DRAW'

                                    save_game_record_if_ready(pre_reset_moves, winner_name=winner_name, duel_mode=False)

                                except Exception:

                                    pass

                    except Exception:

                        pass

            if not running:

                break



            pygame.display.flip()

            clock.tick(60)

            continue

        # Debounce after new game to prevent rapid redraws/flashing

        if UI_STATE.get('debounce_newgame_until', 0) > pygame.time.get_ticks():

            pygame.time.wait(60)

            continue

        # Do not forcibly reset freeze_advance each frame; timers and game_over manage it

        for ev in pygame.event.get():

            # Very early event logging to help debug missing mouse clicks

            try:

                if VERBOSE_DEBUG:

                    if ev.type == pygame.MOUSEBUTTONDOWN:

                        print(f"[EVENT LOG] MOUSEBUTTONDOWN pos={getattr(ev,'pos',None)} button={getattr(ev,'button',None)}")

                    if ev.type == pygame.MOUSEBUTTONUP:

                        print(f"[EVENT LOG] MOUSEBUTTONUP pos={getattr(ev,'pos',None)} button={getattr(ev,'button',None)}")

                    if ev.type == pygame.KEYDOWN:

                        print(f"[EVENT LOG] KEYDOWN key={getattr(ev,'key',None)} mod={getattr(ev,'mod',None)}")

                    # 'b' to dump board state and current active player for debugging

                    try:

                        if ev.key == pygame.K_b:

                            # Build ASCII board and print active turn for quick diagnostics

                            rows = []

                            for rr in range(BOARD_SIZE):

                                row = []

                                for cc in range(BOARD_SIZE):

                                    p = board.get(rr, cc)

                                    row.append('.' if p is None else (p.kind or '?'))

                                rows.append(''.join(row))

                            if VERBOSE_DEBUG:

                                print('[BOARD DUMP]')

                            for rline in rows:

                                print(rline)

                            try:

                                active_col = TURN_ORDER[turn_i] if forced_turn is None else forced_turn

                                print(f"[BOARD DUMP] turn_i={turn_i} active={active_col.name} forced={forced_turn}")

                            except Exception:

                                print('[BOARD DUMP] turn info unavailable')

                        # F9: toggle AI debug HUD

                        if ev.key == pygame.K_F9:

                            AI_DEBUG_HUD = not AI_DEBUG_HUD

                            state = 'ON' if AI_DEBUG_HUD else 'OFF'

                            if VERBOSE_DEBUG:

                                print(f"[AI HUD] {state}")

                        # F8: Force immediate Duel Now (manual two-player activation)

                        if ev.key == pygame.K_F8:

                            try:

                                ok = _force_duel_now(board, gs)

                                if ok and getattr(gs, '_duel_started', False):

                                    _prepare_forced_duel_reset()

                                    banner = "Forced: Duel (Chess) Now - White to move"

                                    ui_state_text = "Duel phase (forced)"

                                else:

                                    banner = "Force Duel (Chess) failed to start"

                            except Exception as _e:

                                banner = f"Force Duel (Chess) failed: {_e}"

                        # L: toggle king locator overlay on/off

                        if ev.key == pygame.K_l:

                            try:

                                cur = bool(UI_STATE.get('king_locator', False))

                                UI_STATE['king_locator'] = not cur

                                banner = f"King markers: {'On' if UI_STATE['king_locator'] else 'Off'}"

                            except Exception:

                                pass

                    except Exception:

                        pass

            except Exception:

                pass



            if ev.type == pygame.QUIT:

                running = False

                break

            elif ev.type == pygame.VIDEORESIZE:

                # Mark that a resize is pending and update the timestamp

                try:

                    resize_pending = True

                    resize_last_event_ms = pygame.time.get_ticks()

                except Exception:

                    pass

            elif ev.type == pygame.MOUSEWHEEL:

                mx, my = pygame.mouse.get_pos()

                overlay_rect = UI_STATE.get('library_overlay_rect')

                if overlay_rect and overlay_rect.collidepoint(mx, my):

                    try:

                        cur = int(UI_STATE.get('library_overlay_scroll', 0) or 0)

                        max_scroll = int(UI_STATE.get('library_overlay_max_scroll', 0) or 0)

                        cur = max(0, min(max_scroll, cur - ev.y))

                        UI_STATE['library_overlay_scroll'] = cur

                    except Exception:

                        pass

                    continue

                if mx >= LOGICAL_W:

                    sidebar_scroll = max(0, sidebar_scroll - ev.y)

            elif ev.type == pygame.MOUSEMOTION:

                # update drag mouse position so ghost follows cursor

                try:

                    mx,my = ev.pos

                    if 'dragging' in locals() and dragging:

                        drag_mouse_pos = (mx, my)

                    # Sidebar hover updates

                    if mx >= LOGICAL_W:

                        # compute current hover key if any

                        over_key = None

                        for k, rect in UI_RECTS.items():

                            if rect.collidepoint(mx, my):

                                over_key = k

                                break

                        # clear all previous hovers, then set current

                        for hk in list(UI_STATE.keys()):

                            if str(hk).startswith('hover_'):

                                UI_STATE[hk] = False

                        if over_key is not None:

                            UI_STATE[f'hover_{over_key}'] = True

                    else:

                        # outside sidebar: clear all hovers

                        for hk in list(UI_STATE.keys()):

                            if str(hk).startswith('hover_'):

                                UI_STATE[hk] = False

                        # track board hover square for legal-destination emphasis

                        br, bc = my // SQUARE, mx // SQUARE

                        if 0 <= br < BOARD_SIZE and 0 <= bc < BOARD_SIZE:

                            # store canonical square under mouse by inverting view

                            can_r, can_c = _transform_rc_for_view(br, bc, inverse=True)

                            UI_STATE['hover_square'] = (can_r, can_c)

                        else:

                            UI_STATE['hover_square'] = None

                except Exception:

                    pass

            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and ev.pos[0] >= LOGICAL_W:

                mx,my = ev.pos

                # handle sidebar toggles pressed visual (only for clicks inside sidebar)

                # clear previous pressed states to avoid multiple pressed visuals

                for key in list(UI_STATE.keys()):

                    if str(key).startswith('pressed_'):

                        UI_STATE[key] = False

                for k, rect in UI_RECTS.items():

                    if rect.collidepoint(mx,my):

                        UI_STATE[f'pressed_{k}'] = True

                # immediate redraw of sidebar so indent shows on press without waiting for next frame

                try:

                    draw_sidebar(screen, moves_list, sidebar_scroll, show_material, mat.captured_points, auto_elim_enabled, gs.two_stage_active, gs.grace_active)

                    pygame.display.update(pygame.Rect(LOGICAL_W, 0, screen.get_size()[0]-LOGICAL_W, LOGICAL_H))

                except Exception:

                    pass

                # We'll toggle on MOUSEBUTTONUP to allow click-drag cancel

            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:

                mx,my = ev.pos

                overlay_rect = UI_STATE.get('library_overlay_rect')

                if overlay_rect and overlay_rect.collidepoint(mx, my):

                    handled_overlay = False

                    close_rect = UI_RECTS.get('library_overlay_close')

                    if close_rect and close_rect.collidepoint(mx, my):

                        UI_STATE.pop('library_overlay', None)

                        UI_STATE.pop('library_overlay_rect', None)

                        UI_STATE.pop('library_overlay_max_scroll', None)

                        UI_STATE.pop('library_overlay_scroll', None)

                        handled_overlay = True

                        banner = "Library overlay hidden"

                    else:

                        overlay = UI_STATE.get('library_overlay') or {}

                        entries = overlay.get('entries') or []

                        for idx, entry in enumerate(entries):

                            key = f'library_entry_{idx}'

                            rect = UI_RECTS.get(key)

                            if rect and rect.collidepoint(mx, my):

                                path = entry.get('path')

                                if path:

                                    try:

                                        _open_with_default_app(path)

                                        try:

                                            show_toast(f"Opening {os.path.basename(path)}", ms=1800)

                                        except Exception:

                                            pass

                                        banner = f"Opening {os.path.basename(path)}"

                                    except Exception as exc:

                                        print(f"[LIBRARY] failed to open entry: {exc}")

                                handled_overlay = True

                                break

                    if handled_overlay:

                        dragging = False

                        drag_start = None

                        drag_legal_targets = []

                        continue

                # If we were dragging a piece and released over a legal square on the BOARD, apply the move

                try:

                    # If not ready yet, ignore board drops (still configuring HUM/AI)

                    if getattr(gs, 'waiting_ready', False):

                        dragging = False

                        drag_start = None

                        drag_legal_targets = []

                        # fall through to sidebar buttons so Ready can be pressed

                        raise Exception("Waiting for Ready; board drop ignored")

                    if 'dragging' in locals() and dragging and mx < LOGICAL_W:

                        dc = mx // SQUARE

                        dr = my // SQUARE

                        if 0 <= dr < BOARD_SIZE and 0 <= dc < BOARD_SIZE and (dr,dc) in drag_legal_targets and not gs.freeze_advance:

                            history.append(make_snapshot())

                            future.clear()

                            prev_forced_turn = forced_turn

                            pre_target = board.get(dr, dc)

                            try:

                                print(f"[DRAG APPLY-UP] attempting board_do_move from {drag_start} -> ({dr},{dc})")

                            except Exception:

                                pass

                            sr, sc = drag_start

                            cap, ph, pk, eff = board_do_move(board, sr, sc, dr, dc)

                            try:

                                print(f"[DRAG APPLY-UP] board_do_move returned cap={cap}, ph={ph}, pk={pk}, eff={eff}")

                            except Exception:

                                pass

                            try:

                                after_piece = board.get(dr, dc)

                                print(f"[VERIFY MOVE] at ({dr},{dc}) exists={bool(after_piece)} id={id(after_piece) if after_piece else None} kind={(after_piece.kind if after_piece else None)}")

                            except Exception as e:

                                print(f"[VERIFY MOVE] exception checking board at ({dr},{dc}): {e}")

                            captured_piece = cap if cap else pre_target

                            mover_after = board.get(dr, dc)

                            try:

                                print(f"[DRAG APPLY-UP] mover_after at ({dr},{dc}) = {mover_after.kind if mover_after else None} color={(mover_after.color.name if mover_after else None)}")

                                print(f"[BOARD SNAPSHOT] {dump_board(board)}")

                            except Exception:

                                pass

                            promoted = bool(eff.get('promoted'))

                            if captured_piece: mat.on_capture(captured_piece)

                            moves_list.append(

                                format_move_algebraic(GameState.turn_counter + 1, (TURN_ORDER[turn_i] if forced_turn is None else forced_turn),

                                                     pk if pk else (mover_after.kind if mover_after else '?'),

                                                     sr, sc, dr, dc, captured_piece, promoted)

                            )

                            try:

                                play_move_sound(captured_piece is not None)

                                move_pulse = {'square': (dr, dc), 'until': pygame.time.get_ticks() + 360}

                            except Exception:

                                pass



                            # Two-stage and bookkeeping

                            ensure_two_stage_state()

                            if gs.two_stage_active and (TURN_ORDER[turn_i] if forced_turn is None else forced_turn) in (gs.final_a, gs.final_b):

                                if in_chess_area(dr,dc) or any(board.get(rr,cc) and board.get(rr,cc).color==(TURN_ORDER[turn_i] if forced_turn is None else forced_turn) and in_chess_area(rr,cc)

                                                             for rr in range(BOARD_SIZE) for cc in range(BOARD_SIZE)):

                                    if not gs.entered[(TURN_ORDER[turn_i] if forced_turn is None else forced_turn)]:

                                        gs.entered[(TURN_ORDER[turn_i] if forced_turn is None else forced_turn)] = True

                                        reduced = apply_queen_reduction_if_needed((TURN_ORDER[turn_i] if forced_turn is None else forced_turn))

                                        if reduced:

                                            banner = f"{((TURN_ORDER[turn_i] if forced_turn is None else forced_turn).name)}: reduced {len(reduced)} Queen(s) to Bishop(s) on entry."

                                    other = two_stage_opponent((TURN_ORDER[turn_i] if forced_turn is None else forced_turn))

                                    if not DUEL_TELEPORT_ON_TWO and other and gs.entered[other] and not gs.grace_active:

                                        gs.grace_active = True

                                        gs.grace_turns_remaining = 2



                            if not gs.chess_lock and both_fully_migrated_incl_kings(board):

                                gs.chess_lock = True



                            try:

                                if prev_forced_turn is None:

                                    turn_i = _advance_turn_index(turn_i + 1)

                                else:

                                    turn_i = _advance_turn_index(TURN_ORDER.index((TURN_ORDER[turn_i] if forced_turn is None else forced_turn)) + 1)

                            except Exception:

                                pass



                            victims = []

                            for col in board.alive_colors():

                                if col == (TURN_ORDER[turn_i] if forced_turn is None else forced_turn): continue

                                if king_in_check(board, col):

                                    victims.append(col)

                            forced_turn = clockwise_from((TURN_ORDER[turn_i] if forced_turn is None else forced_turn), victims) if victims else None



                            selected, moves = None, []

                            GameState.turn_counter += 1

                            gs.start_move_delay(MOVE_DELAY_MS)



                            # Force redraw and display update after drop

                            try:

                                screen.fill((24, 40, 64))

                                draw_board(

                                    screen, board, selected, moves, font, (TURN_ORDER[turn_i] if forced_turn is None else forced_turn),

                                    banner_text=banner, ui_state_text=ui_state_text,

                                    flash_color=gs.elim_flash_color, flash_on=gs.elim_flash_on

                                )

                                draw_sidebar(screen, moves_list, sidebar_scroll, show_material, mat.captured_points, auto_elim_enabled, gs.two_stage_active, gs.grace_active)

                                pygame.display.flip()

                                pygame.event.pump()

                                pygame.time.wait(120)

                            except Exception:

                                pass



                        # end drop handling on mouse-up

                        dragging = False

                        drag_start = None

                        drag_legal_targets = []

                except Exception:

                    # ignore drop errors here and continue to sidebar handling

                    dragging = False

                    drag_start = None

                    drag_legal_targets = []

                # clear pressed visuals and fire actions if cursor still on button

                for k, rect in UI_RECTS.items():

                    was_pressed = UI_STATE.get(f'pressed_{k}', False)

                    if was_pressed:

                        UI_STATE[f'pressed_{k}'] = False

                        if rect.collidepoint(mx,my):

                            # handle named actions

                            if k == 'btn_ready':

                                gs.waiting_ready = False

                                # Lock orientation to the single human seat at Ready (if exactly one)

                                try:

                                    humans = [col for col in TURN_ORDER if not gs.player_is_ai.get(col, False)]

                                    if len(humans) == 1:

                                        UI_STATE['view_seat'] = humans[0].name

                                        banner = f"View set to {humans[0].name}"

                                    elif len(humans) == 0:

                                        UI_STATE['view_seat'] = 'AUTO'

                                        banner = "ReadyAUTO view"

                                    else:

                                        banner = "Readyplay when you are!"

                                except Exception:

                                    banner = "Readyplay when you are!"

                                continue

                            if k == 'btn_newgame':

                                try:

                                    now_ticks = pygame.time.get_ticks()

                                    confirm_until = int(UI_STATE.get('confirm_newgame_until', 0) or 0)

                                    if confirm_until > 0 and now_ticks < confirm_until:

                                        # Confirmed within window: perform reset

                                        # Always resume play immediately on fresh game

                                        hold_pref = False

                                        # Reset core state

                                        board = Board()

                                        mat = MaterialTracker()

                                        moves_list.clear()

                                        history.clear(); future.clear()

                                        turn_i = 0

                                        forced_turn = None

                                        selected = None; moves = []

                                        dragging = False; drag_start = None; drag_legal_targets = []

                                        # Reset GameState and re-apply preferences

                                        gs = GameState()

                                        gs.hold_at_start = hold_pref

                                        gs.waiting_ready = False

                                        try:

                                            prefs = load_user_settings()

                                            if not isinstance(prefs, dict):

                                                prefs = {}

                                            prefs["hold_at_start"] = False

                                            save_user_settings(prefs)

                                        except Exception:

                                            pass

                                        # Reset teams to Human on new game (per request)

                                        for col in TURN_ORDER:

                                            gs.player_is_ai[col] = False

                                        # reflect into AI_PLAYERS

                                        AI_PLAYERS = set()

                                        # Rebuild resign pill rects to ensure geometry consistent

                                        try:

                                            resign_rects.clear()

                                            for pcol, (r0,c0) in CORNER_RECTS.items():

                                                resign_rects[pcol] = pygame.Rect(c0*SQUARE+8, r0*SQUARE+8, 2*SQUARE-16, 2*SQUARE-16)

                                        except Exception:

                                            pass

                                        # Clear any sidebar hover/pressed states

                                        try:

                                            for k in list(UI_STATE.keys()):

                                                if str(k).startswith('pressed_') or str(k).startswith('hover_'):

                                                    UI_STATE[k] = False

                                        except Exception:

                                            pass

                                        # Clear algebraic shadow list if present on screen

                                        try:

                                            if hasattr(screen, '_algebraic_moves'):

                                                screen._algebraic_moves = []

                                        except Exception:

                                            pass

                                        # Set a debounce to prevent rapid redraws/flashing

                                        UI_STATE['debounce_newgame_until'] = pygame.time.get_ticks() + 200

                                        GameState.turn_counter = 0

                                        UI_STATE['confirm_newgame_until'] = 0

                                        banner = "New game started"

                                    else:

                                        # First click: ask for confirmation and show label for ~3 seconds

                                        UI_STATE['confirm_newgame_until'] = now_ticks + 3000

                                        banner = "Press again to confirm New Game"

                                except Exception as e:

                                    banner = f"New game failed: {e}"

                                continue

                            if k == 'btn_holdstart':

                                try:

                                    gs.hold_at_start = not getattr(gs, 'hold_at_start', False)

                                    if getattr(gs, 'waiting_ready', False) and not gs.hold_at_start:

                                        gs.waiting_ready = False

                                        banner = 'Hold disabled  game started.'

                                    else:

                                        banner = f"Hold at Start: {'On' if gs.hold_at_start else 'Off'}"

                                    # Persist updated preference

                                    try:

                                        cur = load_user_settings()

                                        if not isinstance(cur, dict):

                                            cur = {}

                                        cur["hold_at_start"] = bool(gs.hold_at_start)

                                        save_user_settings(cur)

                                    except Exception:

                                        pass

                                except Exception:

                                    banner = 'Hold toggle failed'

                                continue

                            if k == 'btn_force_duel':

                                try:

                                    ok = _force_duel_now(board, gs)

                                    if ok and getattr(gs, '_duel_started', False):

                                        _prepare_forced_duel_reset()

                                        banner = "Forced: Duel (Chess) Now - White to move"

                                        ui_state_text = "Duel phase (forced)"

                                        try:

                                            show_toast("Duel forced")

                                        except Exception:

                                            pass

                                    else:

                                        banner = "Force Duel (Chess) failed to start"

                                except Exception as _e:

                                    banner = f"Force Duel (Chess) failed: {_e}"

                                continue

                            if k.startswith('toggle_'):

                                # toggle per-seat AI

                                try:

                                    parts = k.split('_')

                                    cname = parts[1].upper()

                                    col = PColor[cname]

                                    new = not gs.player_is_ai.get(col, False)

                                    gs.player_is_ai[col] = new

                                    # reset the pre-ai delay flag when toggling

                                    gs.ai_delay_applied[col] = False

                                    AI_PLAYERS = {c for c, flag in gs.player_is_ai.items() if flag}

                                    # If we just switched this seat to HUMAN and it's currently that seat's turn,

                                    # cancel any AI delay/freeze so the human can move immediately.

                                    try:

                                        active_col = (TURN_ORDER[turn_i] if forced_turn is None else forced_turn)

                                        if active_col == col:

                                            banner = f"{col.name}: switched to HUMAN - your move."

                                        gs.post_move_delay_until = 0

                                        gs.freeze_advance = False

                                        gs.waiting_ready = False

                                    except Exception:

                                        pass

                                    # Update seat-oriented view: prefer the only human seat

                                    try:

                                        humans = [c for c in TURN_ORDER if not gs.player_is_ai.get(c, False)]

                                        if len(humans) == 1:

                                            UI_STATE['view_seat'] = humans[0].name

                                        elif len(humans) == 0:

                                            UI_STATE['view_seat'] = 'AUTO'

                                    except Exception:

                                        pass

                                except Exception:

                                    pass

                            elif k == 'btn_ai':

                                AI_STRENGTH = 'fast' if AI_STRENGTH == 'smart' else 'smart'

                                banner = f"AI mode: {AI_STRENGTH.upper()}"

                            elif k == 'btn_material':

                                show_material = not show_material

                                banner = f"Material line: {'On' if show_material else 'Off'}"

                            elif k == 'btn_view':

                                seq = ['AUTO', 'WHITE', 'GREY', 'BLACK', 'PINK']

                                cur = UI_STATE.get('view_seat', 'AUTO')

                                try:

                                    i = (seq.index(cur) + 1) % len(seq)

                                except Exception:

                                    i = 0

                                UI_STATE['view_seat'] = seq[i]

                                banner = f"View set to {seq[i]}"

                            elif k == 'btn_coords':

                                try:

                                    cur = bool(UI_STATE.get('show_coords', False))

                                    UI_STATE['show_coords'] = not cur

                                    banner = f"Coordinates: {'On' if UI_STATE['show_coords'] else 'Off'}"

                                except Exception:

                                    pass

                            elif k == 'btn_export':

                                ok, msg = do_export_moves()

                                banner = msg

                            elif k == 'btn_autoelim':

                                # Cycle threshold: Off(0) -> 18 -> 30 -> Off

                                try:

                                    cur = int(getattr(gs, 'auto_elim_threshold', 18))

                                except Exception:

                                    cur = 18

                                nxt = 18 if cur <= 0 else (30 if cur == 18 else 0)

                                gs.auto_elim_threshold = nxt

                                # Persist updated preference

                                try:

                                    curset = load_user_settings()

                                    if not isinstance(curset, dict):

                                        curset = {}

                                    curset["auto_elim_threshold"] = int(nxt)

                                    save_user_settings(curset)

                                except Exception:

                                    pass

                                if gs.two_stage_active:

                                    banner = f"Auto-Elim {nxt if nxt>0 else 'Off'} (suppressed in two-player mode)"

                                else:

                                    banner = f"Auto-Elim set to {nxt if nxt>0 else 'Off'}"

                            elif k == 'btn_logs':

                                try:

                                    VERBOSE_DEBUG = not VERBOSE_DEBUG

                                    banner = f"Logs: {'On' if VERBOSE_DEBUG else 'Off'}"

                                except Exception:

                                    pass

                            elif k == 'btn_rules_pdf':

                                export_rules_and_open_async()

                                banner = 'Opening rules reference...'

                                continue

                            elif k == 'btn_open_library':

                                overlay_active = bool(UI_STATE.get('library_overlay'))

                                if overlay_active:

                                    UI_STATE.pop('library_overlay', None)

                                    UI_STATE.pop('library_overlay_rect', None)

                                    UI_STATE.pop('library_overlay_max_scroll', None)

                                    UI_STATE.pop('library_overlay_scroll', None)

                                    UI_STATE.pop('library_overlay_last_drawn', None)

                                    try:

                                        print("[LIBRARY] overlay toggled off")

                                    except Exception:

                                        pass

                                    try:

                                        show_toast("Library overlay hidden", ms=1500)

                                    except Exception:

                                        pass

                                    banner = "Library overlay hidden"

                                else:

                                    try:

                                        folder = os.path.join(SCRIPT_DIR, 'games')

                                        activate_library_overlay(folder)

                                    except Exception as exc:

                                        print(f"[LIBRARY] overlay activation error: {exc}")

                                    open_games_library_async()

                                    try:

                                        print("[LIBRARY] overlay toggled on (async launch requested)")

                                    except Exception:

                                        pass

                                    try:

                                        show_toast("Opening games library…", ms=1800)

                                    except Exception:

                                        pass

                                    banner = "Opening games library..."

                                continue

                            elif k == 'btn_mode':

                                # Simple LONG/SHORT label toggle for now

                                cur = str(UI_STATE.get('mode', 'LONG')).upper()

                                nxt = 'SHORT' if cur == 'LONG' else 'LONG'

                                UI_STATE['mode'] = nxt

                                banner = f"Mode switched to {nxt}"

                            elif k == 'btn_scaled':

                                try:

                                    cur = bool(UI_STATE.get('scaled_mode', False))

                                    UI_STATE['scaled_mode'] = not cur

                                    # Recreate window with/without SCALED flag

                                    flags = pygame.RESIZABLE | pygame.DOUBLEBUF

                                    if UI_STATE['scaled_mode']:

                                        flags |= pygame.SCALED

                                    screen = pygame.display.set_mode((TOTAL_W, LOGICAL_H), flags)
                                    ensure_window_icon()

                                    banner = f"Scaled Mode: {'On' if UI_STATE['scaled_mode'] else 'Off'}"

                                except Exception:

                                    pass

                            elif k == 'btn_back':

                                if history:

                                    snap_now = make_snapshot()

                                    future.append(snap_now)

                                    snap = history.pop()

                                    restore_snapshot(snap)

                                    replay_mode = True

                                    ui_state_text = "Replay "

                            elif k == 'btn_resume':

                                # In two-player activation pause, Resume clears the pause and unfreezes

                                try:

                                    if getattr(gs, 'two_stage_pause', False):

                                        gs.two_stage_pause = False

                                        gs.freeze_advance = False

                                        ui_state_text = None

                                    elif replay_mode:

                                        replay_mode = False

                                        ui_state_text = None

                                        future.clear()

                                except Exception:

                                    pass

                            elif k == 'btn_fwd':

                                if future:

                                    snap_now = make_snapshot()

                                    history.append(snap_now)

                                    snap = future.pop()

                                    restore_snapshot(snap)

                                    replay_mode = True

                                    ui_state_text = "Replay "

            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:

                mx,my = ev.pos



                # Quick debug: pressing 'b' shows an ASCII dump of the board and active player

                # (Handled also via KEYDOWN, but leave here as an extra safeguard.)

                # NOTE: 'b' handling is primarily in KEYDOWN; keep this comment to aid debugging.



                # Sidebar buttons

                if mx >= LOGICAL_W:

                    if 'btn_material' in UI_RECTS and UI_RECTS['btn_material'].collidepoint(mx, my):

                        show_material = not show_material

                        banner = f"Material line: {'On' if show_material else 'Off'}"

                        continue

                # If we were dragging a piece, handle drop here (after UI/button handling)

                try:

                    if dragging:

                        # determine drop square (map from view to canonical)

                        dc = mx // SQUARE

                        dr = my // SQUARE

                        dr, dc = _transform_rc_for_view(dr, dc, inverse=True)

                        # only accept drops inside the board

                        if 0 <= dr < BOARD_SIZE and 0 <= dc < BOARD_SIZE and (dr,dc) in drag_legal_targets and not gs.freeze_advance:

                            # perform the move from drag_start -> (dr,dc)

                            history.append(make_snapshot())

                            future.clear()

                            prev_forced_turn = forced_turn

                            pre_target = board.get(dr, dc)

                            try:

                                if VERBOSE_DEBUG:

                                    print(f"[DRAG APPLY] attempting board_do_move from {drag_start} -> ({dr},{dc})")

                            except Exception:

                                pass

                            sr, sc = drag_start

                            cap, ph, pk, eff = board_do_move(board, sr, sc, dr, dc)

                            try:

                                if VERBOSE_DEBUG:

                                    print(f"[DRAG APPLY] board_do_move returned cap={cap}, ph={ph}, pk={pk}, eff={eff}")

                            except Exception:

                                pass

                            try:

                                if VERBOSE_DEBUG:

                                    after_piece = board.get(dr, dc)

                                    print(f"[VERIFY MOVE] at ({dr},{dc}) exists={bool(after_piece)} id={id(after_piece) if after_piece else None} kind={(after_piece.kind if after_piece else None)}")

                            except Exception as e:

                                if VERBOSE_DEBUG:

                                    print(f"[VERIFY MOVE] exception checking board at ({dr},{dc}): {e}")

                            captured_piece = cap if cap else pre_target

                            mover_after = board.get(dr, dc)

                            try:

                                if VERBOSE_DEBUG:

                                    print(f"[DRAG APPLY] mover_after at ({dr},{dc}) = {mover_after.kind if mover_after else None} color={(mover_after.color.name if mover_after else None)}")

                                    print(f"[BOARD SNAPSHOT] {dump_board(board)}")

                            except Exception:

                                pass

                            promoted = bool(eff.get('promoted'))

                            if captured_piece: mat.on_capture(captured_piece)

                            moves_list.append(

                                format_move_algebraic(GameState.turn_counter + 1, (TURN_ORDER[turn_i] if forced_turn is None else forced_turn),

                                                     pk if pk else (mover_after.kind if mover_after else '?'),

                                                     sr, sc, dr, dc, captured_piece, promoted)

                            )

                            try:

                                play_move_sound(captured_piece is not None)

                                move_pulse = {'square': (dr, dc), 'until': pygame.time.get_ticks() + 360}

                            except Exception:

                                pass



                            # Two-stage and book-keeping follow same path as normal click move

                            ensure_two_stage_state()

                            if gs.two_stage_active and (TURN_ORDER[turn_i] if forced_turn is None else forced_turn) in (gs.final_a, gs.final_b):

                                if in_chess_area(dr,dc) or any(board.get(rr,cc) and board.get(rr,cc).color==(TURN_ORDER[turn_i] if forced_turn is None else forced_turn) and in_chess_area(rr,cc)

                                                             for rr in range(BOARD_SIZE) for cc in range(BOARD_SIZE)):

                                    if not gs.entered[(TURN_ORDER[turn_i] if forced_turn is None else forced_turn)]:

                                        gs.entered[(TURN_ORDER[turn_i] if forced_turn is None else forced_turn)] = True

                                        reduced = apply_queen_reduction_if_needed((TURN_ORDER[turn_i] if forced_turn is None else forced_turn))

                                        if reduced:

                                            banner = f"{((TURN_ORDER[turn_i] if forced_turn is None else forced_turn).name)}: reduced {len(reduced)} Queen(s) to Bishop(s) on entry."

                                    other = two_stage_opponent((TURN_ORDER[turn_i] if forced_turn is None else forced_turn))

                                    # Under teleport rules, do NOT enable grace ('checks deferred')

                                    if (not DUEL_TELEPORT_ON_TWO) and other and gs.entered[other] and not gs.grace_active:

                                        gs.grace_active = True

                                        gs.grace_turns_remaining = 2



                            if not gs.chess_lock and both_fully_migrated_incl_kings(board):

                                gs.chess_lock = True



                            try:

                                if prev_forced_turn is None:

                                    turn_i = _advance_turn_index(turn_i + 1)

                                else:

                                    turn_i = _advance_turn_index(TURN_ORDER.index((TURN_ORDER[turn_i] if forced_turn is None else forced_turn)) + 1)

                            except Exception:

                                pass



                            victims = []

                            for col in board.alive_colors():

                                if col == (TURN_ORDER[turn_i] if forced_turn is None else forced_turn): continue

                                if king_in_check(board, col):

                                    victims.append(col)

                            forced_turn = clockwise_from((TURN_ORDER[turn_i] if forced_turn is None else forced_turn), victims) if victims else None



                            selected, moves = None, []

                            GameState.turn_counter += 1

                            gs.start_move_delay(MOVE_DELAY_MS)



                        # end drop handling

                        dragging = False

                        drag_start = None

                        drag_legal_targets = []

                except Exception:

                    # swallow drag/drop faults and continue

                    dragging = False

                    drag_start = None

                    drag_legal_targets = []

                    if 'btn_autoelim' in UI_RECTS and UI_RECTS['btn_autoelim'].collidepoint(mx, my):

                        # Cycle threshold Off -> 18 -> 30 -> Off even in fallback path

                        try:

                            cur = int(getattr(gs, 'auto_elim_threshold', 18))

                        except Exception:

                            cur = 18

                        nxt = 18 if cur <= 0 else (30 if cur == 18 else 0)

                        gs.auto_elim_threshold = nxt

                        # Persist updated preference

                        try:

                            curset = load_user_settings()

                            if not isinstance(curset, dict):

                                curset = {}

                            curset["auto_elim_threshold"] = int(nxt)

                            save_user_settings(curset)

                        except Exception:

                            pass

                        if gs.two_stage_active:

                            banner = f"Auto-Elim {nxt if nxt>0 else 'Off'} (suppressed in two-player stage)"

                        else:

                            banner = f"Auto-Elim set to {nxt if nxt>0 else 'Off'}"

                        continue

                    if 'btn_view' in UI_RECTS and UI_RECTS['btn_view'].collidepoint(mx, my):

                        seq = ['AUTO', 'WHITE', 'GREY', 'BLACK', 'PINK']

                        cur = UI_STATE.get('view_seat', 'AUTO')

                        try:

                            i = (seq.index(cur) + 1) % len(seq)

                        except Exception:

                            i = 0

                        UI_STATE['view_seat'] = seq[i]

                        banner = f"View set to {seq[i]}"

                        continue

                    if 'btn_export' in UI_RECTS and UI_RECTS['btn_export'].collidepoint(mx, my):

                        ok, msg = do_export_moves()

                        banner = msg

                        continue

                    if 'btn_ai' in UI_RECTS and UI_RECTS['btn_ai'].collidepoint(mx, my):

                        AI_STRENGTH = "fast" if AI_STRENGTH == "smart" else "smart"

                        banner = f"AI mode: {AI_STRENGTH.upper()}"

                        continue

                    if 'btn_mode' in UI_RECTS and UI_RECTS['btn_mode'].collidepoint(mx, my):

                        banner = "Mode button clicked"

                        continue

                    # Replay controls

                    if 'btn_back' in UI_RECTS and UI_RECTS['btn_back'].collidepoint(mx, my):

                        if history:

                            snap_now = make_snapshot()

                            future.append(snap_now)

                            snap = history.pop()

                            restore_snapshot(snap)

                            replay_mode = True

                            ui_state_text = "Replay "

                        continue

                    if 'btn_resume' in UI_RECTS and UI_RECTS['btn_resume'].collidepoint(mx, my):

                        if replay_mode:

                            replay_mode = False

                            ui_state_text = None

                            future.clear()

                        continue

                    if 'btn_fwd' in UI_RECTS and UI_RECTS['btn_fwd'].collidepoint(mx, my):

                        if future:

                            snap_now = make_snapshot()

                            history.append(snap_now)

                            snap = future.pop()

                            restore_snapshot(snap)

                            replay_mode = True

                            ui_state_text = "Replay "

                        continue



                # Resign pills (dynamic, per view)

                try:

                    for col in TURN_ORDER:

                        key = f"resign_{col.name.lower()}"

                        rect = UI_RECTS.get(key)

                        if rect is not None and rect.collidepoint(mx, my):

                            eliminate_color(board, gs, col, reason="resign", flash=True)

                            banner = f"{col.name} resigned."

                            break

                except Exception:

                    pass



                if replay_mode:

                    continue



                # Board clicks for human turns

                # Debug: log click coordinates and computed board square

                c = mx // SQUARE

                r = my // SQUARE

                try:

                    if VERBOSE_DEBUG:

                        print(f"[DEBUG CLICK] mouse=({mx},{my}) -> square=({r},{c})")

                    # set transient visual indicator for this click

                    try:

                        click_indicator = (mx, my, pygame.time.get_ticks() + CLICK_INDICATOR_MS)

                    except Exception:

                        pass

                except Exception:

                    pass

                if r >= BOARD_SIZE or c >= BOARD_SIZE:

                    continue



                active_color = TURN_ORDER[turn_i] if forced_turn is None else forced_turn

                # Map view coords to canonical board for selection

                r, c = _transform_rc_for_view(r, c, inverse=True)



                if active_color in AI_PLAYERS:

                    banner = f"{active_color.name} is AIwait..."

                    continue



                # Two-stage ensure + filters

                ensure_two_stage_state()

                must_filter = must_enter_filter_for(board, active_color)

                grace_block = grace_blocks_check_for(active_color)

                opponent = two_stage_opponent(active_color)



                if selected is None:

                    p = board.get(r,c)

                    try:

                        if VERBOSE_DEBUG:

                            print(f"[DEBUG CLICK] piece_at={p.kind if p else None} color={(p.color.name if p else None)}")

                    except Exception:

                        pass

                    if p and p.color == active_color:

                        raw_moves = legal_moves_for_piece(board, r, c, active_color)

                        try:

                            if VERBOSE_DEBUG:

                                print(f"[MOVE LOG] raw_moves for ({r},{c}) = {raw_moves}")

                        except Exception:

                            pass

                        # Normalize moves: accept either (er,ec) entries or full (sr,sc,er,ec)

                        all_moves_rc = []

                        raw_n = len(raw_moves) if raw_moves else 0

                        used_reasons = []

                        if raw_moves:

                            first = raw_moves[0]

                            if isinstance(first, (list, tuple)) and len(first) == 4:

                                all_moves_rc = list(raw_moves)

                            else:

                                # assume list of (er,ec)

                                all_moves_rc = [(r, c, er, ec) for (er,ec) in raw_moves]

                        # Apply two-stage must-enter filter if present

                        try:

                            if gs.two_stage_active and callable(must_filter):

                                before = list(all_moves_rc)

                                all_moves_rc = must_filter(all_moves_rc)

                                try:

                                    print(f"[MOVE LOG] must_enter filtered {before} -> {all_moves_rc}")

                                except Exception:

                                    pass

                                if len(all_moves_rc) < len(before):

                                    used_reasons.append('must-enter')

                        except Exception as e:

                            print(f"[MOVE LOG] must_enter filter exception: {e}")

                        # Convert to simple destination list for UI/selection

                        all_moves = [(er,ec) for (_sr,_sc,er,ec) in all_moves_rc]

                        # Pre-lock "stay-inside" rule: once you've entered, don't move outside the 8-8

                        try:

                            if gs.two_stage_active and active_color in (gs.final_a, gs.final_b) and gs.entered.get(active_color, False) and not gs.chess_lock:

                                before_stay = list(all_moves)

                                all_moves = [(er,ec) for (er,ec) in all_moves if in_chess_area(er,ec)]

                                if len(all_moves) < len(before_stay):

                                    used_reasons.append('stay')

                        except Exception:

                            pass

                        # Chess lock enforces staying inside the 8x8

                        if gs.chess_lock:

                            before_chess = list(all_moves)

                            all_moves = [(er,ec) for (er,ec) in all_moves if in_chess_area(er,ec)]

                            if VERBOSE_DEBUG:

                                try:

                                    print(f"[MOVE LOG] chess_lock filtered {before_chess} -> {all_moves}")

                                except Exception:

                                    pass

                            if len(all_moves) < len(before_chess):

                                used_reasons.append('chess-lock')

                        # Grace rules: filter out moves that intentionally give check to opponent when required

                        if gs.grace_active and opponent is not None:

                            nm = []

                            for (er,ec) in all_moves:

                                cap, ph, pk, eff = board_do_move(board, r,c,er,ec, simulate=True)

                                gives = king_in_check(board, opponent)

                                board_undo_move(board, r,c,er,ec, cap, ph, pk, eff)

                                if not gives:

                                    nm.append((er,ec))

                            all_moves = nm if nm else all_moves

                            if VERBOSE_DEBUG:

                                try:

                                    print(f"[MOVE LOG] grace filtered to {all_moves}")

                                except Exception:

                                    pass

                            # if grace removed any moves

                            if raw_n > 0 and len(all_moves) == 0:

                                used_reasons.append('grace')

                        try:

                            if VERBOSE_DEBUG:

                                print(f"[MOVE LOG] final candidate moves for ({r},{c}) = {all_moves}")

                        except Exception:

                            pass

                        if all_moves:

                            selected = (r,c)

                            moves = all_moves

                            # start drag visually on mouse-down when legal targets exist

                            try:

                                dragging = True

                                drag_start = (r, c)

                                drag_legal_targets = list(all_moves)

                                try:

                                    drag_mouse_pos = (mx, my)

                                except Exception:

                                    drag_mouse_pos = (0,0)

                            except Exception:

                                dragging = False

                                drag_start = None

                                drag_legal_targets = []

                        else:

                            # If no legal moves but we're in debug auto-select mode, still highlight

                            # the clicked friendly piece so we can confirm clicks are being received.

                            if AUTO_SELECT_DEBUG:

                                selected = (r,c)

                                moves = []

                            else:

                                selected, moves = None, []

                                # Show a brief reason banner when a piece has no moves

                                try:

                                    why = []

                                    why.extend(used_reasons)

                                    # If none matched, it could be king-safety or blocked

                                    if not why:

                                        if raw_n == 0:

                                            why.append('blocked')

                                        else:

                                            why.append('king-safety')

                                    piece_name = p.kind if p else '?'

                                    banner = f"No legal moves for {active_color.name} {piece_name}: {', '.join(why)}"

                                except Exception:

                                    pass

                    else:

                        selected = None; moves = []

                else:

                    if (r,c) in moves and not gs.freeze_advance:

                        # Save full game state to history (pure snapshot)

                        history.append(make_snapshot())

                        future.clear()

                        prev_forced_turn = forced_turn



                        pre_target = board.get(r, c)

                        if VERBOSE_DEBUG:

                            try:

                                print(f"[APPLY MOVE] attempting board_do_move from {selected} -> ({r},{c})")

                            except Exception:

                                pass

                        cap, ph, pk, eff = board_do_move(board, selected[0], selected[1], r, c)

                        if VERBOSE_DEBUG:

                            try:

                                print(f"[APPLY MOVE] board_do_move returned cap={cap}, ph={ph}, pk={pk}, eff={eff}")

                            except Exception:

                                pass

                        # Very robust verification: print existence/id/kind of piece at destination

                        if VERBOSE_DEBUG:

                            try:

                                after_piece = board.get(r, c)

                                print(f"[VERIFY MOVE] at ({r},{c}) exists={bool(after_piece)} id={id(after_piece) if after_piece else None} kind={(after_piece.kind if after_piece else None)}")

                            except Exception as e:

                                print(f"[VERIFY MOVE] exception checking board at ({r},{c}): {e}")

                        captured_piece = cap if cap else pre_target

                        mover_after = board.get(r, c)

                        if VERBOSE_DEBUG:

                            try:

                                print(f"[APPLY MOVE] mover_after at ({r},{c}) = {mover_after.kind if mover_after else None} color={(mover_after.color.name if mover_after else None)}")

                                # small snapshot of occupied squares for quick verification

                                print(f"[BOARD SNAPSHOT] {dump_board(board)}")

                            except Exception:

                                pass

                            promoted = bool(eff.get('promoted'))

                            if captured_piece: mat.on_capture(captured_piece)

                            # Prefer SAN from python-chess during chess-lock

                            if getattr(gs, 'chess_lock', False) and eff.get('san'):

                                moves_list.append(f"{GameState.turn_counter + 1}. {active_color.name}: {eff['san']}")

                            else:

                                moves_list.append(

                                    format_move_algebraic(GameState.turn_counter + 1, active_color,

                                                         pk if pk else (mover_after.kind if mover_after else '?'),

                                                         selected[0], selected[1], r, c, captured_piece, promoted)

                                )

                        try:

                            play_move_sound(captured_piece is not None)

                            move_pulse = {'square': (r, c), 'until': pygame.time.get_ticks() + 360}

                        except Exception:

                            pass



                        # Two-stage: mark entry if any of your pieces inside now

                        ensure_two_stage_state()

                        if gs.two_stage_active and active_color in (gs.final_a, gs.final_b):

                            if in_chess_area(r,c) or any(board.get(rr,cc) and board.get(rr,cc).color==active_color and in_chess_area(rr,cc)

                                                         for rr in range(BOARD_SIZE) for cc in range(BOARD_SIZE)):

                                if not gs.entered[active_color]:

                                    gs.entered[active_color] = True

                                    reduced = apply_queen_reduction_if_needed(active_color)

                                    if reduced:

                                        banner = f"{active_color.name}: reduced {len(reduced)} Queen(s) to Bishop(s) on entry."

                                other = two_stage_opponent(active_color)

                                if not DUEL_TELEPORT_ON_TWO and other and gs.entered[other] and not gs.grace_active:

                                    gs.grace_active = True

                                    gs.grace_turns_remaining = 2



                        # If both fully migrated (incl. kings), enable Chess lock

                        if not gs.chess_lock and both_fully_migrated_incl_kings(board):

                            gs.chess_lock = True



                        # After move: compute check victims and set priority if any

                        # === Turn baseline advance (one-move forced response rule) ===

                        # If this move was a normal turn (no forced_turn), advance seat by +1.

                        # If this move was a forced defense, advance baseline to the next seat after the defender.

                        try:

                            if prev_forced_turn is None:

                                turn_i = _advance_turn_index(turn_i + 1)

                            else:

                                # Move just played by 'active_color' as defender

                                turn_i = (TURN_ORDER.index(active_color) + 1) % 4

                        except Exception:

                            pass



                        victims = []

                        for col in board.alive_colors():

                            if col == active_color: continue

                            if king_in_check(board, col):

                                victims.append(col)

                        forced_turn = clockwise_from(active_color, victims) if victims else None



                        selected, moves = None, []

                        GameState.turn_counter += 1

                        gs.start_move_delay(MOVE_DELAY_MS)

                        # Apply Auto-Elim if enabled (only outside two-stage)

                        try:

                            if not gs.two_stage_active:

                                thr = int(getattr(gs, 'auto_elim_threshold', 18))

                                if thr > 0:

                                    elim_color = mat.should_eliminate(board, threshold=thr)

                                    if elim_color and board.find_king(elim_color) is not None:

                                        eliminate_color(board, gs, elim_color, reason="auto-elim", flash=True)

                        except Exception:

                            pass

                        # Force redraw and display update after each HUMAN move (click)

                        try:

                            screen.fill((24, 40, 64))

                            draw_board(

                                screen, board, selected, moves, font, active_color,

                                banner_text=banner, ui_state_text=ui_state_text,

                                flash_color=gs.elim_flash_color, flash_on=gs.elim_flash_on

                            )

                            draw_sidebar(screen, moves_list, sidebar_scroll, show_material, mat.captured_points, auto_elim_enabled, gs.two_stage_active, gs.grace_active)

                            pygame.display.flip()

                            pygame.event.pump()

                            pygame.time.wait(120)

                        except Exception:

                            pass

                        # Immediate end-of-game detection after a move (prevents extra moves and black frame)

                        try:

                            alive_now = board.alive_colors()

                            if len(alive_now) == 1:

                                winner = alive_now[0]

                                game_over = True

                                gs.freeze_advance = True

                                gs.post_move_delay_until = 0

                                gs.elim_flash_color = None

                                gs.chess_lock = True

                                forced_turn = None

                        except Exception:

                            pass



    # If a resize is pending and the events have settled, apply it once

        if resize_pending and pygame.time.get_ticks() - resize_last_event_ms >= RESIZE_DEBOUNCE_MS:

            try:

                # If using scaled mode, avoid recomputing logical sizes to reduce flicker

                use_scaled = bool(UI_STATE.get('scaled_mode', False)) if 'UI_STATE' in globals() else False

                if not use_scaled:

                    _compute_scaling()

                    _clear_caches_on_scale_change()

                # Resign pills are computed dynamically in draw; no static rebuild needed

                # Clear UI hover/pressed to avoid stuck visuals

                for k in list(UI_STATE.keys()):

                    if str(k).startswith('pressed_') or str(k).startswith('hover_'):

                        UI_STATE[k] = False

                # Full redraw once after resize settles

                screen.fill((24, 40, 64))

                active_col = TURN_ORDER[turn_i] if forced_turn is None else forced_turn

                draw_board(screen, board, selected, moves, font, active_col,

                           banner_text=banner, ui_state_text=ui_state_text,

                           flash_color=gs.elim_flash_color, flash_on=gs.elim_flash_on)

                draw_sidebar(screen, moves_list, sidebar_scroll, show_material, mat.captured_points,

                             auto_elim_enabled, gs.two_stage_active, gs.grace_active, game_over)

                pygame.display.flip()

                pygame.event.pump()

            except Exception:

                pass

            resize_pending = False



        # If resize still pending, skip heavy draw to avoid flicker; keep pumping events

        if resize_pending:

            pygame.event.pump()

            clock.tick(60)

            continue



        # Update timers

        gs.update_timers()



        # Flash cleanup (remove pieces when flash ends)

        if gs._pending_cleanup and gs._last_flash_color is not None and gs.elim_flash_color is None:

            skip_cleanup = False

            try:

                skip_cleanup = gs._last_flash_color in getattr(gs, '_elim_skip_cleanup', set())

            except Exception:

                skip_cleanup = False

            if not skip_cleanup:

                to_remove = gs._last_flash_color

                for rr in range(BOARD_SIZE):

                    for cc in range(BOARD_SIZE):

                        t = board.get(rr, cc)

                        if t and t.color == to_remove:

                            board.set(rr, cc, None)

                if forced_turn == gs._last_flash_color:

                    forced_turn = None

            try:

                getattr(gs, '_elim_skip_cleanup', set()).discard(gs._last_flash_color)

            except Exception:

                pass

            gs._pending_cleanup = False

            gs._last_flash_color = None



        # ======== AI / TURN PROGRESSION ========

        if not replay_mode and not gs.freeze_advance and not game_over and not getattr(gs, 'two_stage_pause', False):

            # Hold the game until user confirms Ready (lets them set HUM/AI first)

            if getattr(gs, 'waiting_ready', False):

                # Draw sidebar with READY prompt and skip progression

                try:

                    draw_sidebar(screen, moves_list, sidebar_scroll, show_material, mat.captured_points, auto_elim_enabled, gs.two_stage_active, gs.grace_active)

                    pygame.display.update(pygame.Rect(LOGICAL_W, 0, screen.get_size()[0]-LOGICAL_W, LOGICAL_H))

                except Exception:

                    pass

                clock.tick(60)

                continue

            ensure_two_stage_state()



            # Decrement grace after each full move when active

            if gs.two_stage_active and gs.grace_active and gs.grace_turns_remaining > 0:

                gs.grace_turns_remaining -= 1

                if gs.grace_turns_remaining == 0:

                    gs.grace_active = False



            active_color = TURN_ORDER[turn_i] if forced_turn is None else forced_turn



            # If it's a Human turn, gently hint what to do (only when banner is still the default build text)

            try:

                if active_color not in AI_PLAYERS and not replay_mode:

                    if banner is None or (isinstance(banner, str) and banner.startswith("Build:")):

                        banner = f"{active_color.name}: Human  drag a piece or toggle AI"

            except Exception:

                pass



            # Skip eliminated

            if board.find_king(active_color) is None:

                if forced_turn is not None:

                    forced_turn = None

                else:

                    turn_i = _advance_turn_index(turn_i + 1)

                continue



            legal = all_legal_moves_for_color(board, active_color)

            in_check_now = king_in_check(board, active_color)



            if not legal:

                if in_check_now:

                    eliminate_color(board, gs, active_color, reason="checkmate", flash=True)

                    # Advance to next alive seat after eliminated defender

                    try:

                        ni = (TURN_ORDER.index(active_color) + 1) % 4

                        # skip dead kings

                        for _ in range(4):

                            if board.find_king(TURN_ORDER[ni]) is not None:

                                break

                            ni = (ni + 1) % 4

                        turn_i = ni

                    except Exception:

                        pass

                    forced_turn = None

                else:

                    if forced_turn is not None:

                        forced_turn = None

                    else:

                        turn_i = _advance_turn_index(turn_i + 1)

                continue



            must_filter = must_enter_filter_for(board, active_color)

            grace_block = grace_blocks_check_for(active_color)

            opponent = two_stage_opponent(active_color)



            if active_color in AI_PLAYERS:

                # Allow short grace period when a seat switches to AI so human can toggle it back

                if not gs.ai_delay_applied.get(active_color, False):

                    gs.ai_delay_applied[active_color] = True

                    gs.start_move_delay(gs_pre_ai_delay_ms)

                    # skip actual AI selection this frame

                    continue

                if VERBOSE_DEBUG:

                    print(f"AI TURN: {active_color.name}")

                legal_moves = all_legal_moves_for_color(board, active_color)

                if VERBOSE_DEBUG:

                    print(f"Legal moves for {active_color.name}: {len(legal_moves)}")

                # Clear and prime AI debug text for this decision

                try:

                    globals()['ai_debug_text'] = []

                    if not gs.two_stage_active:

                        try:

                            tgt = _alive_next_color(board, active_color)

                            globals()['ai_debug_text'].append(f"target={tgt.name}")

                        except Exception:

                            pass

                    else:

                        globals()['ai_debug_text'].append("two-stage: target=finalist")

                except Exception:

                    pass

                # Use a budgeted fast decision to keep UI responsive; smart AI delegates to fast if needed

                pygame.event.pump()

                move = choose_ai_move(board, active_color, gs.two_stage_active, must_filter, grace_block, opponent)

                if VERBOSE_DEBUG:

                    print(f"AI chose move: {move}")

                if move is None:

                    if VERBOSE_DEBUG:

                        print(f"AI fallback: random move for {active_color.name}")

                    move = random.choice(legal)



                history.append(make_snapshot())

                future.clear()

                sr, sc, er, ec = move

                pre_target = board.get(er, ec)

                cap, ph, pk, eff = board_do_move(board, sr, sc, er, ec)

                victim = cap if cap else pre_target

                mover_after = board.get(er, ec)

                if VERBOSE_DEBUG:

                    try:

                        print(f"[AI APPLY MOVE] board_do_move returned cap={cap}, ph={ph}, pk={pk}, eff={eff}")

                    except Exception:

                        pass

                    try:

                        after_piece = board.get(er, ec)

                        print(f"[VERIFY AI MOVE] at ({er},{ec}) exists={bool(after_piece)} id={id(after_piece) if after_piece else None} kind={(after_piece.kind if after_piece else None)}")

                        print(f"[BOARD SNAPSHOT] {dump_board(board)}")

                    except Exception as e:

                        print(f"[VERIFY AI MOVE] exception checking board at ({er},{ec}): {e}")

                promoted = bool(eff.get('promoted'))

                if victim: mat.on_capture(victim)

                moves_list.append(

                    format_move_algebraic(GameState.turn_counter + 1, active_color,

                                         pk if pk else (mover_after.kind if mover_after else '?'),

                                         sr, sc, er, ec, victim, promoted)

                )

                # Compact console line for the move (coordinate style only)

                try:

                    if COMPACT_CONSOLE and not VERBOSE_DEBUG:

                        print(f"{GameState.turn_counter + 1}. {duel_to_chess_label(sr,sc)}-{duel_to_chess_label(er,ec)}")

                except Exception:

                    pass

                try:

                    play_move_sound(victim is not None)

                    move_pulse = {'square': (er, ec), 'until': pygame.time.get_ticks() + 360}

                except Exception:

                    pass



                # Two-stage entry bookkeeping & queen reduction

                ensure_two_stage_state()

                if gs.two_stage_active and active_color in (gs.final_a, gs.final_b):

                    if in_chess_area(er,ec) or any(board.get(rr,cc) and board.get(rr,cc).color==active_color and in_chess_area(rr,cc)

                                                   for rr in range(BOARD_SIZE) for cc in range(BOARD_SIZE)):

                        if not gs.entered[active_color]:

                            gs.entered[active_color] = True

                            reduced = apply_queen_reduction_if_needed(active_color)

                            if reduced:

                                banner = f"{active_color.name}: reduced {len(reduced)} Queen(s) to Bishop(s) on entry."

                        other = two_stage_opponent(active_color)

                        if not DUEL_TELEPORT_ON_TWO and other and gs.entered[other] and not gs.grace_active:

                            gs.grace_active = True

                            gs.grace_turns_remaining = 2



                # If both fully migrated (incl. kings), enable Chess lock

                if not gs.chess_lock and both_fully_migrated_incl_kings(board):

                    gs.chess_lock = True



                # Force redraw and display update after each AI move

                # Paint quickly so the UI stays responsive between AI choices

                screen.fill((24, 40, 64))

                draw_board(

                    screen, board, selected, moves, font, active_color,

                    banner_text=banner, ui_state_text=ui_state_text,

                    flash_color=gs.elim_flash_color, flash_on=gs.elim_flash_on

                )

                draw_sidebar(screen, moves_list, sidebar_scroll, show_material, mat.captured_points, auto_elim_enabled, gs.two_stage_active, gs.grace_active)

                pygame.display.flip()

                pygame.event.pump()

                pygame.time.wait(120)



                # Immediate end-of-game detection after AI move

                try:

                    alive_now = board.alive_colors()

                    if len(alive_now) == 1:

                        winner = alive_now[0]

                        game_over = True

                        gs.freeze_advance = True

                        gs.post_move_delay_until = 0

                        gs.elim_flash_color = None

                        gs.chess_lock = True

                        forced_turn = None

                except Exception:

                    pass



                # After move: set check-priority

                # === Turn baseline advance (one-move forced response rule) ===

                # If this move was a normal turn (no forced_turn), advance seat by +1.

                # If this move was a forced defense, advance baseline to the next seat after the defender.

                try:

                    if prev_forced_turn is None:

                        turn_i = _advance_turn_index(turn_i + 1)

                    else:

                        # Move just played by 'active_color' as defender

                        turn_i = (TURN_ORDER.index(active_color) + 1) % 4

                except Exception:

                    pass



                victims = []

                for col in board.alive_colors():

                    if col == active_color: continue

                    if king_in_check(board, col):

                        victims.append(col)

                forced_turn = clockwise_from(active_color, victims) if victims else None



                # Auto-elim 18 applies only if NOT in two-stage

                if not gs.two_stage_active:

                    try:

                        thr = int(getattr(gs, 'auto_elim_threshold', 18))

                    except Exception:

                        thr = 18

                    if thr > 0:

                        elim_color = mat.should_eliminate(board, threshold=thr)

                        if elim_color and board.find_king(elim_color) is not None:

                            eliminate_color(board, gs, elim_color, reason="auto-elim", flash=True)



                GameState.turn_counter += 1

                gs.start_move_delay(MOVE_DELAY_MS)



                # After AI moved, reset delay-flag for that color so it will apply next time

                try:

                    gs.ai_delay_applied[active_color] = False

                except Exception:

                    pass



            # Human turn waits



        # ===== Winner/draw checks (board stays visible) =====

        alive_kings = board.alive_colors()

        if len(alive_kings) == 1:

            winner = alive_kings[0]

            if not game_over:

                # Auto-save completed game once on first detection

                try:

                    save_game_record_if_ready(moves_list, winner_name=winner.name, duel_mode=bool(gs.chess_lock))

                except Exception:

                    pass

            game_over = True

            try:

                gs.last_winner = winner

            except Exception:

                pass

            gs.freeze_advance = True

            gs.post_move_delay_until = 0

            gs.elim_flash_color = None

            gs.chess_lock = True

            forced_turn = None



        # Also stop on draw by repetition

        try:

            if getattr(gs, '_draw_by_repetition', False):

                if not game_over:

                    try:

                        save_game_record_if_ready(moves_list, winner_name='DRAW', duel_mode=bool(gs.chess_lock))

                    except Exception:

                        pass

                game_over = True

                gs.freeze_advance = True

                gs.post_move_delay_until = 0

                gs.elim_flash_color = None

                gs.chess_lock = True

        except Exception:

            pass



        # (overlay is handled within game_over branch)



        # Robust per-frame draw: always clear to a visible background, attempt normal drawing

        try:

            screen.fill((24, 40, 64))

            draw_board(screen, board, selected, moves, font, TURN_ORDER[turn_i] if forced_turn is None else forced_turn,

                       banner_text=banner, ui_state_text=ui_state_text,

                       flash_color=gs.elim_flash_color, flash_on=gs.elim_flash_on)

            draw_sidebar(screen, moves_list, sidebar_scroll, show_material, mat.captured_points, auto_elim_enabled, gs.two_stage_active, gs.grace_active, game_over)

            # Draw transient click indicator (helps confirm clicks on-screen) and move pulse

            try:

                now = pygame.time.get_ticks()

                if click_indicator is not None:

                    cx, cy, until = click_indicator

                    if now < until:

                        # ripple ring that fades

                        life = max(0, until - now)

                        frac = life / CLICK_INDICATOR_MS

                        rad = int(6 + frac * 10)

                        alpha = int(140 * frac)

                        ring = pygame.Surface((rad*2+2, rad*2+2), pygame.SRCALPHA)

                        pygame.draw.circle(ring, (255,255,255, alpha), (rad+1, rad+1), rad, 2)

                        screen.blit(ring, (cx - rad - 1, cy - rad - 1))

                    else:

                        click_indicator = None

                # Move pulse on destination square

                if move_pulse is not None:

                    until = move_pulse.get('until', 0)

                    sq = move_pulse.get('square')

                    if sq is not None and now < until:

                        mr, mc = sq

                        life = max(0, until - now)

                        frac = life / 320.0

                        a = int(120 * frac)

                        glow = pygame.Surface((SQUARE, SQUARE), pygame.SRCALPHA)

                        pygame.draw.rect(glow, (120, 220, 160, a), (4,4,SQUARE-8,SQUARE-8), 2)

                        screen.blit(glow, (mc*SQUARE, mr*SQUARE))

                    else:

                        move_pulse = None

            except Exception:

                pass

        except Exception as e:

            # On draw failure, show a simple diagnostic overlay so the window is not blank

            try:

                screen.fill((90, 20, 20))

                err_font = pygame.font.SysFont('Arial', 20)

                lines = [f'Draw error: {str(e)}', 'Check console for traceback. Press B to dump state.']

                for i, ln in enumerate(lines):

                    surf = err_font.render(ln, True, (255,255,255))

                    screen.blit(surf, (20, 20 + i*26))

            except Exception:

                # If even diagnostics fail, fall back to a solid color only

                screen.fill((120, 20, 20))

        finally:

            pygame.display.flip()

            clock.tick(60)



    pygame.quit()

    # Avoid relying on sys.exit() here to prevent rare UnboundLocalError reports in some environments

    return



HEADLESS_SCRIPT = None

HEADLESS_RESULTS = None

HEADLESS_ENABLED = False



if __name__ == "__main__":

    # Placeholder for self-test hook; replaced during --self-test setup

    def _st_activate_if_needed(*_args, **_kwargs):

        return None

    # Self-test entry: run headless checks when invoked with --self-test

    if any(arg.startswith("--self-test") for arg in sys.argv[1:]):

        try:

            # Self-test suite wired here to keep tests in the Golden file
            globals()['HEADLESS_ENABLED'] = True

            import random as _rnd



            # Parse selector: --self-test or --self-test=name or --self-test=all

            selector = None

            for a in sys.argv[1:]:

                if a.startswith("--self-test"):

                    if "=" in a:

                        selector = a.split("=",1)[1].strip().lower()

                    else:

                        selector = "ai3"  # default

                    break



            # Minimal consolidated install for self-test runs (ensures behavior before bottom install executes)

            def _install_selftest_two_player_consolidation():

                _ST_ORIG_LEGAL = globals().get('legal_moves_for_piece')

                _ST_ORIG_DO = globals().get('board_do_move')

                def _st_in8(rr, cc):

                    return CH_MIN <= rr <= CH_MAX and CH_MIN <= cc <= CH_MAX

                def _st_alive_effective(bd: 'Board', state: 'GameState'):

                    alive = bd.alive_colors()

                    flashing = getattr(state, 'elim_flash_color', None)

                    return [c for c in alive if c != flashing]

                def _st_purge(bd: 'Board'):

                    for rr in range(BOARD_SIZE):

                        for cc in range(BOARD_SIZE):

                            p = bd.get(rr, cc)

                            if p and p.kind != 'K' and not _st_in8(rr, cc):

                                bd.set(rr, cc, None)

                def _st_activate_if_needed(bd: 'Board', state: 'GameState'):

                    eff = _st_alive_effective(bd, state)

                    if len(eff) == 2:

                        if not getattr(state, '_tp_consolidated_done', False):

                            # First-time activation: purge, set finals, lock, and pause+freeze

                            _st_purge(bd)

                            state.two_stage_active = True

                            state.final_a, state.final_b = eff[0], eff[1]

                            state.chess_lock = True

                            state.grace_active = False

                            state.grace_turns_remaining = 0

                            # One-time inspection pause and freeze

                            try:

                                state.freeze_advance = True

                                state.two_stage_pause = True

                            except Exception:

                                pass

                            # Mark as entered/reduced so legacy reducers won't fire

                            state.entered[state.final_a] = True

                            state.entered[state.final_b] = True

                            state.reduced_applied[state.final_a] = True

                            state.reduced_applied[state.final_b] = True

                            state._tp_consolidated_done = True

                        else:

                            # Already active: enforce consolidated lock without reapplying pause

                            if getattr(state, 'final_a', None) is None or getattr(state, 'final_b', None) is None:

                                try:

                                    state.final_a, state.final_b = eff[0], eff[1]

                                except Exception:

                                    pass

                            _st_purge(bd)

                            state.chess_lock = True

                def _st_legal(board: 'Board', r: int, c: int, active_color: 'PColor'=None):

                    base = _ST_ORIG_LEGAL(board, r, c, active_color)

                    # Normalize to list of 4-tuples (sr,sc,er,ec) regardless of source shape

                    base_norm = []

                    if base:

                        first = base[0]

                        if isinstance(first, (list, tuple)) and len(first) == 4:

                            base_norm = list(base)

                        else:

                            # assume sequence of (er,ec) pairs

                            base_norm = [(r, c, er, ec) for (er, ec) in base]

                    else:

                        base_norm = []

                    state = globals().get('gs')

                    if not getattr(state, 'two_stage_active', False):

                        return base_norm

                    p = board.get(r, c)

                    if not p:

                        return base_norm

                    ac = p.color if active_color is None else active_color

                    # Freeze-inside rule: if this color has any piece outside 8-8,

                    # pieces already inside cannot move until entry is complete.

                    def _st_color_has_outside(bd: 'Board', col: 'PColor') -> bool:

                        for rr in range(BOARD_SIZE):

                            for cc in range(BOARD_SIZE):

                                qq = bd.get(rr, cc)

                                if qq and qq.color == col and not _st_in8(rr, cc):

                                    return True

                        return False

                    if _st_color_has_outside(board, ac) and _st_in8(r, c):

                        return []

                    # Non-king: stay inside 8x8

                    if p.kind != 'K':

                        return [(sr, sc, er, ec) for (sr, sc, er, ec) in base_norm if _st_in8(er, ec)]

                    # King outside: do not worsen distance; prefer strictly closer if present

                    if not _st_in8(r, c):

                        cur = dist_to_chess(r, c)

                        closer = [(sr, sc, er, ec) for (sr, sc, er, ec) in base_norm if dist_to_chess(er, ec) < cur]

                        if closer:

                            return closer

                        return [(sr, sc, er, ec) for (sr, sc, er, ec) in base_norm if dist_to_chess(er, ec) == cur]

                    # King inside: stay inside

                    return [(sr, sc, er, ec) for (sr, sc, er, ec) in base_norm if _st_in8(er, ec)]

                def _st_do(board: 'Board', sr, sc, er, ec, simulate=False):

                    res = _ST_ORIG_DO(board, sr, sc, er, ec, simulate)

                    if not simulate:

                        try:

                            _st_activate_if_needed(board, globals().get('gs'))

                        except Exception:

                            pass

                    return res

                globals()['legal_moves_for_piece'] = _st_legal

                globals()['board_do_move'] = _st_do

                # Expose the activator in module scope so tests can call it directly

                globals()['_st_activate_if_needed'] = _st_activate_if_needed



            _install_selftest_two_player_consolidation()



            def _clear_board(bd: 'Board'):

                for _r in range(14):

                    for _c in range(14):

                        bd.set(_r, _c, None)



            def _setup_3p():

                bd = Board()

                _clear_board(bd)

                bd.set(6, 3, Piece('K', PColor.WHITE))

                bd.set(3, 6, Piece('K', PColor.GREY))

                bd.set(10, 10, Piece('K', PColor.BLACK))

                bd.set(8, 3, Piece('Q', PColor.WHITE))

                bd.set(2, 8, Piece('R', PColor.GREY))

                bd.set(9, 8, Piece('R', PColor.BLACK))

                bd.set(5, 6, Piece('P', PColor.GREY))

                return bd



            def _alive_next(bd: 'Board', me: 'PColor'):

                idx = TURN_ORDER.index(me)

                for i in range(1,5):

                    nxt = TURN_ORDER[(idx + i) % 4]

                    if bd.find_king(nxt) is not None:

                        return nxt

                return None



            def _pref_cap_left(bd: 'Board', me: 'PColor', mv):

                sr, sc, er, ec = mv

                cap, ph, pk, eff = board_do_move(bd, sr, sc, er, ec, simulate=True)

                ok = (cap is not None and cap.color == _alive_next(bd, me))

                board_undo_move(bd, sr, sc, er, ec, cap, ph, pk, eff)

                return ok



            # Test: Pawn promotions occur on the inside 8x8 edges for all four colors

            def _test_promotion_inside_edges():

                # Set up an empty board and place one pawn per color one step before its

                # respective inside-edge promotion square; move onto the edge and assert promotion.

                _reset_state()

                b = Board()

                _clear_board(b)

                # Cases: (color_name, start(r,c), end(r,c))

                cases = [

                    (PColor.WHITE, (CH_MIN+1, CH_MIN+4), (CH_MIN,   CH_MIN+4)),  # promote on row CH_MIN (far for WHITE)

                    (PColor.BLACK, (CH_MAX-1, CH_MIN+3), (CH_MAX,   CH_MIN+3)),  # promote on row CH_MAX (far for BLACK)

                    (PColor.GREY,  (CH_MIN+3, CH_MAX-1), (CH_MIN+3, CH_MAX    )),# promote on col CH_MAX (far for GREY)

                    (PColor.PINK,  (CH_MIN+4, CH_MIN+1), (CH_MIN+4, CH_MIN    )),# promote on col CH_MIN (far for PINK)

                ]

                for col, (sr, sc), (er, ec) in cases:

                    b.set(sr, sc, Piece('P', col))

                    cap, ph, pk, eff = board_do_move(b, sr, sc, er, ec, simulate=False)

                    p = b.get(er, ec)

                    if p is None or p.kind != 'Q' or not bool(eff.get('promoted')):

                        print(f"[SELF-TEST FAIL] promo_edges: {col.name} pawn did not promote at {(er,ec)}; got={None if p is None else p.kind}, effects={eff}")

                        return 2

                print('[SELF-TEST PASS] promo_edges: all colors promote on inside edges')

                return 0



            # Test: AI left-neighbor preference in 3-player stage

            def _test_ai3():

                _rnd.seed(0)

                BD = _setup_3p()

                me = PColor.WHITE

                mv = choose_ai_move(BD, me, two_stage=False, must_enter_filter=None, grace_block_fn=None, opponent=None)

                if mv is None:

                    print('[SELF-TEST FAIL] AI returned no move')

                    return 2

                print(f'[SELF-TEST ai3] chosen move: {mv}')

                left = _alive_next(BD, me)

                sr, sc, er, ec = mv

                cap, ph, pk, eff = board_do_move(BD, sr, sc, er, ec, simulate=True)

                give_left = king_in_check(BD, left)

                others = [c for c in TURN_ORDER if c not in (me, left) and BD.find_king(c) is not None]

                give_other = any(king_in_check(BD, oc) for oc in others)

                board_undo_move(BD, sr, sc, er, ec, cap, ph, pk, eff)

                if _pref_cap_left(BD, me, mv) or (give_left and not give_other):

                    print(f'[SELF-TEST PASS] ai3: Left-target pressure ok (left={left.name}).')

                    return 0

                print(f'[SELF-TEST WARN] ai3: Did not prefer left neighbor (left={left.name}). Move={mv}')

                return 1



            # Helpers to reset global game state for two-player tests

            def _reset_state():

                globals()['gs'] = GameState()



            # Test: Activate two-player, purge non-kings off 8x8, lock on

            def _test_tp_activate_purge_lock():

                _reset_state()

                b = Board()

                _clear_board(b)

                # Kings only alive (two colors)

                b.set(11, 6, Piece('K', PColor.WHITE))  # outside 8x8

                b.set(0, 6, Piece('K', PColor.BLACK))   # outside 8x8

                # Non-king pieces outside 8x8 that must be purged on activation

                b.set(1, 1, Piece('R', PColor.WHITE))

                b.set(10, 10, Piece('B', PColor.BLACK))

                # Trigger activation via a real move

                cap, ph, pk, eff = board_do_move(b, 11, 6, 10, 6, simulate=False)

                # Ensure activation is processed

                try:

                    _st_activate_if_needed(b, gs)

                except Exception:

                    pass

                # Diagnostics

                try:

                    print(f"[DEBUG tp_activate] two_stage_active={getattr(gs,'two_stage_active',None)} chess_lock={getattr(gs,'chess_lock',None)} finals=({getattr(gs,'final_a',None)}, {getattr(gs,'final_b',None)})")

                except Exception:

                    pass

                # Assert consolidated flags

                if not (gs.two_stage_active and gs.chess_lock):

                    print('[SELF-TEST FAIL] tp_activate: two_stage or lock not enabled')

                    return 2

                # Purge check

                if b.get(1,1) is not None or b.get(10,10) is not None:

                    print('[SELF-TEST FAIL] tp_activate: purge did not remove off-8x8 non-kings')

                    return 2

                print('[SELF-TEST PASS] tp_activate: activated, purged, locked')

                return 0



            # Test: Non-king moves must stay inside 8x8 once locked

            def _test_tp_nonking_stay_inside():

                _reset_state()

                b = Board()

                _clear_board(b)

                # Place both kings inside to simplify

                b.set(5, 5, Piece('K', PColor.WHITE))

                b.set(6, 6, Piece('K', PColor.BLACK))

                # Inside rook

                b.set(5, 6, Piece('R', PColor.WHITE))

                # Activate via move

                board_do_move(b, 5, 5, 5, 4, simulate=False)

                try:

                    _st_activate_if_needed(b, gs)

                except Exception:

                    pass

                # Legal moves for rook must end inside 8x8

                moves = legal_moves_for_piece(b, 5, 6, PColor.WHITE)

                if not moves:

                    print('[SELF-TEST FAIL] tp_nonking: no moves for rook')

                    return 2

                for mv in moves:

                    if isinstance(mv, (list, tuple)) and len(mv) >= 4:

                        er, ec = mv[2], mv[3]

                    else:

                        # assume (er,ec)

                        er, ec = mv[-2], mv[-1]

                    if not in_chess_area(er, ec):

                        print('[SELF-TEST FAIL] tp_nonking: found move ending outside 8x8')

                        return 2

                print('[SELF-TEST PASS] tp_nonking: all rook moves stay inside 8x8')

                return 0



            # Test: King outside must not increase distance to 8x8 under lock

            def _test_tp_king_must_approach():

                _reset_state()

                b = Board()

                _clear_board(b)

                # Place one king far outside, opponent king anywhere

                b.set(11, 0, Piece('K', PColor.WHITE))

                b.set(5, 5, Piece('K', PColor.BLACK))

                # Activate via opponent move (so rules apply)

                board_do_move(b, 5, 5, 5, 4, simulate=False)

                try:

                    _st_activate_if_needed(b, gs)

                except Exception:

                    pass

                start = dist_to_chess(11, 0)

                moves = legal_moves_for_piece(b, 11, 0, PColor.WHITE)

                if not moves:

                    print('[SELF-TEST FAIL] tp_king: no legal king moves')

                    return 2

                dists = []

                for mv in moves:

                    if isinstance(mv, (list, tuple)) and len(mv) >= 4:

                        er, ec = mv[2], mv[3]

                    else:

                        er, ec = mv[-2], mv[-1]

                    d = dist_to_chess(er, ec)

                    dists.append(d)

                    if d > start:

                        print('[SELF-TEST FAIL] tp_king: king move increases distance to 8x8')

                        return 2

                if min(dists) > start:

                    print('[SELF-TEST WARN] tp_king: did not find any move reducing distance')

                    return 1

                print('[SELF-TEST PASS] tp_king: all moves non-worsening; some reduce distance')

                return 0



            # Test: Two-player activation sets a one-time pause and freeze_advance

            def _test_tp_pause_once():

                _reset_state()

                b = Board()

                _clear_board(b)

                # Only two kings alive to trigger activation

                b.set(11, 6, Piece('K', PColor.WHITE))

                b.set(0, 6, Piece('K', PColor.BLACK))

                # Make a real move to trigger activation path

                board_do_move(b, 11, 6, 10, 6, simulate=False)

                try:

                    _st_activate_if_needed(b, gs)

                except Exception:

                    pass

                # Expect pause + freeze on first activation

                if not getattr(gs, 'two_stage_active', False):

                    print('[SELF-TEST FAIL] tp_pause: two_stage_active not set')

                    return 2

                if not getattr(gs, 'two_stage_pause', False):

                    print('[SELF-TEST FAIL] tp_pause: pause not set on activation')

                    return 2

                if not getattr(gs, 'freeze_advance', False):

                    print('[SELF-TEST FAIL] tp_pause: freeze_advance not set on activation')

                    return 2

                # Simulate user pressing Resume, then ensure pause isn't re-applied on subsequent checks

                gs.two_stage_pause = False

                try:

                    _st_activate_if_needed(b, gs)

                except Exception:

                    pass

                if getattr(gs, 'two_stage_pause', False):

                    print('[SELF-TEST FAIL] tp_pause: pause re-applied after resume')

                    return 2

                print('[SELF-TEST PASS] tp_pause: pause set once and not re-applied')

                return 0



            # Test: Corner blocks remain contiguous 2-2 after view transforms

            def _test_corners_view():

                # Verify for each seat view that each color's home 2-2 corner

                # transforms to a contiguous 2-2 block located at a board corner.

                seats = ['WHITE','GREY','BLACK','PINK']

                # Board corners in transformed coords (use tuples to avoid set-of-set issues)

                allowed_rows = [(0,1), (BOARD_SIZE-2, BOARD_SIZE-1)]

                allowed_cols = [(0,1), (BOARD_SIZE-2, BOARD_SIZE-1)]

                for seat in seats:

                    UI_STATE['view_seat'] = seat

                    for pcol, (r0, c0) in CORNER_RECTS.items():

                        cells = []

                        for dr in (0,1):

                            for dc in (0,1):

                                rr, cc = _transform_rc_for_view(r0+dr, c0+dc)

                                cells.append((rr, cc))

                        uniq = set(cells)

                        if len(uniq) != 4:

                            print(f"[SELF-TEST FAIL] corners_view: non-unique cells for seat={seat} color={pcol.name}: {uniq}")

                            return 2

                        rs = sorted({r for r, _ in uniq})

                        cs = sorted({c for _, c in uniq})

                        # Must be two consecutive rows and two consecutive cols

                        if not (len(rs) == 2 and rs[1] - rs[0] == 1 and len(cs) == 2 and cs[1] - cs[0] == 1):

                            print(f"[SELF-TEST FAIL] corners_view: not contiguous 2x2 for seat={seat} color={pcol.name}: rows={rs} cols={cs}")

                            return 2

                        # Must be at a board corner (top/bottom and left/right 2 rows/cols)

                        if tuple(rs) not in allowed_rows:

                            print(f"[SELF-TEST FAIL] corners_view: rows not at board edge for seat={seat} color={pcol.name}: rows={rs}")

                            return 2

                        if tuple(cs) not in allowed_cols:

                            print(f"[SELF-TEST FAIL] corners_view: cols not at board edge for seat={seat} color={pcol.name}: cols={cs}")

                            return 2

                        # When the seat matches the color, that color's corner should be at bottom rows

                        if seat == pcol.name:

                            if rs != [BOARD_SIZE-2, BOARD_SIZE-1]:

                                print(f"[SELF-TEST FAIL] corners_view: seat={seat} expects {pcol.name} corner at bottom rows, got rows={rs}")

                                return 2

                print('[SELF-TEST PASS] corners_view: all seats and colors contiguous at corners')

                return 0



            # Test: Freeze inside pieces until own king enters 8-8 (for all colors)

            def _test_freeze_inside_all():

                def _setup(color: 'PColor'):

                    _reset_state()

                    b = Board(); _clear_board(b)

                    # Place opponent king inside to ensure two-player activation can proceed

                    opp = PColor.BLACK if color != PColor.BLACK else PColor.WHITE

                    b.set(5, 5, Piece('K', opp))

                    # Place this color's king just outside with a one-step entry available

                    # and one rook inside 8-8

                    if color == PColor.WHITE:

                        b.set(10, 6, Piece('K', color))   # outside (row 10)

                        b.set(5, 6, Piece('R', color))    # inside

                    elif color == PColor.BLACK:

                        b.set(1, 6, Piece('K', color))    # outside (row 1)

                        b.set(5, 6, Piece('R', color))    # inside

                    elif color == PColor.GREY:

                        b.set(6, 1, Piece('K', color))    # outside (col 1)

                        b.set(6, 6, Piece('R', color))    # inside

                    elif color == PColor.PINK:

                        b.set(6, 10, Piece('K', color))   # outside (col 10)

                        b.set(6, 6, Piece('R', color))    # inside

                    # Make a real move to trigger activation path and then enforce activation

                    # Move opponent king one square (legal in empty board)

                    try:

                        ok = legal_moves_for_piece(b, 5, 5, opp)

                        if ok:

                            sr, sc, er, ec = ok[0]

                            board_do_move(b, sr, sc, er, ec, simulate=False)

                    except Exception:

                        pass

                    try:

                        _st_activate_if_needed(b, gs)

                    except Exception:

                        pass

                    return b



                # For each color: inside rook must be frozen while king is outside; once king enters, rook should have moves

                colors = [PColor.WHITE, PColor.GREY, PColor.BLACK, PColor.PINK]

                for col in colors:

                    b = _setup(col)

                    # Locate the inside rook and verify no moves

                    rook_pos = None

                    for rr in range(BOARD_SIZE):

                        for cc in range(BOARD_SIZE):

                            p = b.get(rr, cc)

                            if p and p.color == col and p.kind == 'R' and in_chess_area(rr, cc):

                                rook_pos = (rr, cc); break

                        if rook_pos: break

                    if not rook_pos:

                        print(f"[SELF-TEST FAIL] freeze_inside: no inside rook for {col.name}")

                        return 2

                    rm = legal_moves_for_piece(b, rook_pos[0], rook_pos[1], col)

                    if rm:

                        print(f"[SELF-TEST FAIL] freeze_inside: rook had moves while king outside for {col.name}")

                        return 2

                    # Move king one step into the 8-8

                    # Find king position

                    kp = None

                    for rr in range(BOARD_SIZE):

                        for cc in range(BOARD_SIZE):

                            p = b.get(rr, cc)

                            if p and p.color == col and p.kind == 'K':

                                kp = (rr, cc); break

                        if kp: break

                    if not kp:

                        print(f"[SELF-TEST FAIL] freeze_inside: no king for {col.name}")

                        return 2

                    km = legal_moves_for_piece(b, kp[0], kp[1], col)

                    # Pick a move that enters 8-8

                    enter = None

                    for (sr, sc, er, ec) in km:

                        if in_chess_area(er, ec):

                            enter = (sr, sc, er, ec); break

                    if not enter:

                        print(f"[SELF-TEST FAIL] freeze_inside: no entering move for king {col.name}")

                        return 2

                    board_do_move(b, *enter, simulate=False)

                    try:

                        _st_activate_if_needed(b, gs)

                    except Exception:

                        pass

                    # Now rook should have legal moves

                    rm2 = legal_moves_for_piece(b, rook_pos[0], rook_pos[1], col)

                    if not rm2:

                        print(f"[SELF-TEST FAIL] freeze_inside: rook still frozen after king entry for {col.name}")

                        return 2

                print('[SELF-TEST PASS] freeze_inside: all colors froze inside pieces until king entry')

                return 0



            # Test: Rules exporter writes a non-empty TXT (and PDF if lib available)

            def _test_rules_exporter():

                _reset_state()

                # Import exporter entry point

                try:

                    sys.path.append(os.path.join(SCRIPT_DIR, 'tools'))

                    from export_rules import main as export_rules_main  # type: ignore

                except Exception as e:

                    try:

                        from tools.export_rules import main as export_rules_main  # type: ignore

                    except Exception as ee:

                        print(f"[SELF-TEST FAIL] rules_exporter: cannot import tool: {e} / {ee}")

                        return 2

                out_dir = os.path.join(SCRIPT_DIR, 'docs')

                rc = export_rules_main(['--out', out_dir, '--quiet'])

                # Check TXT

                txt_path = os.path.join(out_dir, 'rules.txt')

                if not os.path.exists(txt_path):

                    print('[SELF-TEST FAIL] rules_exporter: rules.txt not created')

                    return 2

                try:

                    if os.path.getsize(txt_path) <= 0:

                        print('[SELF-TEST FAIL] rules_exporter: rules.txt is empty')

                        return 2

                    # Verify required tail line is last

                    REQUIRED_TAIL = 'To prevent unauthorized reproduction a minor false rule has been included in this limited edition.'

                    with open(txt_path, 'r', encoding='utf-8') as f:

                        lines = [ln.rstrip() for ln in f.readlines() if ln.strip() != '']

                    if not lines or lines[-1] != REQUIRED_TAIL:

                        print('[SELF-TEST FAIL] rules_exporter: required tail not last line')

                        return 2

                except Exception as e:

                    print(f"[SELF-TEST FAIL] rules_exporter: cannot stat rules.txt: {e}")

                    return 2

                # PDF is optional; if present, must be non-empty

                pdf_path = os.path.join(out_dir, 'rules.pdf')

                if os.path.exists(pdf_path):

                    try:

                        if os.path.getsize(pdf_path) <= 0:

                            print('[SELF-TEST FAIL] rules_exporter: rules.pdf exists but is empty')

                            return 2

                    except Exception as e:

                        print(f"[SELF-TEST FAIL] rules_exporter: cannot stat rules.pdf: {e}")

                        return 2

                print('[SELF-TEST PASS] rules_exporter: rules.txt OK; rules.pdf OK or skipped')

                # Treat rc==0 or rc==1 (partial) as success for our purposes

                return 0 if rc in (0,1) else 2



            def _test_short_castling_basic():

                _reset_state()

                b = Board()

                # Clear pieces between WHITE king and rooks to allow both sides

                # Back rank (row 11): remove N,B,Q between a/h rooks and king at col 6

                for cc in range(2, 10):

                    q = b.get(11, cc)

                    if q and q.color == PColor.WHITE and q.kind in ('N','B','Q'):

                        b.set(11, cc, None)

                # Clear pawns in front to avoid simple attacks

                for cc in range(2, 10):

                    b.set(10, cc, None)

                mv = legal_moves_for_piece(b, 11, 6, PColor.WHITE)

                dests = {(er, ec) for (_, _, er, ec) in mv}

                ok = ((11, 8) in dests) or ((11, 4) in dests)

                print('[SELF-TEST PASS] short_castling_basic' if ok else '[SELF-TEST FAIL] short_castling_basic')

                return 0 if ok else 2



            def _test_buttons_headless():

                import os

                from pathlib import Path

                os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

                rules_dir = Path(SCRIPT_DIR) / "docs"

                try:

                    rules_dir.mkdir(parents=True, exist_ok=True)

                except Exception:

                    pass

                export_path = Path(SCRIPT_DIR) / "bishops_moves.txt"

                rules_txt = rules_dir / "rules.txt"

                try:

                    if export_path.exists():

                        export_path.unlink()

                except Exception:

                    pass

                startfile_calls: list = []

                original_startfile = getattr(os, "startfile", None)

                if original_startfile is not None:

                    def _fake_startfile(path, *args, **kwargs):

                        startfile_calls.append(path)

                        return None

                    os.startfile = _fake_startfile

                globals().pop('_HEADLESS_STATE', None)

                globals()['HEADLESS_SCRIPT'] = None

                globals()['HEADLESS_RESULTS'] = None

                plan = [

                    {

                        'name': 'Verify turn rotation',

                        'capture': lambda env: [col.name for col in TURN_ORDER],

                        'check': lambda env, prev: (

                            prev == ['WHITE', 'GREY', 'BLACK', 'PINK'],

                            f"TURN_ORDER unexpected: {prev}"

                        )

                    },

                ]

                globals()['HEADLESS_SCRIPT'] = plan

                try:

                    main()

                except Exception as exc:

                    import traceback

                    traceback.print_exc()

                    raise

                finally:

                    if original_startfile is not None:

                        os.startfile = original_startfile

                res = globals().get('HEADLESS_RESULTS') or {}

                for entry in res.get('log', []):

                    print(f"[SELF-TEST buttons] {entry}")

                fails = list(res.get('fails', []))

                if original_startfile is not None and not startfile_calls:

                    print("[SELF-TEST buttons] startfile not invoked (headless skip)")

                if export_path.exists():

                    try:

                        export_size = export_path.stat().st_size

                    except Exception as exc:

                        fails.append(f"btn_export: cannot stat bishops_moves.txt ({exc})")

                    else:

                        if export_size <= 0:

                            fails.append("btn_export: bishops_moves.txt empty")

                        else:

                            print(f"[SELF-TEST buttons] bishops_moves.txt size={export_size}")

                else:

                    fails.append("btn_export: bishops_moves.txt missing")

                if rules_txt.exists():

                    try:

                        rules_size = rules_txt.stat().st_size

                    except Exception as exc:

                        fails.append(f"btn_rules_pdf: cannot stat rules.txt ({exc})")

                    else:

                        if rules_size <= 0:

                            fails.append("btn_rules_pdf: rules.txt empty")

                        else:

                            print(f"[SELF-TEST buttons] rules.txt size={rules_size}")

                else:

                    fails.append("btn_rules_pdf: rules.txt missing")

                if fails:

                    for msg in fails:

                        print(f"[SELF-TEST FAIL] buttons: {msg}")

                    return 2

                print('[SELF-TEST PASS] buttons: all sidebar controls exercised headlessly')

                return 0



            tests = {

                'buttons': _test_buttons_headless,

                'ai3': _test_ai3,

                'tp_activate': _test_tp_activate_purge_lock,

                'tp_nonking': _test_tp_nonking_stay_inside,

                'tp_king': _test_tp_king_must_approach,

                'tp_pause': _test_tp_pause_once,

                'corners_view': _test_corners_view,

                'freeze_inside': _test_freeze_inside_all,

                'promo_edges': _test_promotion_inside_edges,

                'short_castle': _test_short_castling_basic,

                'rules_exporter': _test_rules_exporter,

                'all': None,

            }



            if selector == 'all':

                # Run the full ordered suite

                order = ['corners_view', 'ai3', 'tp_activate', 'tp_nonking', 'tp_king', 'tp_pause', 'freeze_inside', 'promo_edges', 'short_castle', 'rules_exporter']

                results = []

                codes = []

                for name in order:

                    try:

                        code = tests[name]()

                    except SystemExit as _e:

                        raise

                    except Exception as e:

                        print(f"[SELF-TEST EXC] {name}: {e}")

                        code = 3

                    codes.append(code)

                    results.append((name, code))

                # Write results summary to docs

                try:

                    out_dir = os.path.join(SCRIPT_DIR, 'docs')

                    os.makedirs(out_dir, exist_ok=True)

                    path = os.path.join(out_dir, 'selftest_last.txt')

                    with open(path, 'w', encoding='utf-8') as f:

                        ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        f.write(f"Self-test run: {ts}\n")

                        for name, code in results:

                            status = 'PASS' if code == 0 else ('WARN' if code == 1 else ('FAIL' if code == 2 else 'EXC'))

                            f.write(f"{name}: {status} (code={code})\n")

                        worst = max(codes) if codes else 3

                        overall = 'PASS' if worst == 0 else ('WARN' if worst == 1 else ('FAIL' if worst == 2 else 'EXC'))

                        f.write(f"OVERALL: {overall} (worst={worst})\n")

                except Exception:

                    pass

                worst = max(codes) if codes else 3

                sys.exit(worst)

            else:

                # Single test (or default)

                if selector is None:

                    selector = 'ai3'

                if selector not in tests or tests[selector] is None:

                    print(f"[SELF-TEST] Unknown selector: {selector}")

                    sys.exit(3)

                try:

                    rc = tests[selector]()

                except SystemExit as _e:

                    raise

                except Exception as e:

                    print(f"[SELF-TEST EXC] {selector}: {e}")

                    rc = 3

                # Single test summary

                try:

                    out_dir = os.path.join(SCRIPT_DIR, 'docs')

                    os.makedirs(out_dir, exist_ok=True)

                    path = os.path.join(out_dir, 'selftest_last.txt')

                    with open(path, 'w', encoding='utf-8') as f:

                        ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        status = 'PASS' if rc == 0 else ('WARN' if rc == 1 else ('FAIL' if rc == 2 else 'EXC'))

                        f.write(f"Self-test run: {ts}\n{selector}: {status} (code={rc})\nOVERALL: {status} (worst={rc})\n")

                except Exception:

                    pass

                sys.exit(rc)

        except SystemExit as _e:

            raise

        except Exception:

            import traceback

            traceback.print_exc()

            sys.exit(3)

    # On-demand export of rules PDF and exit

    if '--export-rules-pdf' in sys.argv[1:]:

        try:

            # Attempt relative import first when launched from repo root

            sys.path.append(os.path.join(SCRIPT_DIR, 'tools'))

            from export_rules import main as export_rules_main  # type: ignore

        except Exception:

            try:

                from tools.export_rules import main as export_rules_main  # type: ignore

            except Exception as _e:

                print('[rules] cannot import export_rules tool:', _e)

                sys.exit(2)

        rc = export_rules_main([])

        sys.exit(rc)



    # Defer normal interactive app launch until after consolidated functions are defined

    globals()['_DEFER_LAUNCH'] = True



# ================== APPEND-ONLY VERSION MARKER ==================

__FILE_VERSION__ = "bishops_v1.6.5_consolidated_clean_8x8_lock_AI_turnrule_2025-09-26"

# ================================================================

# Consolidated Two-Player Chess Mode (single source of truth)

# - Triggers when effectively two colours remain (flashing elimination is treated as gone)

# - Purges all pieces outside the 8-8 (no king teleport)

# - Locks movement to 8-8

# - Kings in their 2-2 home corner may enter on ANY adjacent 8-8 square (one step)

# - Disables grace/queen-caps side effects

# ================================================================

try:

    _ORIG_LEGAL = legal_moves_for_piece

    _ORIG_DRAW = draw_board

    _ORIG_DO = board_do_move

except Exception:

    _ORIG_LEGAL = globals().get('legal_moves_for_piece')

    _ORIG_DRAW = globals().get('draw_board')

    _ORIG_DO = globals().get('board_do_move')



# Real chess engine (FIDE rules) for the locked 8-8 phase

try:

    import importlib

    chess = importlib.import_module("chess")  # python-chess (dynamic import)

    _CHESS_OK = True

except Exception:

    chess = None

    _CHESS_OK = False



# --- Mapping between 14-14 (center 8-8) and python-chess squares ---

def _rc_to_sq(r: int, c: int):

    if not (CH_MIN <= r <= CH_MAX and CH_MIN <= c <= CH_MAX) or not _CHESS_OK:

        return None

    file_idx = c - CH_MIN                   # a..h  0..7

    rank_idx = CH_MAX - r                   # rank 1..8  0..7

    try:

        return chess.square(file_idx, rank_idx)

    except Exception:

        return None



def _sq_to_rc(sq: int):

    if not _CHESS_OK:

        return None

    try:

        f = chess.square_file(sq)

        rnk = chess.square_rank(sq)

        r = CH_MAX - rnk

        c = CH_MIN + f

        return (r, c)

    except Exception:

        return None



def _setup_chess_board_from_golden(bd: Board, state: GameState):

    if not _CHESS_OK:

        return None

    try:

        CB = chess.Board(None)  # empty

        # Pieces

        for rr in range(CH_MIN, CH_MAX+1):

            for cc in range(CH_MIN, CH_MAX+1):

                p = bd.get(rr, cc)

                if not p: continue

                if p.color not in (PColor.WHITE, PColor.BLACK):

                    continue

                sq = _rc_to_sq(rr, cc)

                if sq is None: continue

                typ = {

                    'K': chess.KING, 'Q': chess.QUEEN, 'R': chess.ROOK,

                    'B': chess.BISHOP, 'N': chess.KNIGHT, 'P': chess.PAWN

                }.get(p.kind)

                if typ is None: continue

                CB.set_piece_at(sq, chess.Piece(typ, p.color == PColor.WHITE))

        # Whose turn

        active_idx = getattr(state, 'turn_i', 0)

        active_color = TURN_ORDER[active_idx]

        # In two-player we recolor to WHITE/BLACK; ensure turn maps

        CB.turn = (active_color == PColor.WHITE)

        # Castling rights: derive from rooks/kings on their home squares

        rights = ""

        try:

            if CB.piece_at(chess.E1) == chess.Piece(chess.KING, chess.WHITE):

                if CB.piece_at(chess.H1) == chess.Piece(chess.ROOK, chess.WHITE):

                    rights += "K"

                if CB.piece_at(chess.A1) == chess.Piece(chess.ROOK, chess.WHITE):

                    rights += "Q"

            if CB.piece_at(chess.E8) == chess.Piece(chess.KING, chess.BLACK):

                if CB.piece_at(chess.H8) == chess.Piece(chess.ROOK, chess.BLACK):

                    rights += "k"

                if CB.piece_at(chess.A8) == chess.Piece(chess.ROOK, chess.BLACK):

                    rights += "q"

        except Exception:

            rights = rights  # keep whatever accumulated

        try:

            CB.set_castling_fen(rights or "-")

        except Exception:

            # Fallback for older python-chess: compute bitmask manually

            try:

                mask = chess.BB_EMPTY

                if "K" in rights:

                    mask |= chess.BB_H1

                if "Q" in rights:

                    mask |= chess.BB_A1

                if "k" in rights:

                    mask |= chess.BB_H8

                if "q" in rights:

                    mask |= chess.BB_A8

                CB.castling_rights = mask

            except Exception:

                CB.castling_rights = chess.CastlingRights.NONE

        CB.clear_stack()  # ensure clean history

        return CB

    except Exception:

        return None



def _alive_effective(bd: Board, state: GameState) -> List[PColor]:

    alive = bd.alive_colors()

    flashing = getattr(state, "elim_flash_color", None)

    return [c for c in alive if c != flashing]



def _alive_by_kings(bd: Board) -> List[PColor]:

    """Return colors that currently have a King on the board anywhere."""

    out: List[PColor] = []

    for col in (PColor.WHITE, PColor.GREY, PColor.BLACK, PColor.PINK):

        kp = bd.find_king(col)

        if kp:

            out.append(col)

    return out



def _in8(r, c): return CH_MIN <= r <= CH_MAX and CH_MIN <= c <= CH_MAX



def _king_in_home_corner(bd: Board, color: PColor) -> bool:

    kp = bd.find_king(color)

    if not kp: return False

    return tuple(kp) in set(king_home_cells(color)) and not _in8(*kp)



def _resolve_duel_seats(color_a: PColor, color_b: PColor) -> Tuple[Dict[PColor, PColor], PColor, PColor]:

    finalists = [color_a, color_b]

    pair = set(finalists)

    white_origin = None

    black_origin = None

    if PColor.WHITE in pair:

        white_origin = PColor.WHITE

        other = finalists[0] if finalists[1] == PColor.WHITE else finalists[1]

        if other == PColor.WHITE:

            other = finalists[0]

        black_origin = other

    elif PColor.BLACK in pair:

        black_origin = PColor.BLACK

        other = finalists[0] if finalists[1] == PColor.BLACK else finalists[1]

        if other == PColor.BLACK:

            other = finalists[0]

        white_origin = other

    else:

        if pair == {PColor.GREY, PColor.PINK}:

            white_origin = PColor.PINK

            black_origin = PColor.GREY

        else:

            white_origin, black_origin = finalists[0], finalists[1]



    remap: Dict[PColor, PColor] = {}

    if white_origin is not None:

        remap[white_origin] = PColor.WHITE

    if black_origin is not None:

        remap[black_origin] = PColor.BLACK

    return remap, white_origin or PColor.WHITE, black_origin or PColor.BLACK



def _purge_outside_8x8(bd: Board):

    removed = 0

    for rr in range(BOARD_SIZE):

        for cc in range(BOARD_SIZE):

            p = bd.get(rr, cc)

            if p and not _in8(rr, cc) and p.kind != 'K':   # <-- spare kings

                bd.set(rr, cc, None)

                removed += 1

    if removed:

        print(f"[TP-Consolidated] Purged {removed} piece(s) outside 8-8.")

    return removed



def _enter_duel_kqbb(bd: Board, state: GameState, white_name: str = "White", black_name: str = "Black"):

    """Teleport finalists to a strict Chess duel using the full standard starting position.

    Layout:

      - White seat: back rank RNBQKBNR on rank 1 of the central 8x8; pawns on rank 2.

      - Black seat: back rank rnbqkbnr on rank 8; pawns on rank 7.

    Side to move: White.

    Castling: both kings retain KQ castling rights (FIDE rules apply).

    No other pieces exist.

    """

    global AI_PLAYERS

    # Clear entire 8x8 region first

    for rr in range(CH_MIN, CH_MAX+1):

        for cc in range(CH_MIN, CH_MAX+1):

            bd.set(rr, cc, None)

    # Clear outside area completely

    for rr in range(BOARD_SIZE):

        for cc in range(BOARD_SIZE):

            if not _in8(rr, cc):

                bd.set(rr, cc, None)



    # Helpers

    from typing import Tuple

    def put(rc: Tuple[int,int], kind: str, col: PColor):
        r, c = rc
        piece = Piece(kind, col)
        bd.set(r, c, piece)



    # Place pieces (standard chess layout)

    white_back = ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']

    black_back = ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']

    for idx, kind in enumerate(white_back):

        put((CH_MAX, CH_MIN + idx), kind, PColor.WHITE)

    for idx in range(8):

        put((CH_MAX - 1, CH_MIN + idx), 'P', PColor.WHITE)

    for idx, kind in enumerate(black_back):

        put((CH_MIN, CH_MIN + idx), kind, PColor.BLACK)

    for idx in range(8):

        put((CH_MIN + 1, CH_MIN + idx), 'P', PColor.BLACK)



    # Update state to strict chess

    state.two_stage_active = True

    state.final_a, state.final_b = PColor.WHITE, PColor.BLACK

    white_origin = getattr(state, 'duel_white_origin', PColor.WHITE)

    black_origin = getattr(state, 'duel_black_origin', PColor.BLACK)

    state.duel_white_origin = white_origin

    state.duel_black_origin = black_origin

    state.duel_white_name = white_name

    state.duel_black_name = black_name

    GameState.turn_counter = 0

    state._pending_duel_move_log = f"---- Duel Start: {white_name} ({white_origin.name.title()}) vs {black_name} ({black_origin.name.title()}) ----"

    state._reset_moves_for_duel = True

    try:

        if hasattr(state, 'player_names') and isinstance(state.player_names, dict):

            state.player_names['WHITE'] = white_name

            state.player_names['BLACK'] = black_name

    except Exception:

        pass

    state.entered[PColor.WHITE] = True

    state.entered[PColor.BLACK] = True

    state.reduced_applied[PColor.WHITE] = True

    state.reduced_applied[PColor.BLACK] = True

    state.chess_lock = True

    state.grace_active = False

    state.grace_turns_remaining = 0

    # Start duel with human control for both seats; operator can switch to AI later

    try:

        if hasattr(state, 'player_is_ai') and isinstance(state.player_is_ai, dict):

            state.player_is_ai[PColor.WHITE] = False

            state.player_is_ai[PColor.BLACK] = False

            # reflect into AI_PLAYERS global set

            global AI_PLAYERS

            AI_PLAYERS = {c for c, flag in state.player_is_ai.items() if flag}

    except Exception:

        pass

    # Duel starts in pure human-control mode; skip Ready gating.

    try:

        state.hold_at_start = False

        state.waiting_ready = False

    except Exception:

        pass

    # Hard stop the long game; switch to duel phase

    try:

        state.long_game_over = True

        state.phase = 'duel'

    except Exception:

        pass



    # Side to move: White seat starts

    try:

        # Set turn order index to White

        if hasattr(state, 'turn_i'):

            state.turn_i = TURN_ORDER.index(PColor.WHITE)

        # Reset simple move counters/logs if present

        if hasattr(state, 'half_moves'):

            state.half_moves = 0

        if hasattr(state, 'move_no'):

            state.move_no = 1

        if hasattr(state, 'move_log') and isinstance(state.move_log, list):

            state.move_log.clear()

    except Exception:

        pass



    # Initialize python-chess from FEN of the duel setup (rooks, knights, bishops, four pawns)

    if _CHESS_OK:

        try:

            # Standard chess starting position with full castling rights.

            fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

            state.chess_board = chess.Board(fen)

        except Exception:

            state.chess_board = None

    else:

        try:

            state.chess_board = None

        except Exception:

            pass





    # One-time banner helpers

    state._duel_banner = f"Duel: Standard Chess - White: {white_name}, Black: {black_name}"

    state._duel_started = True

    state._duel_turn_reset = True

    try:

        strong = random.choice([PColor.WHITE, PColor.BLACK])

        weak = PColor.BLACK if strong == PColor.WHITE else PColor.WHITE

        state.duel_strong_side = strong

        state.duel_depth_bonus = {

            PColor.WHITE: DUEL_STRONG_DEPTH_BONUS if strong == PColor.WHITE else 0,

            PColor.BLACK: DUEL_STRONG_DEPTH_BONUS if strong == PColor.BLACK else 0,

        }

        state.duel_time_bonus = {

            PColor.WHITE: DUEL_STRONG_TIME_BONUS_MS if strong == PColor.WHITE else 0,

            PColor.BLACK: DUEL_STRONG_TIME_BONUS_MS if strong == PColor.BLACK else 0,

        }

        state.duel_eval_bias = {

            PColor.WHITE: DUEL_EVAL_STRONG_BIAS if strong == PColor.WHITE else 0,

            PColor.BLACK: DUEL_EVAL_STRONG_BIAS if strong == PColor.BLACK else 0,

        }

        print(f"[DUEL] Random seat advantage grants extra depth/time to {strong.name}.")

    except Exception:

        state.duel_strong_side = None

        state.duel_depth_bonus = {PColor.WHITE: 0, PColor.BLACK: 0}

        state.duel_time_bonus = {PColor.WHITE: 0, PColor.BLACK: 0}

        state.duel_eval_bias = {PColor.WHITE: 0, PColor.BLACK: 0}

    # Brief pause to let program/AI settle and show banner (will be cleared by forced duel)

    try:

        import pygame as _pg

        state.freeze_advance = True

        state.two_stage_pause = True

        state._duel_delay_until = _pg.time.get_ticks() + 1200

    except Exception:

        state.freeze_advance = True

        state.two_stage_pause = True



def _force_duel_now(bd: Board, state: GameState) -> bool:

    """Bypass two-player detection and immediately seed the standard chess duel.

    Safe to call from any state. Returns True on success.

    """

    try:

        # Cancel any flashing/delay flags

        for attr, val in (

            ('_finalists_prep_started', False),

            ('_flash_until', None),

            ('_teleport_after', 0),

            ('_duel_cleared_board', False),

        ):

            try:

                setattr(state, attr, val)

            except Exception:

                pass

        # For a forced duel, do not block with any inspection/duel delay

        try:

            state._duel_delay_until = 0

        except Exception:

            pass

        state.two_stage_pause = False

        state.freeze_advance = False

        state.post_move_delay_until = 0

        state.waiting_ready = False

        state.hold_at_start = False

        # Choose display names if available

        try:

            finalists = []

            if hasattr(state, '_finalists_a') and hasattr(state, '_finalists_b') and state._finalists_a and state._finalists_b:

                finalists = [state._finalists_a, state._finalists_b]

            else:

                alive = bd.alive_colors()

                finalists = alive[:2] if len(alive) >= 2 else alive + [c for c in TURN_ORDER if c not in alive][:2-len(alive)]

        except Exception:

            finalists = [PColor.WHITE, PColor.BLACK]

        if len(finalists) < 2:

            finalists = finalists + [c for c in (PColor.WHITE, PColor.BLACK, PColor.GREY, PColor.PINK) if c not in finalists][:2-len(finalists)]

        remap, white_origin, black_origin = _resolve_duel_seats(finalists[0], finalists[1])

        state.duel_white_origin = white_origin
        state.duel_black_origin = black_origin
        state._duel_finalists = (white_origin, black_origin)
        state._duel_remap = remap

        name_map = getattr(state, 'player_names', {}) if hasattr(state, 'player_names') else {}
        w_name = name_map.get(white_origin.name, white_origin.name.title())
        b_name = name_map.get(black_origin.name, black_origin.name.title())
        _enter_duel_kqbb(bd, state, w_name, b_name)

        try:
            state._duel_delay_until = 0
            state.two_stage_pause = False
            state.post_move_delay_until = 0
            state.freeze_advance = False
            state._duel_banner = "Forced: Duel (Chess) Now - White to move"
        except Exception:
            pass



        state._tp_consolidated_done = True
        state._duel_turn_reset = True
        try:
            for col in state.ai_delay_applied:
                state.ai_delay_applied[col] = False
        except Exception:
            pass

        return True

    except Exception:

        return False



def _activate_two_player_if_needed(bd: Board, state: GameState):

    if getattr(state, "_tp_consolidated_done", False):

        # Always re-purge at the start of every turn in two-player mode

        _purge_outside_8x8(bd)

        return

    # Robust trigger: when exactly two kings remain OR two effective colors remain

    kings_alive = _alive_by_kings(bd)

    a = b = None

    if len(kings_alive) == 2:

        a, b = kings_alive[0], kings_alive[1]

    else:

        eff = _alive_effective(bd, state)

        if len(eff) == 2:

            a, b = eff[0], eff[1]

    # If we're mid-teleport flow (board may be cleared), fall back to stored finalists

    if (a is None or b is None) and getattr(state, '_finalists_prep_started', False):

        a = getattr(state, '_finalists_a', None)

        b = getattr(state, '_finalists_b', None)

    if a is None or b is None:

        return



# New ruleset: Two-phase teleport  3s flash of finalists, then empty board, 1s delay, and teleport to standard chess duel

    if DUEL_TELEPORT_ON_TWO and not getattr(state, '_duel_started', False):

        # Start flash phase if not started

        try:

            import pygame as _pg

            now_ticks = _pg.time.get_ticks()

        except Exception:

            now_ticks = 0

        if not getattr(state, '_finalists_prep_started', False):

            state._finalists_a = a

            state._finalists_b = b

            # Freeze the game and show a 3s flash confirmation for winners

            state.freeze_advance = True

            state.two_stage_pause = True

            # Ensure grace is fully off during duel prep so no 'checks deferred' occurs

            try:

                state.grace_active = False

                state.grace_turns_remaining = 0

            except Exception:

                pass

            state._flash_until = now_ticks + 3000

            state._finalists_prep_started = True

            print(f"[DUEL] Finalists identified: {a.name} vs {b.name}. Flashing 3s, then empty board + 1s, then teleport.")

            return

        # After flash finishes, first purge entire board to empty, then wait 1s before seeding standard chess

        if getattr(state, '_finalists_prep_started', False) and now_ticks >= getattr(state, '_flash_until', 0):

            # Step 1: on first pass after flash, empty the entire board (all pieces, including kings)

            if not getattr(state, '_duel_cleared_board', False):

                for rr in range(BOARD_SIZE):

                    for cc in range(BOARD_SIZE):

                        if bd.get(rr, cc) is not None:

                            bd.set(rr, cc, None)

                state._duel_cleared_board = True

                # Start a 1s teleport delay window to allow UI to update and "teleport" banner

                try:

                    import pygame as _pg

                    state._teleport_after = _pg.time.get_ticks() + 1000

                except Exception:

                    state._teleport_after = now_ticks + 1000

                # Keep game frozen during delay

                state.freeze_advance = True

                state.two_stage_pause = True

                state._duel_banner = "Teleporting to Duel"

                return

            # Step 2: if delay in progress, wait until it elapses

            if getattr(state, '_teleport_after', 0) and now_ticks < state._teleport_after:

                # remain paused until teleport

                state.freeze_advance = True

                state.two_stage_pause = True

                return

            # Step 3: delay has elapsed  perform seat mapping, recolor, and teleport

            remap, white_origin, black_origin = _resolve_duel_seats(a, b)

            state.duel_white_origin = white_origin
            state.duel_black_origin = black_origin
            state._duel_finalists = (white_origin, black_origin)

            player_names = getattr(state, 'player_names', {}) if hasattr(state, 'player_names') else {}
            white_name = player_names.get(white_origin.name, white_origin.name.title())
            black_name = player_names.get(black_origin.name, black_origin.name.title())

            _enter_duel_kqbb(bd, state, white_name, black_name)

            state._tp_consolidated_done = True
            state._duel_turn_reset = True

            # Clear flash flags
            state._finalists_prep_started = False
            state._flash_until = None
            state._teleport_after = 0
            state._duel_cleared_board = False

            print(f"[DUEL] Teleported {white_origin.name} vs {black_origin.name} into standard chess duel. White starts.")

            return



    # Legacy consolidated mode (no teleport)  keep for backwards compatibility

    if not DUEL_TELEPORT_ON_TWO:

        name_map = getattr(state, "player_names", {}) if hasattr(state, "player_names") else {}

        white_name = name_map.get(a.name, a.name.title())

        black_name = name_map.get(b.name, b.name.title())

        _enter_duel_kqbb(bd, state, white_name, black_name)

        state.two_stage_active = True
        state.final_a, state.final_b = a, b
        state.chess_lock = True
        state.grace_active = False
        state.grace_turns_remaining = 0

        state._tp_consolidated_done = True
        state._duel_started = True
        state._duel_turn_reset = True

        print(f"[DUEL] Forced {a.name} vs {b.name} into standard chess duel (legacy mode).")



    # Legacy consolidated activation removed in v2



def legal_moves_for_piece(board: Board, r: int, c: int, active_color: Optional[PColor]=None) -> List[Tuple[int,int]]:

    # If caller didn't provide active_color (legacy callers), infer from the piece on the square

    p = board.get(r, c)

    if active_color is None:

        if not p:

            return []

        active_color = p.color



    # If FIDE engine active, use it exclusively for chess-lock move gen

    gs_local = globals().get('gs', None)

    if _CHESS_OK and gs_local and getattr(gs_local, 'chess_lock', False) and getattr(gs_local, 'chess_board', None):

        CB = gs_local.chess_board

        # If this side has any of its own pieces outside the 8-8 (by design, only the king),

        # then freeze all of its pieces that are already inside the 8-8. This enforces

        # priority for entering the 8-8 even under engine-driven move gen.

        try:

            if p is not None and p.kind != 'K':

                has_outside = False

                for rr in range(BOARD_SIZE):

                    for cc in range(BOARD_SIZE):

                        q = board.get(rr, cc)

                        if q and q.color == active_color and not _in8(rr, cc):

                            has_outside = True

                            break

                    if has_outside:

                        break

                if has_outside:

                    return []

        except Exception:

            pass

        sq_from = _rc_to_sq(r, c)

        # If the piece is a king outside 8-8, allow fallback moves to approach/enter the 8-8

        if sq_from is None:

            try:

                if p and p.kind == 'K' and not _in8(r, c):

                    base = _ORIG_LEGAL(board, r, c, active_color)

                    cur = dist_to_chess(r, c)

                    closer = [(r, c, er, ec) for (er, ec) in base if dist_to_chess(er, ec) < cur]

                    if closer:

                        return closer

                    non_worse = [(r, c, er, ec) for (er, ec) in base if dist_to_chess(er, ec) == cur]

                    return non_worse

            except Exception:

                pass

            return []

        # Only allow moves for the side to move

        if (p.color == PColor.WHITE) != CB.turn:

            return []

        out = []

        try:

            for mv in CB.legal_moves:

                if mv.from_square != sq_from:

                    continue

                dst = _sq_to_rc(mv.to_square)

                if dst is None:

                    continue

                er, ec = dst

                out.append((r, c, er, ec))

        except Exception:

            return []

        return out



    base = _ORIG_LEGAL(board, r, c, active_color)

    # If migration is disabled or not in two-player mode, keep original behavior

    if not ENABLE_MIGRATION or not getattr(globals().get('gs', None), 'two_stage_active', False) or active_color not in (getattr(globals().get('gs', None), 'final_a', None), getattr(globals().get('gs', None), 'final_b', None)):

        return base

    p = board.get(r,c)

    if not p or p.color != active_color:

        return []

    # If this color still has any piece outside the 8-8 (typically the king), then

    # freeze all pieces that are already inside the 8-8 until all of this color's

    # pieces have entered. This enforces priority for entering the 8-8.

    def _color_has_piece_outside(bd: Board, col: PColor) -> bool:

        for rr in range(BOARD_SIZE):

            for cc in range(BOARD_SIZE):

                q = bd.get(rr, cc)

                if q and q.color == col and not _in8(rr, cc):

                    return True

        return False

    color_has_outside = _color_has_piece_outside(board, active_color)

    if color_has_outside and _in8(r, c):

        # Inside pieces are frozen until all own pieces are inside.

        return []

    # Non-kings: must stay inside 8-8

    if p.kind != 'K':

        return [(r, c, er, ec) for (er,ec) in base if _in8(er,ec)]

    # Kings: If outside 8-8, must move toward/into 8-8 ASAP (no stalling)

    if not _in8(r, c):

        cur = dist_to_chess(r, c)

        # Prefer moves that strictly reduce distance

        closer = [(r, c, er, ec) for (er,ec) in base if dist_to_chess(er,ec) < cur]

        if closer:

            return closer

        # If no strictly-closer move exists (blocked edge cases), allow non-worsening

        non_worse = [(r, c, er, ec) for (er,ec) in base if dist_to_chess(er,ec) == cur]

        return non_worse

    # Once in 8-8, must stay in 8-8

    return [(r, c, er, ec) for (er,ec) in base if _in8(er,ec)]



def board_do_move(board: Board, sr, sc, er, ec, simulate=False):

    # If in chess-lock with FIDE engine, validate and push via python-chess first,

    # then mirror special moves (castling, en passant, promotion) onto Golden.

    gs_local = globals().get('gs', None)

    use_chess = _CHESS_OK and gs_local and getattr(gs_local, 'chess_lock', False) and getattr(gs_local, 'chess_board', None) and not simulate

    if use_chess:

        p = board.get(sr, sc)

        CB = gs_local.chess_board

        sq_from = _rc_to_sq(sr, sc)

        sq_to   = _rc_to_sq(er, ec)

        if p is None or sq_from is None or sq_to is None:

            # Allow non-engine move (e.g., king stepping toward/into 8-8)

            res = _ORIG_DO(board, sr, sc, er, ec, simulate)

            try:

                if not simulate:

                    # If the moved piece entered the 8-8 or move touched inside, rebuild engine state

                    if in_chess_area(er, ec):

                        gs_local.chess_board = _setup_chess_board_from_golden(board, gs_local)

                    _activate_two_player_if_needed(board, gs)

            except Exception:

                pass

            return res

        # Default to queen promotion; UI for underpromotion can be added later

        promo = None

        try:

            if p.kind == 'P':

                # Promotion rank for side to move is python-chess rank 7 for the move (to_square rank in {0,7})

                to_rank = chess.square_rank(sq_to)

                if to_rank in (0, 7):

                    promo = chess.QUEEN

            mv = chess.Move(sq_from, sq_to, promotion=promo)

            if mv not in CB.legal_moves:

                return _ORIG_DO(board, sr, sc, er, ec, simulate)  # fall back (shouldn't happen)

            is_ep  = CB.is_en_passant(mv)

            # Detect castling by king move two files

            is_castle = (p.kind == 'K' and sr == er and abs(ec - sc) == 2)

            CB.push(mv)

            # Apply on Golden board

            cap, prev_has, prev_kind, effects = _ORIG_DO(board, sr, sc, er, ec, simulate)

            # Mirror en passant capture (captured pawn is behind the destination on source rank)

            if is_ep and cap is None:

                try:

                    # Captured pawn square: same row as source, column = destination column

                    ep_r, ep_c = sr, ec

                    if board.get(ep_r, ep_c) and board.get(ep_r, ep_c).kind == 'P':

                        board.set(ep_r, ep_c, None)

                        if not simulate:

                            log(f"[CAPTURE] {p.color.name} P x (en passant) at ({ep_r},{ep_c})")

                except Exception:

                    pass

            # Mirror castling rook move

            if is_castle:

                try:

                    # Determine side (kingside if moved right)

                    if ec - sc == 2:  # kingside

                        if p.color == PColor.WHITE:

                            r_sr, r_sc, r_er, r_ec = CH_MAX, CH_MIN+7, CH_MAX, CH_MIN+5  # h1->f1

                        else:

                            r_sr, r_sc, r_er, r_ec = CH_MIN, CH_MIN+7, CH_MIN, CH_MIN+5  # h8->f8

                    else:  # queenside

                        if p.color == PColor.WHITE:

                            r_sr, r_sc, r_er, r_ec = CH_MAX, CH_MIN+0, CH_MAX, CH_MIN+3  # a1->d1

                        else:

                            r_sr, r_sc, r_er, r_ec = CH_MIN, CH_MIN+0, CH_MIN, CH_MIN+3  # a8->d8

                    rook = board.get(r_sr, r_sc)

                    if rook and rook.kind == 'R':

                        board.set(r_sr, r_sc, None)

                        board.set(r_er, r_ec, rook)

                        rook.has_moved = True

                except Exception:

                    pass

            # Promotion already handled by original code (auto-queen). Ensure effect flag if python-chess promoted

            try:

                if promo is not None:

                    effects['promoted'] = True

            except Exception:

                pass

            # Attach SAN if desired

            try:

                last = CB.peek()

                effects['san'] = CB.san(last)

            except Exception:

                pass

            # Reactivate two-player safety and return

            try:

                _activate_two_player_if_needed(board, gs)

            except Exception:

                pass

            return cap, prev_has, prev_kind, effects

        except Exception:

            # On any engine error, fall back to original move

            return _ORIG_DO(board, sr, sc, er, ec, simulate)



    # Default behavior outside chess-lock / engine

    res = _ORIG_DO(board, sr, sc, er, ec, simulate)

    if not simulate:

        try:

            _activate_two_player_if_needed(board, gs)

        except Exception:

            pass

    return res



def draw_board(screen, board: Board, *args, **kwargs):

    # Ensure two-player activation/passive purge before each frame draw

    try:

        _activate_two_player_if_needed(board, gs)

        # Safety purge each frame in two-player mode to remove any lingering non-king pieces outside 8-8

        if getattr(gs, 'two_stage_active', False) and DUEL_TELEPORT_ON_TWO:

            _purge_outside_8x8(board)

        # Auto-resume after duel delay

        try:

            import pygame as _pg

            if getattr(gs, '_duel_delay_until', None) is not None:

                if _pg.time.get_ticks() >= gs._duel_delay_until:

                    gs._duel_delay_until = None

                    gs.two_stage_pause = False

                    gs.freeze_advance = False

            # During pre-duel flash, keep the game paused and draw a flashing highlight later

        except Exception:

            pass

    except Exception:

        pass

    # Draw base board first (Golden visuals)

    res = _ORIG_DRAW(screen, board, *args, **kwargs)

    # During chess lock, do NOT replace Golden board visuals; optionally add coordinates overlay on the inside 8-8

    try:

        if getattr(gs, 'chess_lock', False) and bool(UI_STATE.get('show_coords', False)):

            # Per-square coordinate labels at bottom-left of each 8x8 square (a1..h8)

            try:

                fsize = max(12, SQUARE // 6)

                fnt = get_sidebar_font(fsize, False)

            except Exception:

                fnt = None

            if fnt:

                files = "abcdefgh"

                for rr in range(8):

                    for cc in range(8):

                        label = f"{files[cc]}{8-rr}"

                        x = (CH_MIN+cc) * SQUARE + 3

                        y = (CH_MIN+rr) * SQUARE + (SQUARE - fnt.get_height() - 2)

                        # Lighter labels with parity-aware contrast to remain readable

                        is_light = ((rr + cc) % 2 == 0)

                        col = (150,150,150) if is_light else (235,235,235)

                        # Optional subtle shadow for readability

                        try:

                            sh = fnt.render(label, True, (0,0,0))

                            screen.blit(sh, (x+1, y+1))

                        except Exception:

                            pass

                        lab = fnt.render(label, True, col)

                        screen.blit(lab, (x, y))

    except Exception:

        pass

    # Pre-duel flashing overlay

    # Duel-mode bishop visual tint handled directly via piece colouring



    # Flash overlay for finalists and duel banner

    try:

        if getattr(gs, '_finalists_prep_started', False) and getattr(gs, '_flash_until', None):

            import pygame as _pg

            now = _pg.time.get_ticks()

            remain = max(0, getattr(gs, '_flash_until', 0) - now)

            # Banner at bottom indicating upcoming duel and countdown

            try:

                banner_font = pygame.font.SysFont("Arial", 20, bold=True)

                whoA = getattr(gs, '_finalists_a', None)

                whoB = getattr(gs, '_finalists_b', None)

                names = f"{whoA.name if whoA else '?'} vs {whoB.name if whoB else '?'}"

                msg = f"Duel incoming: {names}  teleport in {int((remain/1000)+0.5)}s"

                bar = pygame.Rect(0, BOARD_SIZE*SQUARE, LOGICAL_W, 44)

                pygame.draw.rect(screen, BANNER_OK, bar)

                clr = (240,240,210)

                screen.blit(banner_font.render(msg, True, clr), (10, BOARD_SIZE*SQUARE + 8))

            except Exception:

                pass

            # Flash rectangles around finalists' pieces on the whole board

            phase = (now // 250) % 2

            if phase == 0:

                col = (255, 215, 0)

                for rr in range(BOARD_SIZE):

                    for cc in range(BOARD_SIZE):

                        p = board.get(rr, cc)

                        if not p:

                            continue

                        if p.color in (getattr(gs, '_finalists_a', None), getattr(gs, '_finalists_b', None)):

                            try:

                                pygame.draw.rect(screen, col, (cc*SQUARE+2, rr*SQUARE+2, SQUARE-4, SQUARE-4), 3)

                            except Exception:

                                pass

    except Exception:

        pass

    # Duel started: show banner for 2s settle window

    try:

        if getattr(gs, '_duel_started', False):

            banner = getattr(gs, '_duel_banner', None)

            if banner:

                bar = pygame.Rect(0, BOARD_SIZE*SQUARE, LOGICAL_W, 44)

                pygame.draw.rect(screen, BANNER_OK, bar)

                status_font = pygame.font.SysFont("Arial", 20, bold=True)

                txt = status_font.render(banner, True, (235,235,210))

                screen.blit(txt, (10, BOARD_SIZE*SQUARE + 8))

    except Exception:

        pass

    # Visual overlay: mark any non-king pieces outside 8-8 to help diagnose reports

    try:

        outside: list = []

        for rr in range(BOARD_SIZE):

            for cc in range(BOARD_SIZE):

                p = board.get(rr, cc)

                if p and p.kind != 'K' and not _in8(rr, cc):

                    outside.append((rr, cc, p))

        if outside:

            # Gray outline if not in two-player yet; Red warning if two-player active (should be none)

            two = bool(getattr(gs, 'two_stage_active', False))

            color = (220, 60, 60) if two else (150, 150, 150)

            for (rr, cc, p) in outside:

                try:

                    pygame.draw.rect(

                        screen,

                        color,

                        (cc * SQUARE + 2, rr * SQUARE + 2, SQUARE - 4, SQUARE - 4),

                        2

                    )

                except Exception:

                    pass

            if two:

                try:

                    locs = ', '.join([f"{rc_to_label(r,c)}:{getattr(p,'kind','?')}" for (r,c,p) in outside])

                    print(f"[WARN] Two-player active but found non-king(s) outside 8-8: {locs}")

                except Exception:

                    print("[WARN] Two-player active but found non-king(s) outside 8-8")

    except Exception:

        pass

    return res



# Install consolidated hooks

globals()['legal_moves_for_piece'] = legal_moves_for_piece

globals()['board_do_move'] = board_do_move

globals()['draw_board'] = draw_board



print("[TP-Consolidated] Installed: any-square king entry, purge-off-8-8, 8-8 lock, winner overlay intact.")



# ---- Final entry point ----

# Launch the interactive app after all helpers are defined, unless running CLI-only modes

try:

    # Only auto-launch if not already in a special CLI path

    _argv = sys.argv[1:]

    _cli_only = any(a.startswith("--self-test") for a in _argv) or ("--export-rules-pdf" in _argv)

    if not _cli_only:

        # If earlier code asked to defer, we've now finished definitions; clear and launch

        if globals().get('_DEFER_LAUNCH', False):

            globals()['_DEFER_LAUNCH'] = False

            try:

                main()

            except SystemExit:

                raise

            except Exception:

                import traceback

                traceback.print_exc()

                # On Windows double-click, keep console open to show errors

                try:

                    input("Press Enter to close...")

                except Exception:

                    pass

except Exception:

    # As a last resort, attempt to run main

    try:

        main()

    except Exception:

        pass


