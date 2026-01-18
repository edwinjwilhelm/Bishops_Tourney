# Bishops Game - Deployment Guide

## ✅ What's Set Up

- **Git** installed on your laptop
- **GitHub repository**: https://github.com/edwinjwilhelm/bishops-game
- **Automated deployment** script on your server
- **Permissions** fixed (adminuser + netplay group)

---

## 🚀 Daily Workflow: How to Update Your Website

### 1. Edit Files Locally (in VS Code)
Make changes to any file in `c:\AL_Good_December11-2025\`

### 2. Commit Changes (Save to Git)
Open PowerShell in VS Code and run:
```powershell
# Stage your changed files
git add .

# Commit with a message describing what you changed
git commit -m "Your description here"
```

### 3. Push to GitHub
```powershell
git push
```

### 4. Deploy to Live Website
SSH into your server and run the deploy script:
```powershell
# Connect to server
ssh adminuser@74.208.171.115

# Run deployment script
~/deploy.sh

# Exit server
exit
```

**That's it!** Your changes are now live.

---

## 📝 Example: Making a Small Change

Let's say you want to update the website description:

```powershell
# 1. Edit the file in VS Code (make your changes)

# 2. Stage and commit
git add opt/netplay/netplay/static/index.html
git commit -m "Updated website description"

# 3. Push to GitHub
git push

# 4. Deploy to server
ssh adminuser@74.208.171.115
~/deploy.sh
exit
```

Done! Website updated.

---

## 🔧 Useful Commands

### Check what files changed:
```powershell
git status
```

### See your commit history:
```powershell
git log --oneline
```

### Undo local changes (before commit):
```powershell
git checkout -- filename.html
```

### See what you changed:
```powershell
git diff
```

---

## 🆘 Troubleshooting

### "Permission denied" error on server?
Run this on the server:
```bash
sudo chown -R netplay:netplay /opt/netplay/netplay/static/
sudo chmod -R 775 /opt/netplay/netplay/static/
```

### Forgot to commit before editing?
```powershell
git add .
git commit -m "Describe your changes"
```

### Need to rollback to previous version?
```powershell
git log --oneline  # Find the commit ID you want
git checkout COMMIT_ID -- path/to/file
git commit -m "Rolled back to previous version"
git push
```

---

## 📦 What NOT to Commit

Already configured in `.gitignore`:
- Virtual environments (`.venv/`)
- Python cache files (`__pycache__/`)
- IDE settings (`.vscode/`, `.idea/`)
- OS files (`.DS_Store`, `Thumbs.db`)
- Logs (`*.log`)

---

## 🔐 Important Files

- **GitHub Personal Access Token**: `<REDACTED>`
  - Used for: Server to pull from GitHub
  - Expires: In 90 days (regenerate before expiry)
  
- **Supabase API Key**: In `index.html`
  - URL: `https://wqceqyycatcjggmxunte.supabase.co`
  - Key starts with: `eyJhbGciOiJIUzI1NiIs...`

---

## 🎯 Summary

**Before (FileZilla method):**
1. Edit file
2. Open FileZilla
3. Find file
4. Upload manually
5. Deal with permission errors
6. Repeat for each file

**Now (Git method):**
1. Edit files
2. `git add . && git commit -m "message" && git push`
3. `ssh adminuser@74.208.171.115` → `~/deploy.sh` → `exit`

**Result:** Faster, safer, professional workflow with version history!

---

## 📞 Need Help?

- Git documentation: https://git-scm.com/doc
- GitHub help: https://docs.github.com
- Supabase docs: https://supabase.com/docs
