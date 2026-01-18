"""Fast batch runner for Bishops_Golden self-play matches.
For quick diagnostics we force AI_STRENGTH to 'fast', set small max_plies and per-match timeout.
"""
import importlib.util, time, random, os
spec = importlib.util.spec_from_file_location('bg', r'c:\Bishops_chatGPT\Bishops_Golden.py')
bg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bg)
# Force fast AI for speed
bg.AI_STRENGTH = 'fast'

Board = bg.Board
TURN_ORDER = bg.TURN_ORDER
PIECE_VALUES = bg.PIECE_VALUES

def play_one(max_plies=40, timeout_seconds=6, seed=None):
    if seed is not None:
        random.seed(seed)
    b = Board()
    plies = 0
    captures = 0
    t0 = time.time()
    while plies < max_plies:
        alive = b.alive_colors()
        if len(alive) <= 1:
            break
        for col in TURN_ORDER:
            if time.time() - t0 > timeout_seconds:
                # timeout
                plies = max_plies
                break
            if b.find_king(col) is None:
                continue
            mv = bg.choose_ai_move(b, col, two_stage=False)
            if mv is None:
                continue
            sr, sc, er, ec = mv
            cap, ph, pk, eff = bg.board_do_move(b, sr, sc, er, ec, simulate=False)
            if cap:
                captures += 1
            plies += 1
            if plies >= max_plies:
                break
    material = {c:0 for c in TURN_ORDER}
    for r in range(bg.BOARD_SIZE):
        for c in range(bg.BOARD_SIZE):
            p = b.get(r,c)
            if p:
                material[p.color] += PIECE_VALUES.get(p.kind, 0)
    alive = b.alive_colors()
    if len(alive) == 1:
        winner = alive[0]
    else:
        winner = max(material.items(), key=lambda kv:(kv[1], kv[0].value))[0]
    return {'plies': plies, 'captures': captures, 'material': material, 'winner': winner, 'alive': alive}

if __name__ == '__main__':
    # Allow environment overrides for safer batch runs
    try:
        N = int(os.environ.get('BG_BATCH_N', '10'))
        MAX_PLIES = int(os.environ.get('BG_MAX_PLIES', '20'))
        TIMEOUT = int(os.environ.get('BG_TIMEOUT', '4'))
    except Exception:
        N = 10; MAX_PLIES = 20; TIMEOUT = 4
    results = []
    for i in range(N):
        seed = int(time.time()*1000) % 2**32
        print(f'Run {i+1}/{N}, seed={seed}...')
        res = play_one(max_plies=MAX_PLIES, timeout_seconds=TIMEOUT, seed=seed)
        results.append(res)
    wins = {c:0 for c in TURN_ORDER}
    tot_plies = sum(r['plies'] for r in results)
    tot_capt = sum(r['captures'] for r in results)
    tot_mat = {c:0 for c in TURN_ORDER}
    for r in results:
        wins[r['winner']] += 1
        for c in TURN_ORDER:
            tot_mat[c] += r['material'].get(c,0)
    print('\nBatch summary:')
    print(f'Runs: {N}')
    for c in TURN_ORDER:
        print(f'  {c.name}: wins={wins[c]} avg_mat={tot_mat[c]/N:.1f}')
    print(f'Avg plies: {tot_plies/N:.1f}, Avg captures: {tot_capt/N:.2f}')
