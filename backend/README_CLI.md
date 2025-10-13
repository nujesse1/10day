# Drill Sergeant CLI v0

Natural language habit tracker with LLM-powered intent parsing and semantic matching.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables in `.env`:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
OPENAI_API_KEY=your_openai_api_key
API_BASE_URL=http://localhost:8000  # optional, defaults to localhost:8000
```

## Running

1. Start the FastAPI backend:
```bash
cd backend && uvicorn main:app --reload
```

2. In another terminal, run the CLI:
```bash
cd backend && python3 cli.py
```

## Usage

The CLI uses natural language parsing with OpenAI. Examples:

### Add habits
```
> add morning run
✅ Habit added: 'morning run'

> track my daily reading
✅ Habit added: 'track my daily reading'
```

### Complete habits
```
> complete my morning jog
✅ Completed: 'morning run'

> finished reading with proof /path/to/screenshot.png
✅ Completed: 'daily reading' (proof: /path/to/screenshot.png)
```

### Show status
```
> show status
📋 Today's Status (2025-10-12):

✅ morning run
⬜ daily reading

Progress: 1/2 (50%)

> what's my progress today?
📋 Today's Status (2025-10-12):
...
```

### Remove habits
```
> remove the morning run habit
✅ Habit 'morning run' removed successfully

> delete reading
✅ Habit 'daily reading' removed successfully
```

## How it works

1. **Intent Parsing**: User input → OpenAI `gpt-4o-mini` with structured JSON output
2. **Semantic Matching**: Backend uses LLM to match user's habit description against existing habits
3. **Backend API**: All operations hit FastAPI endpoints with Supabase storage

### Architecture

```
User Input (natural language)
    ↓
CLI (cli.py) - OpenAI structured parser
    ↓ JSON: {"intent": "...", "args": {...}}
    ↓
FastAPI Backend (main.py)
    ↓ LLM semantic matching
    ↓
Supabase (habits + habit_completions tables)
```

## API Endpoints

The CLI uses these backend endpoints:

- `POST /add-habit` - Add new habit
- `POST /remove-habit` - Remove habit (with LLM matching)
- `POST /complete-habit` - Mark habit complete (with LLM matching)
- `GET /habits/today` - Get today's status

## v0 Features

✅ Add/remove habits
✅ Complete habits (with optional proof path)
✅ Show today's status
✅ Natural language parsing
✅ Semantic habit matching
✅ Persist in Supabase

## Future (post-v0)

- Scheduling and recurring habits
- Strike system and penalties
- Multi-day views and analytics
- Habit streaks
