# Testing Conversational Memory

The CLI now maintains conversation history throughout the session. Here are some test scenarios:

## Test Scenario 1: Follow-up on Added Habits
```
> add morning workout
✅ Habit 'morning workout' added successfully

> add daily reading
✅ Habit 'daily reading' added successfully

> what habits did I just add?
You just added two habits: 'morning workout' and 'daily reading'.
```

## Test Scenario 2: Referencing Previous Context
```
> show my status
📋 Today's Status:
⬜ morning workout
⬜ daily reading

> complete the first one
✅ Completed: 'morning workout'
```

## Test Scenario 3: Clarifications and Follow-ups
```
> I want to add a habit
Sure! What habit would you like to add?

> make my bed
✅ Habit 'make my bed' added successfully

> actually, remove that
✅ Habit 'make my bed' removed successfully
```

## How It Works

- **Session Storage**: Conversation history is stored in memory during the CLI session
- **System Prompt**: Initialized at the start with the system instructions
- **Message History**: Each user message and assistant response is appended to history
- **Context Passing**: The full history is passed to the LLM on each request
- **Session Scope**: History persists until you quit the CLI (not saved to disk)

## Technical Details

The conversation history format follows OpenAI's message structure:
```python
conversation_history = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "add morning workout"},
    {"role": "assistant", "content": "Habit 'morning workout' added successfully"},
    {"role": "user", "content": "what did I just add?"},
    # ... and so on
]
```
