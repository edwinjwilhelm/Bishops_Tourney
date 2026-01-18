# Bishops Golden Project - Complete Information

## Project Overview
This document contains all information related to the `Bishops_Golden.py` file and the complete Bishops netplay game system extracted from project documentation.

---

## Main File: Bishops_Golden.py

### Location
- Current version: `c:\All_Good_Files\Bishops_Golden.py`
- Project folder: `November03-2025` (preferred/stable version)
- Alternative folders: `November07-2025`, `November10-2025`

### File Details
- **Type**: Four-Player Chess Game
- **Version**: v1.6.4 (Consolidated Two-Player Mode)
- **Total Lines**: ~14,189 lines
- **Language**: Python with Pygame
- **Main Dependencies**: pygame, json, hashlib, threading

### Key Configuration Constants (Lines 1-100)
```python
BOARD_SIZE = 12
SQUARE = 56
DEFAULT_SQUARE = 60
LOGICAL_W = BOARD_SIZE * SQUARE    # 672
LOGICAL_H = BOARD_SIZE * SQUARE + 44  # 716 (incl. status)

# Colors
LIGHT = (240, 217, 181)
DARK = (181, 136, 99)
HL = (255, 255, 0)
OUTLINE = (20, 20, 20)
BANNER_OK = (35, 35, 35)

# Timing
MOVE_DELAY_MS = 500
ELIM_FLASH_MS = 3000
ELIM_FLASH_RATE_MS = 250

# Character limits
CH_MIN = 2
CH_MAX = 9
```

### Important Sections

#### 1. Rules Reference (Lines 130-350)
- Contains complete game rules documentation
- Used by the "Rules (PDF)" button
- Export function: `export_rules_and_open_async()` (Lines 4193-4243)
- Exports to: `docs/rules.pdf` or `docs/rules.txt`

#### 2. UI Components (Lines 4606-4623)
- Spectator/right-sidebar UI
- Button definitions registered in `UI_RECTS`
- Event loop handling (Lines 9212-9224)

#### 3. Export Rules Handler (Lines 4193-4243)
- Function: `export_rules_and_open_async()`
- Creates docs folder beside script
- Runs `tools/export_rules.py --out docs --quiet`
- Opens generated PDF/TXT with default app

---

## Complete Project Structure

### Required Folders and Files

```
Project Root (e.g., November03-2025/)/
│
├── Bishops_Golden.py          # Main game file
├── engine_adapter_v3.py       # Engine adapter for netplay
├── server_v3.py              # Server component
├── requirements.txt          # Python dependencies
├── server_settings.json      # Server configuration
├── teddy.ico                # Game icon
│
├── docs/                     # Documentation output
│   ├── rules.pdf            # Generated rules (PDF format)
│   ├── rules.txt            # Generated rules (text fallback)
│   └── flow.txt             # IPN workflow documentation
│
├── games/                    # Game recordings
│   ├── game_*.json          # Individual game files
│   ├── game_*.pgn.txt       # PGN format games
│   └── index.json           # Games library index
│
├── netplay/                  # Netplay components
│   ├── __init__.py
│   ├── server_v3.py         # Netplay server
│   └── engine_adapter_v3.py # Engine adapter
│
├── pieces/                   # Game piece assets
│   └── [piece image files]
│
├── tools/                    # Helper scripts
│   └── export_rules.py      # Rules export script
│
├── spares/                   # Backup/alternate files
│   └── Bishops_Golden.py    # Backup version
│
└── subscription/             # Subscription system (optional)
    ├── data/
    │   └── subscribers.json
    ├── docs/
    │   └── flow.txt
    ├── scripts/
    │   └── TODO.txt
    └── README.txt
```

---

## Netplay System

### Server Setup

#### VPS Configuration (IONOS)
- **Location**: Root folder on VPS
- **Upload**: Entire November03-2025 folder
- **Server File**: `netplay/server_v3.py`
- **Port**: 8200
- **Service**: systemd service named `netplay.service`

#### Systemd Service File
Location: `/etc/systemd/system/netplay.service`

```ini
[Unit]
Description=Bishops Netplay Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/November03-2025
Environment=PYTHONPATH=/root/November03-2025
ExecStart=/usr/bin/python3 -m netplay.server_v3
Restart=always
User=root

[Install]
WantedBy=multi-user.target
```

#### Service Commands
```bash
sudo systemctl daemon-reload
sudo systemctl restart netplay.service
systemctl status netplay.service
journalctl -u netplay.service -f
```

### Client Setup

#### Local Network Play (4 players on same WiFi)
1. Run server on one machine
2. Server listens on `0.0.0.0:8200`
3. Other players connect to `http://192.168.1.X:8200`
4. No VPS needed for local play

#### Distributed Files
- **netplay.zip**: Client/host launcher for customers
- **Contents**: Python/Pygame binaries + game files
- **Does NOT include**: Server components (those stay on VPS)

---

## Key Features & Buttons

### Spectator Panel Buttons

#### 1. "Rules (PDF)" Button
- **Handler**: `export_rules_and_open_async()`
- **Dependencies**: 
  - `tools/export_rules.py` script
  - Write access to `docs/` folder
  - Python subprocess permissions
- **Output**: 
  - Primary: `docs/rules.pdf`
  - Fallback: `docs/rules.txt`
- **Source**: `RULES_REFERENCE` constant (Lines 130-230)

#### 2. "Open Games Library" Button
- **Dependencies**: 
  - `games/` folder with content
  - `games/index.json` file
  - PGN format files: `game_*.pgn.txt`
- **Behavior**: Shows overlay or file browser with game history

#### 3. "Force Duel" Button
- **Dependencies**: 
  - Chess-duel assets
  - Piece images in `pieces/` folder
- **Note**: May be prevented if state machine is mid-animation

---

## Version History & Folders

### November03-2025 (PREFERRED/STABLE)
- **Status**: Stable, preferred version
- **Location**: `C:\Bishops_chatGPT\November03-2025`
- **Use**: Main development and VPS deployment
- **Features**: All core functionality working

### November07-2025
- **Status**: Copy of November03 with updated documentation
- **Changes**: 
  - Updated rules text
  - Sample PGN entries added
  - New teddy.ico icon
  - Same core code as November03

### November10-2025
- **Status**: Intended for subscription system integration
- **Note**: Later mirrored back to November03 code
- **Additions**: `subscription/` folder structure

---

## Website Integration

### Website Folder: Website1110-2025
Location: `C:\Bishops20231126\Website1110-2025`

#### Key Files
- `index.htm` - Homepage with $5/month subscription
- `checkout_realtime.htm` - PayPal subscription checkout
- `findyourflag.htm` - Flag selection page
- `rules.htm` - Rules display page
- `netplay.zip` - Downloadable client package

### Payment Flow
1. Customer visits website
2. Clicks flag or subscribe button
3. Redirected to `checkout_realtime.htm`
4. Pays $5/month via PayPal subscription
5. Receives email with download link to `netplay.zip`
6. Downloads and runs client
7. Connects to VPS server for online play

---

## Import Issues & Solutions

### Common Error
```
ImportError: attempted relative import with no known parent package
```

### Cause
Running `server_v3.py` directly instead of as module

### Solution
Run as module with PYTHONPATH set:
```bash
export PYTHONPATH=/root/November03-2025
python3 -m netplay.server_v3
```

OR use the systemd service (recommended)

---

## Running the Game

### Local Standalone
```bash
cd C:\Bishops_chatGPT\November03-2025
python Bishops_Golden.py
```

### With Netplay Server
```bash
cd C:\Bishops_chatGPT\November03-2025
python -m netplay.server_v3
```

### Expected Output
```
INFO: Will watch for changes in these directories: ['C:\Bishops_chatGPT\November03-2025']
INFO: Uvicorn running on http://0.0.0.0:8200 (Press CTRL+C to quit)
[EngineLoader] Using hard-coded golden engine from spares/Bishops_Golden.py
pygame 2.6.1 (SDL 2.28.4, Python 3.12.6)
[TP-Consolidated] Installed: any-square king entry, purge-off-8-8, 8-8 lock, winner overlay intact.
```

---

## VPS Deployment Checklist

### Files to Upload to VPS
- ✅ Complete `November03-2025/` folder
- ✅ All subdirectories: `docs/`, `games/`, `netplay/`, `pieces/`, `tools/`
- ✅ Configuration: `requirements.txt`, `server_settings.json`

### Files NOT for Customers
- ❌ Server components stay on VPS only
- ❌ `engine_adapter_v3.py` (server-side)
- ❌ `server_v3.py` (server-side)
- ❌ `subscription/` folder (server-side)

### Customer Download Package (netplay.zip)
- ✅ Client launcher
- ✅ Game assets (pieces, icons)
- ✅ Client-side Python/Pygame
- ✅ Connection scripts
- ❌ NO server components

---

## Troubleshooting

### Rules Button Opens Blank Window
**Causes**:
1. Missing `tools/export_rules.py` script
2. No write permission to `docs/` folder
3. Python can't spawn subprocess
4. PDF library (reportlab) not installed

**Solutions**:
1. Verify `tools/export_rules.py` exists
2. Run manually: `python tools/export_rules.py --out docs`
3. Check permissions on `docs/` folder
4. Install reportlab: `pip install reportlab`
5. Use fallback `rules.txt` if PDF fails

### Games Library Empty
**Causes**:
1. No files in `games/` folder
2. Missing `games/index.json`
3. No PGN format files

**Solutions**:
1. Add sample PGN files: `game_*.pgn.txt`
2. Create `games/index.json` with game list
3. Ensure folder exists and is readable

### Server Won't Start
**Causes**:
1. Running script directly instead of as module
2. Missing PYTHONPATH environment variable
3. Relative imports failing

**Solutions**:
1. Use: `python3 -m netplay.server_v3`
2. Set PYTHONPATH to project root
3. Use systemd service file (recommended)

---

## Required Python Packages

From `requirements.txt`:
- pygame
- fastapi (for server)
- uvicorn (for server)
- python-multipart
- Additional dependencies as needed

Install with:
```bash
pip install -r requirements.txt
```

---

## File Paths Reference

### On Windows (Development)
- Project: `C:\Bishops_chatGPT\November03-2025\`
- Website: `C:\Bishops20231126\Website1110-2025\`
- Desktop shortcut target: Points to November03-2025

### On Linux VPS (Production)
- Project: `/root/November03-2025/`
- Service: `/etc/systemd/system/netplay.service`
- Web root: `/var/www/vhosts/bishopsthegame.com/httpdocs/`

---

## Notes

1. **Always use November03-2025 as the stable/production version**
2. **Server components never go to customers - only netplay.zip**
3. **VPS gets the complete November03-2025 folder**
4. **Test locally before deploying to VPS**
5. **Keep backups of working configurations**
6. **Use systemd service for reliable server operation**
7. **Monitor logs with journalctl for debugging**

---

## Next Steps for Full Recreation

1. ✅ Main game file: `Bishops_Golden.py` (exists in workspace)
2. ⚠️ Need: `engine_adapter_v3.py` content
3. ⚠️ Need: `netplay/server_v3.py` content
4. ⚠️ Need: `tools/export_rules.py` content
5. ⚠️ Need: Complete `netplay/` folder structure
6. ⚠️ Need: Assets from `pieces/` folder
7. ⚠️ Need: Sample files for `games/` folder
8. ⚠️ Need: Complete `requirements.txt` package list

---

*This documentation extracted from Pieces0001.odt on December 5, 2025*
