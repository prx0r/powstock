# Human Tasks — Unlock Data Collection

These are things only you can do. Everything else I can handle.

**Priority order. Do #1 first — it unlocks the most data.**

---

## 1. ~~Companies House API Key~~ ✅ DONE

Key is configured and working. Company profiles, directors, filings, charges, PSC all collecting.

---

## 2. Tracefour API Key (FREE — unlocks insider data)

**What you get:** UK PDMR insider dealing filings, cluster buys (3+ insiders same direction), buying streaks. This is the structured insider data that replaces Investegate scraping.

**Steps:**

1. Go to **https://tracefour.com**
2. Click **"Sign Up"** (top right)
3. Create account (email + password, no payment required)
4. Log in
5. Go to **Settings** (click your name/avatar → Settings)
6. Find **"API Key"** section
7. Click **"Generate Key"** or **"Create Key"**
8. Copy the key
9. Send me the key and I'll add it to `.env`

**Rate limit:** 60 requests per hour (free)

**Time:** 2 minutes

---

## 3. Finnhub API Key (FREE — optional, extra insider data)

**What you get:** SEC Form 4 insider transactions for UK tickers (e.g. `LSEG.L`, `NG.L`). Good cross-reference with Tracefour.

**Steps:**

1. Go to **https://finnhub.io/register**
2. Fill in: name, email, password
3. Verify your email
4. Log in → go to **"Dashboard"**
5. Find your API key at the top (format: `xxxxxxxxxxxxxx`)
6. Copy the key
7. Send me the key and I'll add it to `.env`

**Rate limit:** 60 calls per minute (free)

**Time:** 2 minutes

---

## 4. GitHub Push Access (token revoked)

**What happened:** The GitHub token you pasted was exposed in plain text. I removed it from the git remote. It's been revoked.

**Steps:**

1. Go to **https://github.com/settings/tokens**
2. Click **"Generate new token (classic)"**
3. Note: "powstock push"
4. Expiration: **90 days** (or whatever you prefer)
5. Scopes: check **`repo`** (full control of private repositories)
6. Click **"Generate token"**
7. Copy the token (format: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)
8. Run this on the server:

```bash
cd /root/powstock
git remote set-url origin https://<YOUR_TOKEN>@github.com/prx0r/powstock.git
git push origin main
```

9. Then immediately remove the token from the remote URL:

```bash
git remote set-url origin https://github.com/prx0r/powstock.git
```

**Time:** 2 minutes

---

## 5. Create .env File (do after getting keys)

Once you have the keys from tasks 1-3, send them to me or create the file yourself:

```bash
cd /root/powstock
cp .env.example .env
```

Then edit `.env` and fill in:

```
POWSTOCK_COMPANIES_HOUSE_API_KEY=<key from task 1>
POWSTOCK_FINNHUB_API_KEY=<key from task 3>
POWSTOCK_TRACEFOUR_API_KEY=<key from task 2>
```

---

## What Unlocks What

| Task | Data Unlocked | Current State |
|------|---------------|---------------|
| #1 CH API key | Company profiles, directors, filings, charges, PSC, financials | 25 profiles exist but no API key for fresh data |
| #2 Tracefour key | Structured UK insider dealing (PDMR), cluster buys, streaks | Investegate scraper returns wrong companies |
| #3 Finnhub key | SEC insider transactions for UK tickers | Skipped without key |
| #4 GitHub push | Push code to remote | Token revoked, 2 commits stuck locally |

---

## What Already Works (no keys needed)

| Source | Status | Data |
|--------|--------|------|
| Yahoo Finance prices | ✅ Working | 5,968 rows, 23 tickers, ~250 days |
| FCA short interest | ✅ Working | 421 positions, 14 universe matches |
| Investegate RNS | ✅ Working | Fixed — direct company pages |
| Investegate PDMR | ⚠️ Partial | Returns non-universe companies (Tracefour fixes this) |

---

## Time Estimate

| Task | Time |
|------|------|
| #1 Companies House key | 2 min |
| #2 Tracefour key | 2 min |
| #3 Finnhub key | 2 min |
| #4 GitHub push | 2 min |
| **Total** | **8 minutes** |

---

## After You Do These

I will:
1. Wire all 4 keys into `.env`
2. Run the full collector pipeline (`make run`)
3. Verify data for all 25 universe stocks
4. Push to GitHub
5. Run the acceptance test suite

The garden goes from "prices and short interest only" to "full UK corporate/market tape" in one pipeline run.
