# HackerRank Profile Tracker & Analyzer

A professional Python project that reads public HackerRank profile data, stores the latest snapshot in MongoDB Atlas, and presents it through a modern Streamlit dashboard.

The app is intentionally limited to public, unauthenticated data. It never invents profile statistics or fabricates fields that HackerRank does not expose. If a field is not publicly available, the dashboard shows `Not publicly available`.

## Project title

HackerRank Profile Tracker & Analyzer

## Features

- Username or public profile URL analysis
- Public profile data collection from HackerRank
- Coding statistics and profile overview
- Skills and domains when explicitly exposed
- Badges and achievements when publicly visible
- Contest information when available
- Recent activity when publicly available
- MongoDB Atlas storage with safe upserts
- Streamlit dashboard for a polished developer analytics view

## Tech stack

- Python
- Streamlit
- Requests
- BeautifulSoup
- PyMongo
- MongoDB Atlas

## Setup instructions

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example file and create a local `.env` file:

```powershell
Copy-Item .env.example .env
```

Then set your local MongoDB values without sharing credentials in the repository:

```dotenv
MONGODB_URI=mongodb+srv://USERNAME:PASSWORD@your-cluster.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=hackerrank_tracker
```

### 4. Run the dashboard

```powershell
streamlit run app.py
```

### 5. Run the collector from the terminal

```powershell
python scripts\hackerrank_collector.py dnyaneshwariphal
python scripts\hackerrank_collector.py "https://www.hackerrank.com/dnyaneshwariphal"
```

### 6. Sync a profile to MongoDB

```powershell
python scripts\sync_to_mongodb.py dnyaneshwariphal
```

## Notes

- The project does not use private cookies, login sessions, hidden APIs, or other restricted access methods.
- The dashboard displays only fields that are actually found on the public HackerRank page.
- Repeated analysis for the same username updates the current MongoDB record instead of creating duplicates.
- If HackerRank does not publicly expose a field, the application intentionally shows `Not publicly available` rather than inventing data.

## Security

This project keeps secrets in `.env` and ignores them through `.gitignore`. Never commit MongoDB passwords, API keys, cookies, session tokens, or private credentials.

## Limitations

The public HackerRank profile page is not guaranteed to expose a fixed set of fields. Some profile details may be hidden, delayed, or absent for unauthenticated users. The app therefore shows only data that is actually present and otherwise marks it as unavailable.
