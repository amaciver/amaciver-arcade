# Sushi-Scout API Testing

Test scripts for validating API access and menu data availability.

## Setup

### Option 1: Using uv (Recommended)

**After restarting your terminal:**

```bash
cd api_testing
uv sync
uv run python google_places_test.py
```

### Option 2: Using pip

```bash
cd api_testing
pip install -r requirements.txt
python google_places_test.py
```

## Scripts

### google_places_test.py

Tests Google Places API for menu data availability.

**Prerequisites:**
- Google Places API key set in environment: `GOOGLE_PLACES_API_KEY`
- See [../API_SETUP_GUIDE.md](../API_SETUP_GUIDE.md) for setup instructions

**Usage:**
```bash
# Set API key (Windows PowerShell)
$env:GOOGLE_PLACES_API_KEY="your_key_here"

# Run test
uv run python google_places_test.py
```

## Expected Results

The script will:
1. Search for sushi restaurants in San Francisco
2. Test menu data retrieval for first 3 results
3. Report what menu fields are available
4. Determine if Google Places API is viable for our use case
