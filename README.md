<img width="800" height="397" alt="Screenshot 2026-05-03 at 12 27 16 PM" src="https://github.com/user-attachments/assets/4a4bcbf4-c315-4519-a2c6-b3544844d636" />
 12.27.16 PM.png…]()


# 📺 YT Schedule Maker

A Python + Flask web app that connects to your YouTube account, lets you **pick specific videos from each subscribed channel**, and generates a month-wise **Excel watch schedule** — complete with daily time budgets, revision slots, and India national holidays.

---

## ✨ Features

- **OAuth login** — read-only access to your YouTube subscriptions
- **Channel grid** — browse, search and filter all subscribed channels (Tech / Finance / Skipped)
- **Video picker panel** — open any channel, see all recent videos, check/uncheck individual ones
- **Smart scheduling** — splits long videos across days to fit your daily time budget
- **Revision time** — adds practice buffer after each video
- **Live holidays** — India national holidays fetched from [Calendarific API](https://calendarific.com), auto-assigned 3h budget
- **Excel output** — one sheet per month, clickable video links, Watched / Practiced dropdowns
- **Incremental runs** — only new videos are added; existing ticks are never overwritten

---

## 🖥️ Preview

```
┌─────────────────────────────────────────────────────────────┐
│  📺 YTSchedule   ● YouTube Connected   📅 Schedule From     │
├──────────────┬──────────────────────────────────────────────┤
│  Overview    │  🔍 Search...   All  Tech  Finance  Skipped  │
│  Channels 42 │                                              │
│  Videos   17 │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│              │  │ Fireship │  │ ThePrimeA│  │ Theo  t3 │  │
│  Selection   │  │  ✓ 3/12  │  │  ✓ 5/8  │  │  0/6     │  │
│  3 channels  │  │ View Vids│  │ View Vids│  │ View Vids│  │
│  17 videos   │  └──────────┘  └──────────┘  └──────────┘  │
├──────────────┤                                              │
│  Config      │                                              │
│  Weekday 1.5h│                          ⚡ Generate Schedule│
└──────────────┴──────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1 — Clone the repo
```bash
git clone https://github.com/SahilLoona-ios/yt-schedule-maker.git
cd yt-schedule-maker
```

### 2 — Set up Python environment
```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3 — Add Google credentials

1. Create a project in [Google Cloud Console](https://console.cloud.google.com)
2. Enable **YouTube Data API v3**
3. Create an **OAuth 2.0 Desktop App** credential
4. Download and rename it to `client_secret.json`
5. Place it in the project root

> See [SETUP.md](SETUP.md) for detailed steps.

### 4 — Add Calendarific API key

1. Sign up free at [calendarific.com](https://calendarific.com/sign-up) (1000 calls/month, no credit card)
2. Copy your API key from the dashboard
3. Create a `.env` file in the project root:

```bash
CALENDARIFIC_API_KEY=your_api_key_here
```

> `.env` is gitignored — never committed to the repo.

### 5 — Run
```bash
python server.py
```

Open **http://localhost:5000** in your browser.

---

## 📖 Full Setup Guide

→ See **[SETUP.md](SETUP.md)** for:
- Google Cloud Console walkthrough (with every click explained)
- OAuth consent screen configuration
- Calendarific API key setup
- Dashboard usage guide
- Excel output explained
- Cron / Task Scheduler automation
- All troubleshooting errors

---

## 📁 File Structure

```
yt-schedule-maker/
├── server.py            ← Flask API + serves dashboard  ← RUN THIS
├── dashboard.html       ← Web UI (auto-served)
├── main.py              ← CLI alternative
├── auth.py              ← Google OAuth
├── config.py            ← All settings
├── channel_filter.py    ← Tech/Finance classification
├── youtube_client.py    ← YouTube API wrapper
├── scheduler.py         ← Session splitting logic
├── excel_writer.py      ← Excel builder
├── state_manager.py     ← Incremental run state
└── requirements.txt

 ── Create these locally (gitignored) ──
├── .env                 ← CALENDARIFIC_API_KEY=your_key
├── client_secret.json   ← Google OAuth credentials  ⚠️ keep private
├── token.pickle         ← Saved login token (auto-generated)
└── state.json           ← Tracks scheduled videos (auto-generated)
```

---

## ⚙️ Configuration

Edit `config.py` to change defaults:

```python
WEEKDAY_BUDGET_HOURS = 1.5      # Mon–Fri
WEEKEND_BUDGET_HOURS = 3.0      # Sat–Sun
REVISION_MINUTES     = 30       # Practice buffer per video
VIDEOS_START_DATE    = "2026-01-01"
SKIP_CHANNELS        = ["iOS Labs", "tunsdev", "Paul Hudson"]
```

---

## 📊 API Quotas

| API | Free Limit | Used Per Run |
|-----|-----------|-------------|
| YouTube Data API v3 | 10,000 units/day | ~150–300 units |
| Calendarific | 1,000 calls/month | 1 call on server start |

No billing required for either.

---

## 🛠️ Built With

- Python 3.10+
- Flask 3.0
- YouTube Data API v3
- Calendarific API (India national holidays)
- openpyxl
- google-auth-oauthlib
- python-dotenv
