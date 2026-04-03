# RSAF Daily Web Monitoring Agent

An automated agent that searches the public web every night for new mentions of the Republic of Singapore Air Force (RSAF), analyses them with AI, and sends you a concise morning briefing by email.

Built for communications professionals who need to stay on top of RSAF media coverage without manually checking dozens of sources.

---

## What It Does

Every night, this agent:

1. **Searches** the web for new RSAF mentions across news sites, defence media, blogs, forums, and government sites
2. **Extracts** article content, metadata, and publication details
3. **Deduplicates** aggressively — syndicated copies and near-identical rewrites are merged
4. **Filters** out false matches (e.g., "RSAF" meaning Royal Saudi Air Force)
5. **Summarises** each article in 2-3 sentences
6. **Assesses sentiment** — positive, neutral, mixed, or negative (lightweight directional, not deep analysis)
7. **Assesses impact** — reputational risk, media interest, public concern, operational and stakeholder sensitivity
8. **Generates a digest** with executive summary, key developments, themes, and recommended follow-up
9. **Emails you** a mobile-friendly morning briefing

---

## Quick Start (Step by Step)

### Prerequisites

- A computer with **Python 3.10 or newer** installed
- An **Anthropic API key** (for the AI analysis) — get one at https://console.anthropic.com/
- A **Gmail account** (or other SMTP email) for sending the briefing

### Step 1: Download the project

```bash
# If you have git:
git clone <your-repo-url>
cd rsaf-monitor

# Or just download and unzip the folder, then open a terminal in it.
```

### Step 2: Create a virtual environment

This keeps the project's packages separate from your system Python.

```bash
python3 -m venv venv
```

### Step 3: Activate the virtual environment

**macOS / Linux:**
```bash
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

You should see `(venv)` at the start of your terminal prompt.

### Step 4: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Set up your configuration

```bash
cp .env.example .env
```

Now open `.env` in any text editor and fill in:

| Variable | What to put |
|----------|------------|
| `RSAF_ANTHROPIC_API_KEY` | Your Anthropic API key (starts with `sk-ant-`) |
| `RSAF_SMTP_USERNAME` | Your Gmail address |
| `RSAF_SMTP_PASSWORD` | A Gmail **App Password** (not your regular password — see below) |
| `RSAF_SENDER_EMAIL` | Same as your Gmail address |
| `RSAF_RECIPIENT_EMAIL` | The email address to receive the briefing |

**How to create a Gmail App Password:**
1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and your device
3. Click "Generate"
4. Copy the 16-character password into your `.env` file

### Step 6: Test with mock data

This runs the full pipeline using sample articles, without searching the web or sending email:

```bash
python -m rsaf_monitor.main --mock --dry-run
```

Check the `reports/` folder — you should see three files:
- `rsaf_digest_YYYY-MM-DD.txt` (email text)
- `rsaf_digest_YYYY-MM-DD.md` (Markdown report)
- `rsaf_digest_YYYY-MM-DD.json` (structured data)

### Step 7: Test with real search (no email)

```bash
python -m rsaf_monitor.main --test --dry-run
```

This searches the web with a short lookback window. Check the reports folder for results.

### Step 8: Full run with email

```bash
python -m rsaf_monitor.main
```

This searches, analyses, and sends the email.

---

## How to Schedule It Nightly

### Option A: Cron (Recommended — macOS and Linux)

Cron is the standard Unix task scheduler. It runs your script at a set time without needing any extra software.

**Step 1:** Find your Python path:
```bash
which python3
# Example output: /home/you/rsaf-monitor/venv/bin/python3
```

**Step 2:** Open your crontab:
```bash
crontab -e
```

**Step 3:** Add this line (runs at 2:00 AM every day):
```cron
0 2 * * * cd /path/to/rsaf-monitor && /path/to/rsaf-monitor/venv/bin/python3 -m rsaf_monitor.main >> /path/to/rsaf-monitor/logs/cron.log 2>&1
```

Replace `/path/to/rsaf-monitor` with the actual path to your project folder.

**Why 2 AM?** This gives the script time to run overnight. Your email arrives by morning.

**To change the time:** The format is `minute hour * * *`. For 5:30 AM: `30 5 * * *`

### Option B: Python Scheduler (Fallback)

If you can't use cron (e.g., on Windows):

```bash
pip install schedule
python -m rsaf_monitor.scheduler --time 02:00
```

This runs as a long-lived process. Keep the terminal open or run it as a background service.

**Cron is preferred** because it's simpler, uses no memory when idle, and automatically handles restarts.

---

## How to Change Settings

### Change the recipient email

Edit `.env` and change:
```
RSAF_RECIPIENT_EMAIL=new-recipient@example.com
```

### Change the keywords

Edit `config.yaml` and modify the `keywords` list under `search:`. You can add or remove any keyword. Queries in double quotes search for exact phrases.

### Change the search provider

The default (DuckDuckGo) is free but limited. For better results:

**SerpAPI** (recommended upgrade — has a free tier):
1. Sign up at https://serpapi.com/
2. Add to `.env`:
   ```
   RSAF_SEARCH_PROVIDER=serpapi
   RSAF_SERPAPI_KEY=your-key-here
   ```

**Google Custom Search:**
1. Set up at https://programmablesearchengine.google.com/
2. Add to `.env`:
   ```
   RSAF_SEARCH_PROVIDER=google_cse
   RSAF_GOOGLE_CSE_API_KEY=your-key
   RSAF_GOOGLE_CSE_CX=your-cx-id
   ```

### Change the AI model

Edit `.env`:
```
RSAF_LLM_MODEL=claude-sonnet-4-20250514
```

---

## Troubleshooting

### "No articles found"
- Normal if there's genuinely no RSAF coverage that day
- Try `--test` mode with a longer lookback: edit `test_lookback_hours: 72` in `config.yaml`
- Check `logs/rsaf_monitor.log` for search errors

### "SMTP authentication failed"
- Make sure you're using a Gmail **App Password**, not your regular password
- Check that 2-factor authentication is enabled on your Google account
- Verify `RSAF_SMTP_USERNAME` matches your Gmail address exactly

### "anthropic package not installed"
- Make sure your virtual environment is activated: `source venv/bin/activate`
- Reinstall: `pip install -r requirements.txt`

### "Rate limited" or "Too many requests"
- Increase `request_delay_seconds` in `config.yaml` (try 5.0)
- Reduce the number of keywords
- Switch to SerpAPI for more reliable results

### Email not received
- Check your spam/junk folder
- Check `logs/rsaf_monitor.log` for send errors
- Try `--dry-run` first to confirm the pipeline works, then test email separately

### Reports are generated but empty
- The search may not have found relevant results
- Check the log file for "Filtered out" messages — the relevance filter may be too strict
- Try broader keywords

---

## Project Structure

```
rsaf-monitor/
├── rsaf_monitor/           # Main Python package
│   ├── __init__.py
│   ├── __main__.py         # Allows: python -m rsaf_monitor
│   ├── main.py             # Pipeline orchestrator
│   ├── config.py           # Configuration management
│   ├── search.py           # Web search + RSS layer
│   ├── extract.py          # Content extraction
│   ├── dedupe.py           # Deduplication
│   ├── analyze.py          # LLM analysis (Claude)
│   ├── report.py           # Report generation
│   ├── deliver.py          # Email delivery
│   ├── storage.py          # SQLite database
│   ├── prompts.py          # All LLM prompts
│   ├── scheduler.py        # Python scheduler (Option B)
│   └── utils.py            # Shared utilities
├── tests/                  # Unit tests
│   ├── test_dedupe.py
│   └── test_report.py
├── config.yaml             # Main configuration file
├── .env.example            # Template for secrets
├── .gitignore
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

Generated at runtime:
```
├── data/                   # SQLite database (auto-created)
├── logs/                   # Log files (auto-created)
└── reports/                # Generated reports (auto-created)
```

---

## How It Works (Technical Overview)

```
┌─────────────┐     ┌───────────┐     ┌──────────┐
│   Search     │────▶│  Extract  │────▶│  Dedupe  │
│ (Web + RSS)  │     │ (Content) │     │ (Filter) │
└─────────────┘     └───────────┘     └──────────┘
                                            │
                                            ▼
┌─────────────┐     ┌───────────┐     ┌──────────┐
│   Deliver   │◀────│  Report   │◀────│ Analyse  │
│  (Email)    │     │ (Format)  │     │  (LLM)   │
└─────────────┘     └───────────┘     └──────────┘
```

1. **Search**: Queries DuckDuckGo (or SerpAPI/Google CSE) with RSAF-related keywords, plus checks RSS feeds from Singapore and defence news sources.
2. **Extract**: Downloads each page and extracts clean text using newspaper3k, with BeautifulSoup fallback.
3. **Dedupe**: Normalises URLs, computes content hashes, and uses SimHash for near-duplicate detection. Checks against a SQLite database of previously processed articles.
4. **Analyse**: Sends each article to Claude for relevance confirmation, summarisation, sentiment tagging, and impact assessment. Uses carefully designed prompts (see `prompts.py`).
5. **Report**: Generates a daily digest in plain text, Markdown, and JSON formats. Sorts by priority score.
6. **Deliver**: Sends the plain text version by email via SMTP. If email fails, the report is still saved locally.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Future Improvements

- **Slack / Telegram delivery** — send the digest to a chat channel
- **CSV export** — for spreadsheet analysis
- **Source-level whitelists and blacklists** — fine-grained source control
- **Trend comparison** — compare today's volume and sentiment vs. the past 7 days
- **Simple dashboard** — a local web page showing trends over time
- **Categorised sections** — separate Singapore media, international media, defence media, and web chatter
- **NewsAPI / GDELT integration** — plug in professional news APIs for broader coverage
- **Multi-language support** — monitor Chinese-language Singapore media
- **Webhook triggers** — alert immediately on high-priority negative coverage instead of waiting for the morning digest

---

## Disclaimer

- Sentiment and impact assessments are **lightweight directional indicators**, not rigorous analysis. Use professional judgement.
- This tool searches the **public web only**. It does not access private platforms, social media APIs, or paywalled content unless separately configured.
- Web scraping respects a polite user agent and configurable rate limits. The tool does not attempt to bypass access controls.
