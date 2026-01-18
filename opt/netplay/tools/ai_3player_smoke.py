import sys
import os
import random
import time

# Ensure we can import the engine module from repo root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from Bishops_Golden import Board, Piece, PColor, TURN_ORDER, board_do_move, board_undo_move
from Bishops_Golden import choose_ai_move, all_legal_moves_for_color, king_in_check, PIECE_VALUES


def clear_board(b: Board):
    for r in range(14):
        for c in range(14):
            b.set(r, c, None)


def setup_simple_3player_position():
    b = Board()
    clear_board(b)
    # Place three kings on safe-ish squares, WHITE moves first by default
    b.set(6, 3, Piece('K', PColor.WHITE))
    b.set(3, 6, Piece('K', PColor.GREY))
    b.set(10, 10, Piece('K', PColor.BLACK))
    # Give each some material
    b.set(8, 3, Piece('Q', PColor.WHITE))
    b.set(2, 8, Piece('R', PColor.GREY))
    b.set(9, 8, Piece('R', PColor.BLACK))
    # Add a bait piece for the left-target (from WHITE's perspective, left neighbor is GREY)
    b.set(5, 6, Piece('P', PColor.GREY))
    return b


def alive_next_color(board: Board, me: PColor) -> PColor:
    idx = TURN_ORDER.index(me)
    for i in range(1, 5):
        nxt = TURN_ORDER[(idx + i) % 4]
        if board.find_king(nxt) is not None:
            return nxt
    return None


def pref_left_target_capture(board: Board, me: PColor, move):
    sr, sc, er, ec = move
    cap, ph, pk, eff = board_do_move(board, sr, sc, er, ec, simulate=True)
    ok = (cap is not None and cap.color == alive_next_color(board, me))
    board_undo_move(board, sr, sc, er, ec, cap, ph, pk, eff)
    return ok


def main():
    random.seed(0)
    b = setup_simple_3player_position()
    me = PColor.WHITE
    # Two-stage is False (we are in 3-player), and we don't need filters here
    mv = choose_ai_move(b, me, two_stage=False, must_enter_filter=None, grace_block_fn=None, opponent=None)
    if mv is None:
        print("[FAIL] AI returned no move")
        sys.exit(2)
    print(f"Chosen move: {mv}")
    # Prefer that the chosen move either captures left neighbor or gives check to them
    left = alive_next_color(b, me)
    cap_pref = pref_left_target_capture(b, me, mv)
    # Check preference: move should give check to left neighbor more likely than others
    sr, sc, er, ec = mv
    cap, ph, pk, eff = board_do_move(b, sr, sc, er, ec, simulate=True)
    give_check_left = king_in_check(b, left)
    # Also compute if it gives check to the non-target rival
    others = [c for c in TURN_ORDER if c not in (me, left) and b.find_king(c) is not None]
    give_check_other = False
    for oc in others:
        if king_in_check(b, oc):
            give_check_other = True
            break
    board_undo_move(b, sr, sc, er, ec, cap, ph, pk, eff)

    if cap_pref or (give_check_left and not give_check_other):
        print(f"[PASS] Left-target pressure ok (left={left.name}).")
        sys.exit(0)
    else:
        print(f"[WARN] Did not prefer left neighbor (left={left.name}). Move={mv}")
        sys.exit(1)


if __name__ == "__main__":
    main()
