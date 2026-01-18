import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location('bg', r'c:\Bishops_chatGPT\Bishops_Golden.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

Board = mod.Board
GameState = mod.GameState
PColor = mod.PColor

def parse_label(lbl: str):
    lbl = lbl.strip().lower()
    if len(lbl) < 2:
        return None
    col = ord(lbl[0]) - ord('a')
    try:
        row = int(lbl[1:]) - 1
    except Exception:
        return None
    return (row, col)

def main():
    if len(sys.argv) < 2:
        print('Usage: python tools/load_moves_and_run.py "a2-a3, b7-b6, ..."')
        return
    seq = sys.argv[1]
    moves = []
    for part in seq.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' not in part:
            print('Skipping malformed move:', part)
            continue
        s, e = part.split('-', 1)
        src = parse_label(s)
        dst = parse_label(e)
        if not src or not dst:
            print('Skipping malformed move:', part)
            continue
        moves.append((src, dst))

    b = Board()
    gs = GameState()
    globals_ref = globals()
    globals_ref['gs'] = gs
    print('[LOADER] Applying', len(moves), 'moves')
    color_cycle = list(mod.TURN_ORDER)
    turn_i = 0
    for (sr, sc), (er, ec) in moves:
        col = color_cycle[turn_i % 4]
        p = b.get(sr, sc)
        if not p or p.color != col:
            # try to find a piece of this color that can move to dst
            legal = mod.all_legal_moves_for_color(b, col)
            found = None
            for r0,c0, r1,c1 in legal:
                if (r1,c1)==(er,ec):
                    found = (r0,c0,r1,c1)
                    break
            if not found:
                print(f"[LOADER] No {col.name} move to {er,ec} found; skipping {sr,sc}->{er,ec}")
                turn_i += 1
                continue
            sr,sc,er,ec = found
        mod.board_do_move(b, sr, sc, er, ec, simulate=False)
        mod.GameState.turn_counter += 1
        turn_i += 1
        # Let teleport logic react
        try:
            mod._activate_two_player_if_needed(b, gs)
        except Exception:
            pass

    # After applying moves, fast-forward any flash/teleport timers
    if getattr(gs, '_finalists_prep_started', False):
        setattr(gs, '_flash_until', 0)
        mod._activate_two_player_if_needed(b, gs)
        setattr(gs, '_teleport_after', 0)
        mod._activate_two_player_if_needed(b, gs)

    print('[LOADER] Done. duel_started=', getattr(gs, '_duel_started', False), 'chess_lock=', gs.chess_lock)

if __name__ == '__main__':
    main()
