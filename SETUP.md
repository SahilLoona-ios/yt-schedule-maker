# 📺 YouTube Schedule Tracker — Complete Setup Guide

> A Python + Flask tool that connects to your YouTube account, fetches videos from your
> tech subscriptions, and builds a month-wise Excel watch schedule — with a full web dashboard.

---

## 📋 Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Download the Project](#2-download-the-project)
3. [Google Cloud Console Setup](#3-google-cloud-console-setup)
4. [Enable YouTube Data API](#4-enable-youtube-data-api)
5. [Create OAuth Credentials](#5-create-oauth-credentials)
6. [Configure OAuth Consent Screen](#6-configure-oauth-consent-screen)
7. [Calendarific API Key (Holidays)](#7-calendarific-api-key-holidays)
8. [Project Setup (Python Environment)](#8-project-setup-python-environment)
9. [Run the Dashboard](#9-run-the-dashboard)
10. [Using the Dashboard](#10-using-the-dashboard)
11. [Understanding the Excel Output](#11-understanding-the-excel-output)
12. [Automate with Cron](#12-automate-with-cron)
13. [Configuration Reference](#13-configuration-reference)
14. [File Structure](#14-file-structure)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Prerequisites

Before starting, make sure you have the following installed:

### Check Python (need 3.10+)
```bash
python3 --version
```
If not installed:
```bash
# macOS
brew install python

# Ubuntu/Debian
sudo apt install python3 python3-pip
```

### Check pip
```bash
pip3 --version
```

### Check Git (optional, for cloning)
```bash
git --version
```

---

## 2. Download the Project

Create a folder and place all project files inside it:

```bash
mkdir yt_tracker
cd yt_tracker
```

Your folder should contain these files:
```
yt_tracker/
├── server.py
├── dashboard.html
├── main.py
├── auth.py
├── config.py
├── channel_filter.py
├── youtube_client.py
├── scheduler.py
├── excel_writer.py
├── state_manager.py
└── requirements.txt
```

> ⚠️ All files must be in the **same folder**. Do not put them in subfolders.

---

## 3. Google Cloud Console Setup

This project uses the **YouTube Data API v3** which requires Google Cloud credentials.

### Step 1 — Create a Google Cloud Project

1. Open your browser and go to:
   ```
   https://console.cloud.google.com
   ```

2. Sign in with your **Google account** (the same one whose YouTube subscriptions you want to use)

3. Click the **project selector dropdown** at the top (it may say "Select a project")

4. Click **"New Project"**

5. Fill in:
   - **Project name:** `yt-tracker` (or anything you like)
   - **Location:** No organisation

6. Click **"Create"**

7. Wait a few seconds, then make sure your new project is **selected** in the top dropdown

---

## 4. Enable YouTube Data API

1. In the left sidebar, click **"APIs & Services"** → **"Library"**

2. In the search box, type:
   ```
   YouTube Data API v3
   ```

3. Click on **"YouTube Data API v3"** from the results

4. Click the blue **"Enable"** button

5. Wait for it to enable (takes 10–20 seconds)

> ✅ You should see the API overview page — this means it's enabled.

---

## 5. Create OAuth Credentials

1. In the left sidebar, go to **"APIs & Services"** → **"Credentials"**

2. Click **"+ Create Credentials"** at the top

3. Select **"OAuth client ID"**

4. Under **"Application type"**, select **"Desktop app"**

5. Under **"Name"**, type: `yt-tracker-desktop`

6. Click **"Create"**

7. A popup will appear — click **"Download JSON"**

8. A file will download with a name like `client_secret_xxxx.apps.googleusercontent.com.json`

9. **Rename it** to exactly:
   ```
   client_secret.json
   ```

10. **Move it** into your `yt_tracker/` project folder

> ⚠️ This file is your private key. Never share it or upload it to GitHub.

---

## 6. Configure OAuth Consent Screen

This step is required to allow your own Gmail to log in.

1. In the left sidebar, go to **"APIs & Services"** → **"OAuth consent screen"**

2. Under **"User Type"**, if it says **"Internal"** — click **"MAKE EXTERNAL"** and confirm

   > If you get an error about Google Workspace, select **External** from the start

3. Fill in the required fields:
   - **App name:** `YT Tracker`
   - **User support email:** your Gmail
   - **Developer contact email:** your Gmail

4. Click **"Save and Continue"**

5. On the **Scopes** page — click **"Save and Continue"** (no changes needed)

6. On the **Test Users** page:
   - Click **"+ Add Users"**
   - Enter your **Gmail address**
   - Click **"Add"**

7. Click **"Save and Continue"**

8. Click **"Back to Dashboard"**

> ✅ Your Gmail is now a test user — the OAuth login will work for you.

---

## 7. Calendarific API Key (Holidays)

The dashboard displays India national holidays and automatically assigns a **3h budget** on those days. Holidays are fetched live from the [Calendarific API](https://calendarific.com) — no hardcoded lists.

### Step 1 — Sign up for a free account

1. Go to: [https://calendarific.com/sign-up](https://calendarific.com/sign-up)
2. Fill in your email and password — no credit card needed
3. Verify your email address

### Step 2 — Get your API key

1. Log in and go to your [API dashboard](https://calendarific.com/account)
2. Copy the **API Key** shown on the page

### Step 3 — Create a `.env` file

In your project folder, create a file named `.env` (note the dot):

```bash
CALENDARIFIC_API_KEY=paste_your_key_here
```

> ⚠️ `.env` is listed in `.gitignore` — it will never be committed to GitHub.
> Never share this key or paste it into any code file.

**Free tier limits:**
- 1,000 API calls/month
- The app makes **1 call per year** on server start — well within limits

---

## 8. Project Setup (Python Environment)

Run all these commands from inside your `yt_tracker/` folder.

### Step 1 — Create a virtual environment
```bash
python3 -m venv venv
```

### Step 2 — Activate it
```bash
# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

> You'll see `(venv)` appear at the start of your terminal prompt. This means it's active.

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

This installs:
- `google-auth`, `google-auth-oauthlib` — OAuth authentication
- `google-api-python-client` — YouTube API
- `openpyxl` — Excel file creation
- `flask`, `flask-cors` — Web dashboard server

### Step 4 — Verify client_secret.json is in place
```bash
ls client_secret.json
```
You should see the file listed. If not, go back to [Step 5](#5-create-oauth-credentials).

---

## 9. Run the Dashboard

### Start the server
```bash
# Make sure venv is active (you see (venv) in terminal)
source venv/bin/activate

python server.py
```

You should see:
```
══════════════════════════════════════════════════
  📺  YT Schedule Dashboard
  🌐  Open: http://localhost:5000
══════════════════════════════════════════════════
```

### Open the Dashboard
Open your browser and go to:
```
http://localhost:5000
```

> 🎉 The dashboard should load with a dark interface.

---

## 10. Using the Dashboard

### Step 1 — Connect YouTube

1. Click the **"Connect YouTube →"** button in the centre of the screen
   *(or click the red badge in the top-left)*

2. Your **default browser will open** a Google login page

3. Select your Google account

4. You may see **"Google hasn't verified this app"** — this is expected since it's your personal app
   - Click **"Advanced"**
   - Click **"Go to YT Tracker (unsafe)"**

5. Click **"Allow"** to grant read-only YouTube access

6. The browser tab will show a success message and close automatically

7. Back in the dashboard — the badge should turn **green** saying `● YouTube Connected`

> ✅ A `token.pickle` file is saved in your project folder — you won't need to log in again.

---

### Step 2 — Browse Your Channels

After connecting, the dashboard will:
- Fetch all your subscribed channels (may take 20–40 seconds)
- Automatically classify each as **Tech** or **Finance**
- Show them in a searchable, filterable grid

**Filter options:**
| Tab | Shows |
|-----|-------|
| All | Every subscribed channel |
| Tech | Auto-detected tech/coding channels ✅ |
| Finance | Auto-detected finance channels ⛔ |
| Skipped | Channels in your skip list ⚠️ |

**To search:** Type in the search box to filter by channel name

---

### Step 3 — Select Channels

- By default, all **Tech** channels are pre-selected (teal border)
- **Click any card** to toggle selection on/off
- Use **"✓ Select All Tech"** to select all tech channels at once
- Use **"✕ Deselect All"** to clear all selections
- The **Selected** counter in the sidebar updates live

---

### Step 4 — Configure Your Schedule

In the left sidebar, adjust:

| Setting | What it does |
|---------|-------------|
| **Videos Start Date** | Only fetch videos uploaded after this date (default: 2026-01-01) |
| **Weekday Budget** | Hours available Mon–Fri (default: 1.5h) |
| **Weekend Budget** | Hours available Sat–Sun (default: 3.0h) |
| **Revision Time** | Minutes added after each video for practice (default: 30m) |
| **Skip Channels** | Channels always excluded — type a name and press Enter to add |

> India national holidays are automatically given a **3h budget** regardless of weekday/weekend setting. Holidays are fetched live from Calendarific API — no manual updates needed.

---

### Step 5 — Generate Schedule

1. Click **"⚡ Generate Schedule"** (top-right or bottom of sidebar)

2. A progress overlay appears showing real-time steps:
   ```
   Connecting to YouTube API…        5%
   Loading subscriptions…           10%
   Fetching videos for N channels…  20%
   Collecting video IDs…            35%
   Fetching video details…          55%
   Building schedule…               70%
   Writing Excel…                   85%
   Done! ✅                         100%
   ```

3. When done — click **"⬇ Download Excel"** to save `yt_schedule.xlsx`

---

### Subsequent Runs (Incremental Updates)

When you run the script again:
- Only **new videos** (uploaded since last run) are fetched
- New sessions are **appended** to the existing Excel file
- Your existing checkbox ticks are **never overwritten**
- A 3-day buffer ensures no videos are missed due to upload delays

---

## 11. Understanding the Excel Output

The Excel file has **one sheet per month** (e.g. `Jan 2026`, `Feb 2026`).

### Columns

| Column | Description |
|--------|-------------|
| # | Row number |
| Channel | Channel name |
| Video Title | Clickable hyperlink to the video |
| Published | Date the video was uploaded |
| Duration | Total video length |
| Part | "1/3", "2/3", "Full" — which part of a split video |
| Date | Your scheduled watch date |
| Weekday | Monday, Tuesday… |
| From | Start timestamp — e.g. `0:00:00` |
| To | End timestamp — e.g. `1:30:00` |
| Session | Duration of this session |
| Revision | "+30 min" shown on the last part only |
| **Watched** | Dropdown: `☐ Pending` → `☑ Watched` |
| **Practiced** | Dropdown: `☐ Pending` → `☑ Practiced` (last part only) |

### Colour Coding

| Colour | Meaning |
|--------|---------|
| 🟩 Dark green row | Both Watched ✓ and Practiced ✓ |
| 🟢 Light green row | Only Watched ✓ |
| 🔵 Teal row | Only Practiced ✓ |
| Normal row | Not yet started |

### How Video Splitting Works

```
Example: 3h video, 1.5h weekday budget, 30min revision

Monday   → Watch  0:00:00 – 1:30:00  (1h 30m)
Tuesday  → Watch  1:30:00 – 3:00:00  (1h 30m)  +30min revision
Wednesday → Next video starts
```

---

## 12. Automate with Cron

Run the schedule builder automatically every week so new videos are added without manual intervention.

### macOS / Linux — Cron

Open crontab editor:
```bash
crontab -e
```

Add this line to run every Monday at 8:00 AM:
```bash
0 8 * * 1 cd /full/path/to/yt_tracker && /full/path/to/yt_tracker/venv/bin/python3 server.py &
```

Or to just regenerate the Excel silently (no dashboard):
```bash
0 8 * * 1 cd /full/path/to/yt_tracker && /full/path/to/yt_tracker/venv/bin/python3 main.py >> yt_tracker.log 2>&1
```

> Replace `/full/path/to/yt_tracker` with your actual folder path.
> Find it by running `pwd` inside the folder.

### Windows — Task Scheduler

1. Open **Task Scheduler** (search in Start menu)
2. Click **"Create Basic Task"**
3. Name: `YT Schedule Tracker`
4. Trigger: **Weekly** → Monday → 8:00 AM
5. Action: **Start a program**
   - Program: `C:\path\to\yt_tracker\venv\Scripts\python.exe`
   - Arguments: `C:\path\to\yt_tracker\main.py`
   - Start in: `C:\path\to\yt_tracker`
6. Click **Finish**

---

## 13. Configuration Reference

Edit `config.py` to change defaults permanently:

```python
# ── Watch Schedule ──────────────────────────────
WEEKDAY_BUDGET_HOURS = 1.5      # Mon–Fri daily hours
WEEKEND_BUDGET_HOURS = 3.0      # Sat–Sun daily hours
REVISION_MINUTES     = 30       # Extra time after each video

# ── Video Date Range ────────────────────────────
VIDEOS_START_DATE = "2026-01-01"  # Fetch videos from this date onwards

# ── Output Files ────────────────────────────────
OUTPUT_FILE = "yt_schedule.xlsx"   # Excel output filename
STATE_FILE  = "state.json"         # Tracks what's already scheduled

# ── Always Skip These Channels ──────────────────
SKIP_CHANNELS = [
    "iOS Labs",
    "tunsdev",
    "Paul Hudson",
    # Add more here
]
```

> ⚠️ Changes to `config.py` take effect on the next run.
> Dashboard sliders override these values at runtime for that session only.

---

## 14. File Structure

```
yt_tracker/
│
├── server.py              ← Flask API + serves dashboard  (RUN THIS)
├── dashboard.html         ← Web UI (served automatically by server.py)
├── main.py                ← CLI entry point (alternative to dashboard)
│
├── auth.py                ← Google OAuth token management
├── config.py              ← All configuration values
├── channel_filter.py      ← Tech vs finance classification logic
├── youtube_client.py      ← YouTube API wrapper (quota-efficient)
├── scheduler.py           ← Daily session splitting logic
├── excel_writer.py        ← Excel builder with formatting
├── state_manager.py       ← Tracks scheduled videos between runs
│
├── requirements.txt       ← Python dependencies
│
│  ── Create these locally — gitignored, never commit ──
├── .env                   ← CALENDARIFIC_API_KEY=your_key  ⚠️ keep private
├── client_secret.json     ← Google OAuth credentials       ⚠️ keep private
│
│  ── Auto-generated (do not delete) ──
├── venv/                  ← Python virtual environment
├── token.pickle           ← Saved login token (auto-refreshes)
├── state.json             ← Tracks last run state (prevents duplicates)
└── yt_schedule.xlsx       ← Your generated Excel schedule
```

---

## 15. Troubleshooting

### ❌ `zsh: command not found: pip`
Use `pip3` instead:
```bash
pip3 install -r requirements.txt
```
Or use the full path:
```bash
python3 -m pip install -r requirements.txt
```

---

### ❌ `externally-managed-environment` error
You're trying to install outside a virtual environment. Always activate venv first:
```bash
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

---

### ❌ `Error 403: org_internal`
Your OAuth consent screen is set to **Internal**. Fix:
1. Go to Google Cloud Console → APIs & Services → OAuth consent screen
2. Click **"MAKE EXTERNAL"**
3. Save and try again

---

### ❌ `accessNotConfigured` — YouTube API not enabled
Click the link in the error message, or:
1. Go to Google Cloud Console → APIs & Services → Library
2. Search **YouTube Data API v3**
3. Click **Enable**
4. Wait 2 minutes, then retry

---

### ❌ `FileNotFoundError: client_secret.json not found`
The credentials file is missing or misnamed. Make sure:
- The file is named exactly `client_secret.json` (no extra text)
- It's in the same folder as `server.py`
- You downloaded it from the correct Google Cloud project

---

### ❌ `Cannot reach server` in browser
The Flask server isn't running. In your terminal:
```bash
source venv/bin/activate
python server.py
```
Then open `http://localhost:5000`

---

### ❌ `file_cache is only supported with oauth2client<4.0.0`
This is just a **warning**, not an error. The script will continue working fine — you can ignore it.

---

### ❌ Channels not loading / stuck on spinner
1. Check the terminal where `server.py` is running for error messages
2. Try clicking **"↺ Refresh"** in the dashboard header
3. If quota exceeded — wait until midnight (Pacific Time) for quota reset

---

### ❌ No new videos found on re-run
This is expected if:
- No new videos were uploaded since your last run
- The `VIDEOS_START_DATE` in `config.py` is in the future
- All recent videos are already in `state.json`

To force a full re-fetch, delete `state.json`:
```bash
rm state.json
```
> ⚠️ This will re-schedule all videos from the start date. Existing Excel rows are preserved (new rows will be appended).

---

### ❌ Token expired / login required again
Delete the token file and re-authenticate:
```bash
rm token.pickle
python server.py
```
Then connect again from the dashboard.

---

## 🔑 Important Files to Never Delete

| File | Why |
|------|-----|
| `token.pickle` | Your saved login — deleting forces re-login |
| `state.json` | Tracks scheduled videos — deleting causes full re-schedule |
| `client_secret.json` | Your API credentials — deleting requires re-downloading from Google Cloud |
| `venv/` | Your Python environment — deleting requires re-running `pip install` |

---

## 📊 YouTube API Quota

| Action | Quota Cost |
|--------|-----------|
| Fetch subscriptions (100 channels) | ~2 units |
| Fetch channel details (100 channels) | ~2 units |
| Fetch upload playlists | ~1 unit/channel |
| Fetch video details (50 videos) | 1 unit |
| **Typical full run** | **~150–300 units** |
| **Daily free quota** | **10,000 units** |

You are well within the free tier. No billing required.

---

*Last updated: May 2026 | Built with Python 3.10+, Flask 3.0, YouTube Data API v3, Calendarific API, openpyxl, python-dotenv*
