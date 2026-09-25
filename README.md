# HackerRank Profile Tracker

A beginner-friendly Python project that reads publicly accessible HackerRank profile data and stores the collected snapshot in MongoDB. It is designed for Windows, VS Code, PowerShell, MongoDB Atlas, and GitHub.

The project uses only the public profile page. It does not use private cookies, session tokens, passwords, CAPTCHA bypasses, undocumented authenticated APIs, or other restricted access methods.

## 1. Project overview

Enter a HackerRank username, fetch the public profile page, parse fields that are actually present, and upsert the result into MongoDB. Running the sync repeatedly updates the current snapshot for that username instead of creating duplicate current documents.

The default example username is `dnyaneshwariphal`, but the username is supplied at runtime and is not hardcoded.

## 2. Features

- Validates HackerRank usernames before making a request.
- Fetches only `https://www.hackerrank.com/profile/<username>`.
- Handles HTTP, timeout, and network errors.
- Reads standard metadata and JSON explicitly embedded in the public HTML.
- Collects profile fields, statistics, badges, contests, and recent activity when available.
- Stores unavailable fields as `None`, `{}`, or `[]` instead of inventing data.
- Uses MongoDB upserts and useful indexes.
- Records successful and failed sync attempts in `sync_logs`.
- Keeps MongoDB credentials in `.env`, which is ignored by Git.

## 3. Technology stack

- Python 3.10+
- `requests` for public HTTP requests
- `beautifulsoup4` for HTML and metadata parsing
- `pymongo` for MongoDB
- `python-dotenv` for environment variables
- MongoDB Atlas or a local MongoDB server

## 4. Project structure

```text
hackerrank-profile-tracker/
├── scripts/
│   ├── hackerrank_collector.py  # Public profile collector
│   └── sync_to_mongodb.py       # Collector plus MongoDB sync CLI
├── database/
│   └── mongodb.py                # Connection, indexes, and upsert helpers
├── .env                         # Local secrets; never commit this
├── .env.example                 # Safe configuration template
├── .gitignore
├── requirements.txt
└── README.md
```

## 5. Prerequisites

Install Python 3.10 or newer, a MongoDB Atlas cluster or local MongoDB server, a MongoDB database user, and PowerShell in VS Code. Internet access to the public HackerRank profile page is also required.

For MongoDB Atlas, add your current IP address under **Network Access**, create a database user, and copy the Python connection string from **Connect > Drivers**.

## 6. Create a Python virtual environment

Open PowerShell in the project folder and run:

```powershell
python -m venv venv
```

## 7. Activate the environment on Windows PowerShell

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this once for the current process and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

## 8. Install requirements

```powershell
pip install -r requirements.txt
```

## 9. Configure `.env`

Copy the example file:

```powershell
Copy-Item .env.example .env
```

Open `.env` and set your Atlas connection string:

```dotenv
MONGODB_URI=mongodb+srv://USERNAME:PASSWORD@your-cluster.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=hackerrank_tracker
```

Replace the placeholders with real values. If the password contains reserved URL characters, URL-encode it. Never put the real connection string in `README.md`, `.env.example`, or Python source code.

## 10. Test the MongoDB connection

After `.env` is configured and the Atlas IP allowlist is ready, run:

```powershell
python -c "from database.mongodb import get_database; client, database = get_database(); print('MongoDB connection successful:', database.name); client.close()"
```

Expected output includes `MongoDB connection successful: hackerrank_tracker`. If it fails, check the URI, Atlas IP allowlist, database credentials, and network access. Do not print the URI while troubleshooting.

If the message says authentication failed, open **Security > Database Access** in MongoDB Atlas, edit `dnyaneshwariphatangare8_db_user`, choose **Edit Password**, save a new password, and update the URI locally in `.env`. Never send the password in chat. If the password contains characters such as `@`, `:`, `/`, or `#`, URL-encode those characters in the URI. If the message says server selection timed out, check the current laptop IP in **Security > Network Access**, confirm the cluster is running, and verify that the Atlas host in the URI is correct.

## 11. Run the collector

The collector prints the fields it actually finds. MongoDB is not required:

```powershell
python scripts\hackerrank_collector.py dnyaneshwariphal
```

You can use another username or omit the argument and enter one interactively:

```powershell
python scripts\hackerrank_collector.py
```

## 12. Sync data to MongoDB

After the MongoDB connection test succeeds, run:

```powershell
python scripts\sync_to_mongodb.py dnyaneshwariphal
```

The script reports each section as `collected` or `not available publicly`. It only reports MongoDB success after the upserts and sync log have completed.

## 13. MongoDB collections

- `hackerrank_profiles`: current profile snapshot, one document per username.
- `hackerrank_statistics`: current public statistics snapshot.
- `hackerrank_badges`: current public badge snapshot.
- `hackerrank_contests`: current public contest snapshot.
- `hackerrank_submissions`: current public recent-activity snapshot.
- `sync_logs`: timestamped successful or failed sync attempts.

Unique username indexes prevent duplicate current snapshots in the profile and statistics collections. Repeated syncs replace the current badge, contest, and activity snapshots. Sync logs intentionally retain history.

To inspect documents in Atlas, open **Browse Collections**, select the `hackerrank_tracker` database, and open one of the collections above.

## 14. Run the project on another laptop

Clone the repository, open PowerShell in the cloned folder, and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Configure the new laptop's `.env`, make sure its IP is allowed in Atlas, and run the connection test followed by the sync command. The virtual environment and `.env` are machine-specific and are not transferred through Git.

## 15. GitHub setup

This project is prepared for GitHub with `.gitignore`, `README.md`, `requirements.txt`, and `.env.example`. Git has not been initialized or pushed automatically.

When ready:

```powershell
git init
git add .
git status
git commit -m "Initial HackerRank profile tracker"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/hackerrank-profile-tracker.git
git push -u origin main
```

Before `git add .`, confirm that `.env` is not listed as a staged file. Create the GitHub repository first if it does not already exist.

## 16. Security notes

Never commit or share `.env`, MongoDB usernames or passwords, API keys, private HackerRank cookies, session tokens, or other private credentials. The `.gitignore` excludes `.env`, virtual environments, Python cache files, and common editor folders. If a secret is accidentally committed, rotate it immediately.

## 17. Limitations of HackerRank public profile data

HackerRank does not guarantee a stable public API for every profile field. The collector reads only public HTML metadata and JSON explicitly embedded in the page. Some fields may be hidden by profile settings, loaded only after browser JavaScript runs, unavailable to unauthenticated visitors, or changed by HackerRank without notice.

For `dnyaneshwariphal`, the live public request returned the username and profile URL plus generic image metadata. It did not reliably expose display name, location, education, work experience, skills, statistics, badges, contests, or recent activity. Those fields remain empty rather than being fabricated.

The project cannot promise historical submissions, private profile information, complete rankings, or data that HackerRank does not expose publicly. Respect HackerRank's terms, access rules, and request limits.

## Verification checklist

Run these in order after configuring `.env`:

```powershell
pip install -r requirements.txt
python -c "from database.mongodb import get_database; client, database = get_database(); print('MongoDB connection successful:', database.name); client.close()"
python scripts\hackerrank_collector.py dnyaneshwariphal
python scripts\sync_to_mongodb.py dnyaneshwariphal
python scripts\sync_to_mongodb.py dnyaneshwariphal
```

After the first sync, verify the documents in Atlas. After the second sync, the current profile/statistics/badges/contests/activity collections should still contain one current document for the username; `sync_logs` should contain two entries by design.
