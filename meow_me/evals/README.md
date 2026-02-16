# Meow Me Evaluation Suite

Arcade-based evaluations for testing whether AI models correctly select and invoke Meow Me tools.

## What These Evals Test

Unlike the pytest suite (which tests **implementation correctness**), these evaluations test **LLM tool selection**:

- Does the model call `meow_me` when user says "Meow me!"?
- Does the model call `get_cat_fact(count=3)` when user says "Give me 3 cat facts"?
- Does the model correctly route to `send_cat_fact` vs `send_cat_image`?
- Does the model understand multi-tool workflows?

## Evaluation Suites

### `meow_me_eval_suite` (10 cases)
Core tool selection patterns:
- One-shot "Meow me"
- Fetching facts with various counts (1, 3, 5)
- Sending facts to Slack channels
- Getting user avatar (2 phrasings)
- Generating cat images (with multi-turn context)
- Ambiguous requests

### `meow_me_edge_cases` (2 cases)
Edge cases and boundary conditions:
- Count clamping (requesting 10 facts → clamps to 5)
- Channel name variations (with `#` prefix)

## Prerequisites

```bash
# Ensure arcade-evals is installed
cd meow_me
uv sync --all-extras

# Set API keys
export OPENAI_API_KEY=sk-...
export ARCADE_API_KEY=arc-...      # For Slack OAuth
export ARCADE_USER_ID=you@email.com
```

## Running Evaluations

### Run all evaluations
```bash
cd meow_me
uv run arcade evals evals/
```

### Run with detailed output
```bash
uv run arcade evals evals/ --details
```

### Capture mode (bootstrap expectations)
```bash
uv run arcade evals evals/ --capture -o results.json
```

### Run specific provider
```bash
uv run arcade evals evals/ --use-provider openai:gpt-4o-mini
```

### Multiple runs for stability
```bash
uv run arcade evals evals/ --num-runs 3
```

## Understanding Results

### Scoring

Each test case is scored 0.0 to 1.0 based on:
1. **Tool selection**: Did the model call the right tool?
2. **Parameter accuracy**: Were the arguments correct?

Critics weigh each parameter:
- `BinaryCritic`: Exact match (1.0 if match, 0.0 if not)
- `SimilarityCritic`: Fuzzy text matching (0.0-1.0 based on similarity)

Weights are normalized to sum to 1.0.

### Rubrics

Default thresholds:
- **Fail**: < 0.85
- **Warn**: < 0.95
- **Pass**: ≥ 0.95

Some cases use lenient rubrics for ambiguous requests.

### Example Output

```
✓ One-shot meow_me                              1.00
✓ Fetch cat facts with specific count           1.00
✓ Fetch single cat fact (implicit count=1)      0.95 ⚠
✗ Ambiguous: cat art                             0.75

3 passed, 1 warning, 1 failed
```

## Cost Considerations

Each evaluation case makes 1+ LLM API calls. Costs vary by provider:
- OpenAI gpt-4o-mini: ~$0.01-0.05 per full suite run
- OpenAI gpt-4o: ~$0.10-0.50 per full suite run
- Anthropic Claude 3.5 Sonnet: ~$0.05-0.25 per full suite run

Use `--num-runs` judiciously to avoid excessive costs.

## Comparison with Pytest Suite

| Dimension | Arcade Evals | Pytest Suite |
|-----------|--------------|--------------|
| Tests | LLM tool selection | Implementation correctness |
| Speed | Slow (LLM API) | Fast (~3 sec for 138 tests) |
| Cost | $0.01-0.50 per run | Free |
| Determinism | Model-dependent | Fully mocked |
| Coverage | 16 tool routing patterns | 138 unit + integration tests |

Both are valuable! Evals validate **agent behavior**, pytest validates **code correctness**.

## CI/CD Integration

For production, you might run evals:
- On PR (with --num-runs 1 to minimize cost)
- Nightly (with --num-runs 3 for stability)
- Before release (full suite across multiple providers)

Example GitHub Actions:
```yaml
- name: Run evaluations
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    ARCADE_API_KEY: ${{ secrets.ARCADE_API_KEY }}
  run: |
    cd meow_me
    uv run arcade evals evals/ --use-provider openai:gpt-4o-mini
```

## Troubleshooting

### "No API key found"
Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in your environment.

### "MCP server failed to start"
Ensure the server runs: `uv run arcade mcp -p meow_me stdio`

### "Tool not found"
Check that all tools are registered in `meow_me/__init__.py`

### Inconsistent results
Use `--num-runs 3` to average across multiple runs. LLM behavior varies!

## Further Reading

- [Arcade Evaluation Docs](https://docs.arcade.dev/en/guides/create-tools/evaluate-tools/create-evaluation-suite.md)
- [Capture Mode](https://docs.arcade.dev/en/guides/create-tools/evaluate-tools/capture-mode.md)
- [Critics](https://docs.arcade.dev/en/guides/create-tools/evaluate-tools/create-evaluation-suite.md)
