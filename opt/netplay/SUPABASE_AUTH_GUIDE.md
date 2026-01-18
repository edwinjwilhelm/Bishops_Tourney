# Supabase Authentication Integration

## Overview

This integration connects Supabase email authentication to the Bishops game server, allowing users who sign in via email to claim game seats securely.

## How It Works

### **Without Authentication (Current Fallback)**
- Player types a username: `"Bob"`
- Anyone can type "Bob" and take over seats
- No protection against impersonation

### **With Supabase Authentication**
- Player signs in with email on landing page
- Gets a JWT token that proves their identity
- When connecting to game, sends token with WebSocket
- Server validates token and uses verified email as user ID
- Seat ownership is tied to verified email address
- No one else can steal the seat

## Setup Instructions

### 1. Install New Dependencies

On your **laptop**, update the requirements:

```powershell
cd c:\AL_Good_December11-2025\opt\netplay
pip install -r netplay/requirements.txt
```

On your **server** (via SSH):

```bash
ssh adminuser@74.208.171.115
cd ~/deployment/bishops-game/opt/netplay
# If you have a venv:
source .venv/bin/activate  # or activate equivalent
pip install -r netplay/requirements.txt
```

### 2. Get Your Supabase JWT Secret

1. Go to: https://supabase.com/dashboard/project/wqceqyycatcjggmxunte/settings/api
2. Find the section labeled **"JWT Secret"**
3. Click to reveal/copy the secret (starts with a long string)
4. **IMPORTANT:** This is different from the API keys - it's specifically the JWT secret

### 3. Set Environment Variable on Server

SSH into your server and set the JWT secret as an environment variable:

```bash
ssh adminuser@74.208.171.115

# Add to your shell profile (choose one based on your shell)
echo 'export SUPABASE_JWT_SECRET="your-jwt-secret-here"' >> ~/.bashrc
# OR if using zsh:
echo 'export SUPABASE_JWT_SECRET="your-jwt-secret-here"' >> ~/.zshrc

# Reload profile
source ~/.bashrc  # or source ~/.zshrc

# Verify it's set
echo $SUPABASE_JWT_SECRET
```

**For production**, you should set this in your server's systemd service file or process manager.

### 4. Restart Your Game Server

After setting the environment variable, restart your netplay server:

```bash
# If running manually:
cd ~/deployment/bishops-game/opt/netplay
python -m netplay.server_v3

# If using systemd (adjust service name):
sudo systemctl restart bishops-netplay
```

## Usage

### For Players

**Option 1: Authenticated (Secure Seats)**
1. Go to https://www.bishopsthegame.com
2. Scroll to "Sign up / Sign in"
3. Enter email and click "Send Magic Link"
4. Check email and click the login link
5. Go to game: https://play.bishopsthegame.com/static/index_v3.html
6. You'll see "🔒 Signed in as: your@email.com"
7. Select a seat and click Connect
8. Your seat is now protected - only you can control it

**Option 2: Guest (Legacy Username)**
1. Go directly to game: https://play.bishopsthegame.com/static/index_v3.html
2. Type any username
3. Connect to a seat
4. Anyone can use your username (no protection)

### For Developers

**Check if authentication is working:**

Open browser console on the game page:
```javascript
// Check if user is authenticated
const { data } = await supabase.auth.getSession();
console.log(data.session?.user.email); // Should show email if logged in
```

**Test the WebSocket connection:**

Look in the Network tab for the WebSocket connection:
- If authenticated: `ws://...?token=eyJ...` (token parameter present)
- If guest: `ws://...?user=Bob` (no token, just username)

## Features Enabled

With authentication, you can now:

✅ **Secure seat ownership** - Email-verified users control their seats
✅ **Prevent impersonation** - Can't steal someone else's seat
✅ **Ready for future features:**
   - Player statistics (wins/losses per email)
   - Rating/ranking systems
   - Game history ("your last 10 games")
   - Reconnection (rejoin your seat automatically)
   - Private tables (invite-only by email)
   - Friend lists

## Architecture

### Client Side (index_v3.html)
- Checks for Supabase session on page load
- If authenticated, displays email with 🔒 badge
- Sends JWT token in WebSocket URL: `?token=xxx`
- Falls back to username if not authenticated

### Server Side (server_v3.py)
- Checks for `token` parameter in WebSocket connection
- Validates JWT token with Supabase JWT secret
- Extracts verified email from token
- Uses email as `user_id` (overrides username)
- Falls back to username authentication if no token

### Authentication Module (supabase_auth.py)
- `validate_supabase_token()` - Validates JWT tokens
- `get_user_email()` - Extracts email from valid tokens
- Uses PyJWT library for secure token validation
- Checks expiration, audience, and signature

## Security Notes

1. **JWT Secret is sensitive** - Never commit it to Git
2. **Tokens expire** - Users will need to re-login periodically
3. **HTTPS required** - Tokens should only be sent over HTTPS in production
4. **Fallback exists** - If auth fails, system falls back to username

## Troubleshooting

**"Invalid API key" error:**
- Check that you have the correct JWT Secret (not the anon key)
- Verify environment variable is set: `echo $SUPABASE_JWT_SECRET`

**"User required" error:**
- User needs to either sign in OR enter a username
- Check browser console for auth errors

**Token validation fails:**
- JWT secret might be wrong
- Token might be expired (user needs to re-login)
- Check server logs for specific JWT errors

**Can't see authenticated status:**
- Clear browser cache
- Make sure user signed in on landing page first
- Check browser console for JavaScript errors

## Next Steps

Potential enhancements:
- [ ] Store player stats in Supabase database
- [ ] Add ELO rating system
- [ ] Implement game history viewer
- [ ] Create admin dashboard for user management
- [ ] Add reconnection logic (auto-rejoin on disconnect)
- [ ] Implement private/invite-only tables
- [ ] Add friend list and invitations
- [ ] Tournament mode with brackets
