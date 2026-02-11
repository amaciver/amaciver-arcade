# Setup Instructions for Sushi-Scout Development

## Quick Start

### 1. Restart Your Terminal

After installing `uv`, you need to restart your terminal for the PATH changes to take effect.

**Close and reopen your terminal/PowerShell/VSCode, then:**

```bash
# Verify uv is installed
uv --version  # Should show: uv 0.10.2 (or similar)
```

### 2. Set Up API Testing Environment

```bash
cd api_testing
uv sync  # Creates virtual environment and installs dependencies
```

### 3. Get API Keys

Follow [API_SETUP_GUIDE.md](API_SETUP_GUIDE.md) to:
- Create Google Places API key
- Create Yelp Fusion API key (optional for now)

### 4. Test API Access

```bash
# Set your API key (Windows PowerShell)
$env:GOOGLE_PLACES_API_KEY="your_key_here"

# Run the test
cd api_testing
uv run python google_places_test.py
```

## Next Steps After API Testing

Once you've validated API access:

### 1. Scaffold MCP Server

```bash
# Install arcade CLI if needed
uv tool install arcade-mcp

# Create MCP server
arcade new sushi-scout-mcp
```

### 2. Development Workflow

All subsequent development will use `uv` for dependency management:

```bash
cd sushi-scout-mcp
uv add <package-name>  # Add dependencies
uv run pytest          # Run tests
uv run python -m sushi_scout  # Run the server
```

## Troubleshooting

### "uv: command not found" after installation

**Solution:** Restart your terminal completely. The installer modified your PATH environment variable.

### Google Places API errors

Check:
1. API key is correct
2. "Places API (New)" is enabled in Google Cloud Console
3. Billing is enabled (required for the free $200 credit)

See [API_SETUP_GUIDE.md](API_SETUP_GUIDE.md) for detailed troubleshooting.

## Project Structure

```
amaciver-arcade/
├── api_testing/           # API validation scripts (current step)
│   ├── google_places_test.py
│   ├── pyproject.toml
│   └── .venv/            # Created by `uv sync`
├── sushi-scout-mcp/       # MCP server (to be created)
├── sushi-agent/           # Agent application (to be created)
└── docs/
    ├── API_SETUP_GUIDE.md
    ├── DEVELOPMENT_NOTES.md
    └── claude.md
```
