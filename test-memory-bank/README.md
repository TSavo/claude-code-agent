# Google Memory Bank Test

Testing Google Memory Bank in isolation with existing Gemini API key.

## Setup

1. Copy your Gemini API key from main `.env` to `.env` in this directory
2. Install dependencies: `pip install google-adk[vertexai]`
3. Run the test: `python memory_bank_test.py`

## Files

- `memory_bank_test.py` - Basic Memory Bank test
- `simple_memory_test.py` - Simplified version using just Gemini API
- `.env.example` - Template for environment variables