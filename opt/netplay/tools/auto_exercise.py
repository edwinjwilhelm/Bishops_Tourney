import random
import sys
import os
from typing import Dict, List, Tuple

# Ensure local packages (e.g., 'netplay') are importable when running directly
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Ensure we load the same engine wrapper as the server (headless / SDL dummy)
from netplay.engine_adapter import create_engine, engine

PColor = engine.PColor
Piece = engine.Piece


def color_name(c: PColor) -> str:
    return getattr(c, 'name', str(c))


def edge_restriction_applies(gs) -> bool:
    return getattr(gs, 'half_moves', 0) < 4


def exercise_piece_legality(headless) -> Dict[str, int]:
    """Enumerate legal moves per piece and spot-check a handful of illegal moves.
    Returns counters for summary output.
    """
    b = headless.board
    counts = {"pieces": 0, "legal_moves": 0, "illegal_checked": 0}
    SIZE = engine.BOARD_SIZE

    # Build a map of legal moves by source for each color
    all_legal_by_color: Dict[PColor, List[Tuple[int,int,int,int]]] = {}
    for col in engine.TURN_ORDER:
        all_legal_by_color[col] = list(engine.all_legal_moves_for_color(b, col))

    def set_turn(col: PColor):
        headless.turn_i = engine.TURN_ORDER.index(col)
        headless.forced_turn = None

    # Helper to test illegal moves by generating obviously-bad deltas per kind
    def sample_illegal_moves(sr: int, sc: int, kind: str, col: PColor) -> List[Tuple[int,int,int,int]]:
        candidates = []
        # Always include "no move" and an off-board attempt
        candidates.append((sr, sc, sr, sc))
        candidates.append((sr, sc, -1, sc))
        if kind == 'P':
            # Use engine pawn_dir to compute forward axis and generate clearly illegal patterns
            gs = getattr(engine, 'gs', None)
            default_dir = {PColor.WHITE: -1, PColor.BLACK: 1, PColor.GREY: 1, PColor.PINK: -1}
            pd = default_dir.get(col, -1)
            if gs is not None:
                pd = gs.pawn_dir.get(col, pd)
            if col in (engine.PColor.WHITE, engine.PColor.BLACK):
                fwd = (pd, 0)
                # Backward one, sideways multi, knight-like
                candidates += [ (sr, sc, sr - fwd[0], sc - fwd[1]), (sr, sc, sr, sc+3), (sr, sc, sr+2, sc+1) ]
            else:
                # GREY/PINK move along columns
                fwd = (0, pd)
                candidates += [ (sr, sc, sr - fwd[0], sc - fwd[1]), (sr+3, sc, sr, sc), (sr+2, sc+1, sr, sc) ]
        elif kind == 'N':
            # Not an L
            candidates += [ (sr, sc, sr+2, sc+2), (sr, sc, sr+1, sc+1) ]
        elif kind == 'B':
            # Non-diagonal
            candidates += [ (sr, sc, sr+2, sc), (sr, sc, sr, sc+2) ]
        elif kind == 'R':
            # Diagonal
            candidates += [ (sr, sc, sr+2, sc+2) ]
        elif kind == 'Q':
            # Knight-like only
            candidates += [ (sr, sc, sr+2, sc+1) ]
        elif kind == 'K':
            # Two squares
            candidates += [ (sr, sc, sr+2, sc), (sr, sc, sr, sc+2) ]
        return candidates

    for r in range(SIZE):
        for c in range(SIZE):
            p = b.get(r, c)
            if not p:
                continue
            counts["pieces"] += 1
            col = p.color
            set_turn(col)
            legal = [m for m in all_legal_by_color[col] if m[0]==r and m[1]==c]
            counts["legal_moves"] += len(legal)
            # Check a few illegal patterns don't slip through
            for (sr, sc, er, ec) in sample_illegal_moves(r, c, p.kind, col)[:4]:
                ok = headless.is_legal_move(sr, sc, er, ec)
                # It should NOT be legal
                if ok:
                    raise AssertionError(f"Illegal move flagged legal: {p.kind} {color_name(col)} ({sr},{sc})->({er},{ec})")
                counts["illegal_checked"] += 1

    return counts


def test_edge_pawn_restriction_first_round(headless) -> int:
    """Assert that in the opening round no legal move is an 'edge pawn' capturing an opposing edge pawn.
    Returns number of inspected pawn-capture candidates.
    """
    b = headless.board
    SIZE = engine.BOARD_SIZE
    inspected = 0
    CH_MIN = engine.CH_MIN
    CH_MAX = engine.CH_MAX
    gs = getattr(engine, 'gs', None)
    # Ensure we're in first-round state
    if gs is not None:
        gs.half_moves = 0
    for col in engine.TURN_ORDER:
        moves = list(engine.all_legal_moves_for_color(b, col))
        for (sr, sc, er, ec) in moves:
            sp = b.get(sr, sc)
            tp = b.get(er, ec)
            if not sp or sp.kind != 'P' or not tp or tp.kind != 'P' or tp.color == sp.color:
                continue
            # WHITE/BLACK edge files; GREY/PINK edge ranks
            if col in (engine.PColor.WHITE, engine.PColor.BLACK):
                attacker_on_edge = sc in (CH_MIN, CH_MAX)
                target_on_edge = ec in (CH_MIN, CH_MAX)
            else:
                attacker_on_edge = sr in (CH_MIN, CH_MAX)
                target_on_edge = er in (CH_MIN, CH_MAX)
            if attacker_on_edge and target_on_edge:
                inspected += 1
                raise AssertionError(f"Edge-pawn capture was legal in first round: {color_name(col)} ({sr},{sc})->({er},{ec})")
    return inspected


def autoplay_random(headless, plies: int = 40, seed: int = 7) -> Dict[str, int]:
    random.seed(seed)
    stats = {"plies": 0, "moves_made": 0, "skipped": 0}
    for _ in range(plies):
        color = headless.active_color()
        legal = list(engine.all_legal_moves_for_color(headless.board, color))
        legal = [(r0,c0,r1,c1) for (r0,c0,r1,c1) in legal]
        if not legal:
            stats["skipped"] += 1
            # advance turn baseline
            headless.turn_i = (engine.TURN_ORDER.index(color) + 1) % 4
            continue
        mv = random.choice(legal)
        res = headless.apply_move(color.name, *mv)
        if not res.get("ok", False):
            raise AssertionError(f"Engine rejected its own legal move: {color_name(color)} {mv} -> {res}")
        stats["moves_made"] += 1
        stats["plies"] += 1
    return stats


def _greedy_key(board, mv) -> Tuple[int, int, int, int, int]:
    """Score a move tuple (sr,sc,er,ec) with simple greedy heuristics.
    Higher is better. Prefers captures, promotions, center/8x8, and approach.
    """
    from netplay import engine_adapter as ea  # local import to avoid circulars at top
    engine = ea.engine
    sr, sc, er, ec = mv
    tgt = board.get(er, ec)
    capv = engine.PIECE_VALUES.get(tgt.kind, 0) if tgt and tgt.color != board.get(sr, sc).color else 0
    # simulate to detect promotion
    cap, ph, pk, eff = engine.board_do_move(board, sr, sc, er, ec, simulate=True)
    moved = board.get(er, ec)
    promoted = 1 if isinstance(eff, dict) and eff.get('promoted') else 0
    # center/8x8 preference
    in8 = 2 if engine.in_chess_area(er, ec) else 0
    # approach towards the 8x8 boundary
    try:
        start_d = engine.dist_to_chess(sr, sc)
        end_d = engine.dist_to_chess(er, ec)
        approach = max(0, start_d - end_d)
    except Exception:
        approach = 0
    # knights/bishops small encouragement for development
    dev = 1 if moved and moved.kind in ('N', 'B') else 0
    # undo sim
    engine.board_undo_move(board, sr, sc, er, ec, cap, ph, pk, eff)
    # tuple order: capture value, promotion, in8, approach, develop
    return (capv, promoted, in8, approach, dev)


def autoplay_greedy(headless, plies: int = 40) -> Dict[str, int]:
    """Play with a naive greedy policy: pick the highest scoring move by _greedy_key.
    Falls back to random choice on ties.
    """
    from netplay import engine_adapter as ea
    engine = ea.engine
    stats = {"plies": 0, "moves_made": 0, "skipped": 0}
    for _ in range(plies):
        color = headless.active_color()
        legal = list(engine.all_legal_moves_for_color(headless.board, color))
        legal = [(r0, c0, r1, c1) for (r0, c0, r1, c1) in legal]
        if not legal:
            stats["skipped"] += 1
            headless.turn_i = (engine.TURN_ORDER.index(color) + 1) % 4
            continue
        # choose best by greedy key
        legal.sort(key=lambda mv: _greedy_key(headless.board, mv), reverse=True)
        # slight noise to avoid deterministic loops between equal moves
        top = [mv for mv in legal if _greedy_key(headless.board, mv) == _greedy_key(headless.board, legal[0])]
        mv = random.choice(top)
        res = headless.apply_move(color.name, *mv)
        if not res.get("ok", False):
            raise AssertionError(f"Engine rejected its own greedy-legal move: {color_name(color)} {mv} -> {res}")
        stats["moves_made"] += 1
        stats["plies"] += 1
    return stats


def _empty_board():
    b = engine.Board()
    # Clear all squares
    for r in range(engine.BOARD_SIZE):
        for c in range(engine.BOARD_SIZE):
            b.set(r, c, None)
    return b


def test_promotions() -> int:
    """Place pawns one step from the inner 8x8 edge (CH_MIN/CH_MAX) and verify they auto-queen."""
    b = _empty_board()
    promoted = 0
    ch_min = getattr(engine, 'CH_MIN', 2)
    ch_max = getattr(engine, 'CH_MAX', 9)
    center_row = (ch_min + ch_max) // 2
    center_col = center_row

    # WHITE: advance into the top edge of the chess area
    b.set(ch_min + 1, center_col, Piece('P', PColor.WHITE))
    cap, ph, pk, eff = engine.board_do_move(b, ch_min + 1, center_col, ch_min, center_col, simulate=False)
    assert b.get(ch_min, center_col) and b.get(ch_min, center_col).kind == 'Q' and eff.get('promoted'), 'WHITE promotion failed'
    promoted += 1

    # BLACK: advance into the bottom edge of the chess area
    b.set(ch_max - 1, center_col + 1, Piece('P', PColor.BLACK))
    cap, ph, pk, eff = engine.board_do_move(b, ch_max - 1, center_col + 1, ch_max, center_col + 1, simulate=False)
    assert b.get(ch_max, center_col + 1) and b.get(ch_max, center_col + 1).kind == 'Q' and eff.get('promoted'), 'BLACK promotion failed'
    promoted += 1

    # GREY: advance into the right edge of the chess area
    b.set(center_row, ch_max - 1, Piece('P', PColor.GREY))
    cap, ph, pk, eff = engine.board_do_move(b, center_row, ch_max - 1, center_row, ch_max, simulate=False)
    assert b.get(center_row, ch_max) and b.get(center_row, ch_max).kind == 'Q' and eff.get('promoted'), 'GREY promotion failed'
    promoted += 1

    # PINK: advance into the left edge of the chess area
    b.set(center_row + 1, ch_min + 1, Piece('P', PColor.PINK))
    cap, ph, pk, eff = engine.board_do_move(b, center_row + 1, ch_min + 1, center_row + 1, ch_min, simulate=False)
    assert b.get(center_row + 1, ch_min) and b.get(center_row + 1, ch_min).kind == 'Q' and eff.get('promoted'), 'PINK promotion failed'
    promoted += 1

    return promoted


def test_king_corner_immunity() -> None:
    """Move WHITE king into its corner with two bishops present; ensure bishops->queens and immunity flag prevents check."""
    gs = getattr(engine, 'gs', None)
    if gs is None:
        raise AssertionError('gs not available')
    # Reset immunity
    gs.corner_immune[PColor.WHITE] = False
    b = _empty_board()
    # Place WHITE K ready to enter corner (WHITE corner at bottom-left 2x2)
    b.set(10, 1, Piece('K', PColor.WHITE))
    # Place two WHITE bishops anywhere
    b.set(6, 6, Piece('B', PColor.WHITE))
    b.set(7, 7, Piece('B', PColor.WHITE))
    # Place a BLACK rook lined on row 11 to attack (11,1)
    b.set(11, 5, Piece('R', PColor.BLACK))
    # Move K into corner (11,1)
    cap, ph, pk, eff = engine.board_do_move(b, 10, 1, 11, 1, simulate=False)
    # Expect bishops transformed to queens and immunity set
    assert gs.corner_immune.get(PColor.WHITE, False), 'Corner immunity not set'
    qcount = 0
    for r in range(engine.BOARD_SIZE):
        for c in range(engine.BOARD_SIZE):
            p = b.get(r,c)
            if p and p.color == PColor.WHITE and p.kind == 'Q':
                qcount += 1
    assert qcount >= 2, 'Bishops not transformed to queens'
    # Despite rook attack along the row, WHITE king should not be considered in check
    assert not engine.king_in_check(b, PColor.WHITE), 'King in corner should be immune to check'


def test_two_player_activation() -> None:
    """With only two kings on board, two-stage activates and finalists are set; must-enter filter should apply when king outside 8x8."""
    gs = getattr(engine, 'gs', None)
    if gs is None:
        raise AssertionError('gs not available')
    gs.two_stage_active = False
    gs.final_a = gs.final_b = None
    b = _empty_board()
    b.set(11, 3, Piece('K', PColor.WHITE))  # outside 8x8
    b.set(0, 8, Piece('K', PColor.BLACK))
    engine.activate_two_stage_if_needed(b, gs)
    assert gs.two_stage_active, 'Two-stage not activated'
    assert set([gs.final_a, gs.final_b]) == set([PColor.WHITE, PColor.BLACK]), 'Finalists incorrect'
    mf = engine.must_enter_filter_for(b, PColor.WHITE)
    assert mf is None, 'must_enter_filter_for should be disabled under consolidated rules'


def test_forced_turn_behavior() -> None:
    """A checking move should force the checked color to move next; others cannot move until resolved."""
    # Ensure consolidated two-stage overrides do not interfere with tuple shapes
    gs = getattr(engine, 'gs', None)
    if gs is not None:
        gs.two_stage_active = False
        gs.final_a = gs.final_b = None
    h = create_engine()
    b = _empty_board()
    h.board = b
    # Place kings (required for legality and check logic)
    b.set(9, 9, Piece('K', PColor.WHITE))
    b.set(6, 8, Piece('K', PColor.BLACK))
    # Place a WHITE rook to deliver check after a move
    b.set(6, 2, Piece('R', PColor.WHITE))
    # Set active to WHITE
    h.turn_i = engine.TURN_ORDER.index(PColor.WHITE)
    # Move rook to (6,7) to check BLACK king on (6,8)
    res = h.apply_move('WHITE', 6, 2, 6, 7)
    assert res.get('ok'), f"white checking move rejected: {res}"
    assert h.forced_turn == PColor.BLACK, 'Forced turn should be BLACK after check'
    # Attempt GREY move should be denied
    res2 = h.apply_move('GREY', 0, 0, 0, 0)
    assert not res2.get('ok') and 'Not' in res2.get('error',''), 'Non-victim should not be allowed to move during forced turn'
    # Attempt BLACK's response. If no legal moves (mate/stuck), that's acceptable for this test; otherwise ensure response is allowed.
    legal = [mv for mv in h.legal_moves_for_active() if mv[0]==6 and mv[1]==8]
    if legal:
        r0,c0,r1,c1 = legal[0]
        res3 = h.apply_move('BLACK', r0, c0, r1, c1)
        assert res3.get('ok'), f"black escape move rejected: {res3}"
        # Forced turn should be cleared (unless another check persists)
        assert h.forced_turn in (None, PColor.WHITE, PColor.GREY, PColor.PINK) and h.forced_turn != PColor.BLACK, 'Forced turn not cleared from BLACK'
    else:
        # No legal escape moves; at minimum, ensure forced turn remains BLACK (since it's their obligation)
        assert h.forced_turn == PColor.BLACK, 'Forced turn should remain on the checked color when no moves exist'


def main():
    headless = create_engine()
    # 1) Piece legality exercise
    counts = exercise_piece_legality(headless)
    print(f"[OK] pieces={counts['pieces']} legal_moves={counts['legal_moves']} illegal_checked={counts['illegal_checked']}")
    # 2) First-round edge-pawn restriction
    inspected = test_edge_pawn_restriction_first_round(headless)
    print(f"[OK] edge-pawn first-round inspected={inspected}")
    # 3) Autoplay for coverage
    auto = autoplay_random(headless, plies=40)
    print(f"[OK] autoplay plies={auto['plies']} moves_made={auto['moves_made']} skipped={auto['skipped']}")
    # 3b) Greedy autoplay (more realistic capture/center bias)
    greedy = autoplay_greedy(headless, plies=40)
    print(f"[OK] autoplay-greedy plies={greedy['plies']} moves_made={greedy['moves_made']} skipped={greedy['skipped']}")
    # 4) Promotions
    promos = test_promotions()
    print(f"[OK] promotions verified={promos}")
    # 5) King-corner immunity
    test_king_corner_immunity()
    print(f"[OK] king-in-corner immunity")
    # 6) Two-player activation & must-enter filter
    test_two_player_activation()
    print(f"[OK] two-player activation + must-enter filter")
    # 7) Forced-turn behavior
    test_forced_turn_behavior()
    print(f"[OK] forced-turn behavior")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"[FAIL] {e}")
        sys.exit(1)
