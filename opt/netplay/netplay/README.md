# Bishops Netplay (Prototype)

This is a minimal networked prototype to let up to 4 people connect to a hosted Bishops board from their browsers.  
As of November 2025 it supports multiple simultaneous rooms (tables) per server.

What it is:

- A FastAPI WebSocket server hosting one or more rooms (each room owns its own engine instance)
- A static web client (`index_v3.html`) with a lobby panel to create/select rooms and take seats (WHITE/GREY/BLACK/PINK)
- A headless engine bridge -- the trusted pygame/Golden ruleset validates moves server-side (no desktop window needed)

## Quick start (Windows PowerShell)

1. Create a virtual environment (optional but recommended)

   ```
   python -m venv .venv
   . .venv\Scripts\Activate.ps1
   ```

2. Install dependencies

   ```
   pip install -r netplay/requirements.txt
   ```

3. Run the server (either via the module entry-point or uvicorn)

   ```
   python -m netplay.server_v3
   ```

   You can also run `python -m uvicorn netplay.server_v3:app --host 0.0.0.0 --port 8200` if you want explicit uvicorn control.

4. Open the client/lobby in your browser(s)

- Navigate to `http://localhost:8000` (or whatever host/port you exposed)
- Use the **Room** panel to pick/create a room, then pick a seat and click **Connect**
- Open multiple tabs/browsers (or devices) to simulate several humans

## Multi-room API surface

- `GET /rooms` -> list summaries (room id, label, seat usage, spectators, move count, AI status)
- `POST /rooms` -> create a new room; optional JSON `{ "room_id": "slug", "label": "Friendly name" }`
- `DELETE /rooms/{room_id}` -> remove an empty room (the default `main` room cannot be deleted)
- WebSockets now use `ws://host/ws?room=<id>&seat=<seat>`; omitting `room` falls back to `main`
- REST helpers that operate on a single game also accept `?room=<id>` (`/seats`, `/admin/new-game`, `/library/*`, `/debug/piece-count`, etc.)

## Minimal protocol

- Connect: WebSocket to `ws://localhost:8000/ws?room=main&seat=WHITE` (seats: WHITE/GREY/BLACK/PINK/SPECTATOR)
- Server messages:
  - `{ "type":"state", "payload": { turn, board[14][14], alive[], moves[] } }`
  - `{ "type":"error", "payload": "string message" }`
- Client -> Server:
  - `{ "type":"move", "payload": { "sr":int, "sc":int, "er":int, "ec":int } }` (must be sent by the active seat)

Tip: You can still try a move from the browser console after connecting:

```
ws.send(JSON.stringify({type:'move', payload:{sr:12, sc:1, er:11, ec:1}}))
```

Coordinates use the engine's 14x14 board indices (0..13).

## Next steps (planned)

- Phase 3: integrate the lobby/game viewer into the public marketing site shell (shareable links, on-brand chrome)
- Persistence & reconnection per room (restore games if the process restarts)
- Spectator chat and player wait-listing for busy rooms
