# API Setup Guide

This guide walks through setting up the necessary API keys for the sushi-scout project.

---

## Google Places API (New)

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Name it "sushi-scout" (or similar)
4. Click "Create"

### Step 2: Enable Places API (New)

1. In the Cloud Console, go to "APIs & Services" → "Library"
2. Search for "Places API (New)"
3. Click on it and press "Enable"

**Note:** Make sure it's the **New** Places API, not the legacy one.

### Step 3: Create API Key

1. Go to "APIs & Services" → "Credentials"
2. Click "+ CREATE CREDENTIALS" → "API key"
3. Copy the API key (starts with `AIza...`)
4. **Optional but recommended:** Click "Restrict Key"
   - Set "Application restrictions" to "None" (for testing) or "IP addresses" (for production)
   - Under "API restrictions", select "Restrict key" → Choose "Places API (New)"

### Step 4: Check Billing

⚠️ **Important:** Google Places API requires a billing account, but includes $200/month free credit.

1. Go to "Billing" in Cloud Console
2. Link a billing account (credit card required)
3. Check that you have the $200 monthly credit active

**Pricing reminder:**
- Basic tier: $0.032 per request
- $200 credit = ~6,250 requests free per month
- Our estimated usage: ~$0.35 per complete search workflow

### Step 5: Set Environment Variable

**Windows (PowerShell):**
```powershell
$env:GOOGLE_PLACES_API_KEY="your_api_key_here"
```

**Windows (CMD):**
```cmd
set GOOGLE_PLACES_API_KEY=your_api_key_here
```

**Mac/Linux:**
```bash
export GOOGLE_PLACES_API_KEY="your_api_key_here"
```

**Or create a `.env` file:**
```bash
# .env
GOOGLE_PLACES_API_KEY=your_api_key_here
```

---

## Yelp Fusion API

### Step 1: Create Yelp Developer Account

1. Go to [Yelp Developers](https://www.yelp.com/developers)
2. Click "Get Started" or "Sign Up"
3. Log in with existing Yelp account or create new one

### Step 2: Create an App

1. Go to [Manage App](https://www.yelp.com/developers/v3/manage_app)
2. Click "Create New App"
3. Fill in details:
   - **App Name:** sushi-scout
   - **Industry:** Food & Beverage
   - **Company:** Personal Project
   - **Description:** "Agent toolkit for finding cheapest sushi rolls"
4. Agree to terms and click "Create App"

### Step 3: Get API Key

1. Your API key will be displayed on the app page
2. Copy the "API Key" (not Client ID)

### Step 4: Check Pricing Plan

1. Go to [Plans](https://docs.developer.yelp.com/docs/plans)
2. Default is "Starter" plan: $7.99 per 1000 calls
3. First month may have free tier (check current offers)

### Step 5: Set Environment Variable

**Windows (PowerShell):**
```powershell
$env:YELP_API_KEY="your_api_key_here"
```

**Mac/Linux:**
```bash
export YELP_API_KEY="your_api_key_here"
```

**Or add to `.env` file:**
```bash
# .env
YELP_API_KEY=your_api_key_here
```

---

## Testing API Access

### Install Dependencies

```bash
pip install requests python-dotenv
```

### Run Test Script

```bash
cd api_testing
python google_places_test.py
```

This script will:
- ✅ Search for sushi restaurants in San Francisco
- ✅ Test menu data retrieval from first 3 results
- ✅ Analyze what menu fields are available
- ✅ Report success rate and data quality

Expected output:
```
🔍 Searching for sushi restaurants near (37.7749, -122.4194)...
✅ Found 10 restaurants

📋 Fetching menu for: [Restaurant Name]
   Has menuItems field: True/False
   Has menu field: True/False

SUMMARY
Total restaurants searched: 10
Restaurants with menu data: X/3
```

---

## Troubleshooting

### Google Places API

**Error: "This API project is not authorized to use this API"**
- Solution: Make sure you enabled "Places API (New)" in the API Library

**Error: "The request is missing a valid API key"**
- Solution: Check that `GOOGLE_PLACES_API_KEY` is set correctly

**Error: 429 - Quota exceeded**
- Solution: Check your quota in Cloud Console → APIs & Services → Quotas
- You may need to enable billing for the free $200 credit

**No menu data returned:**
- This is expected! Not all restaurants have menu data in Google Places
- We'll implement fallback strategy (synthetic data or Yelp)

### Yelp Fusion API

**Error: 401 - Unauthorized**
- Solution: Check that your API key is correct and active

**Error: 429 - Rate limit exceeded**
- Solution: Yelp has rate limits (5000 calls/day for free tier)
- Wait 24 hours or upgrade plan

---

## Next Steps

Once you have API keys set up:

1. ✅ Run `python api_testing/google_places_test.py`
2. ✅ Document findings in DEVELOPMENT_NOTES.md
3. ✅ Decide on primary/fallback strategy based on results
4. ✅ Proceed to scaffold MCP server with `arcade new`

---

## Security Best Practices

⚠️ **Never commit API keys to git!**

Add to `.gitignore`:
```gitignore
.env
*.env
.env.*
api_keys.txt
```

Use environment variables or `.env` files for local development.
