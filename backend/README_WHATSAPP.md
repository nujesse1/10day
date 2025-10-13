# WhatsApp Integration Guide

Transform your Drill Sergeant habit tracker into a WhatsApp bot! Chat with your habit tracker naturally through WhatsApp instead of using the CLI.

## Features

✅ **Natural Language Commands** - Just message like you would text a friend
✅ **Per-User Sessions** - Each WhatsApp user has their own habit list and conversation history
✅ **Conversation Memory** - The bot remembers context within your session (30-minute timeout)
✅ **Multi-User Support** - Multiple people can use the same bot simultaneously
✅ **Media Support Ready** - Infrastructure prepared for proof photo uploads (coming soon)

## Architecture

```
WhatsApp User → Twilio → FastAPI Webhook → Chat Engine → Supabase
                              ↓
                       Session Store (per-user history)
```

## Setup Instructions

### 1. Get Twilio Account & Sandbox

1. Sign up for a free Twilio account at https://www.twilio.com/try-twilio
2. Go to the Twilio Console: https://console.twilio.com/
3. Navigate to **Messaging** → **Try it out** → **Send a WhatsApp message**
4. Follow the instructions to join your Twilio WhatsApp Sandbox:
   - You'll get a number like `+1 415 523 8886`
   - You need to send a specific code from your WhatsApp to activate it
   - Example: Send "join <your-code>" to the Twilio number

### 2. Get Your Twilio Credentials

From the Twilio Console (https://console.twilio.com/):

1. Copy your **Account SID** (starts with `AC...`)
2. Copy your **Auth Token** (click to reveal)
3. Note your **WhatsApp Sandbox Number** (format: `whatsapp:+14155238886`)

### 3. Configure Environment Variables

Add these to your `backend/.env` file:

```bash
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

**Replace** the values with your actual credentials from step 2.

### 4. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This will install the Twilio SDK along with other dependencies.

### 5. Expose Your Local Server (for Development)

Twilio needs a public URL to send webhooks to your local server. Use **ngrok**:

1. Install ngrok: https://ngrok.com/download
2. Start your FastAPI server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
3. In another terminal, start ngrok:
   ```bash
   ngrok http 8000
   ```
4. Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

### 6. Configure Twilio Webhook

1. Go to Twilio Console → Messaging → Settings → WhatsApp Sandbox Settings
2. Under **"When a message comes in"**, set:
   ```
   https://your-ngrok-url.ngrok.io/webhook/whatsapp
   ```
3. Make sure the method is set to **POST**
4. Click **Save**

### 7. Test It!

Send a WhatsApp message to your Twilio number:

```
add morning workout
```

The bot should respond with confirmation!

## Usage Examples

### Add Habits
```
add daily meditation
track my water intake
start tracking pushups
```

### Complete Habits
```
complete meditation
finished my workout
done with reading
```

### Check Status
```
show my status
what's my progress today?
how am I doing?
```

### Remove Habits
```
remove meditation
delete the workout habit
stop tracking water
```

## How It Works

### Session Management

- Each WhatsApp number gets its own conversation session
- Sessions include conversation history for context-aware responses
- Sessions auto-expire after 30 minutes of inactivity
- Each user has their own independent habit list (stored by phone number... future enhancement)

### Message Flow

1. User sends WhatsApp message
2. Twilio forwards to `/webhook/whatsapp` endpoint
3. System retrieves or creates user's session
4. Message processed through chat engine (same as CLI)
5. Response sent back via Twilio API
6. Updated conversation history saved to session

### Multi-User Support

Currently, all users share the same habit list in Supabase (no user separation). To add true multi-user support:

1. Add a `user_id` or `phone_number` field to the `habits` table
2. Modify backend API to filter habits by user
3. Link phone number to user account

## API Endpoints

### WhatsApp Webhook
- **POST** `/webhook/whatsapp` - Receives incoming WhatsApp messages from Twilio

### Health Check
- **GET** `/webhook/whatsapp/health` - Check if WhatsApp integration is configured

### Status Callback
- **POST** `/webhook/whatsapp/status` - Receives delivery status updates from Twilio

## Troubleshooting

### Bot Not Responding

1. **Check ngrok is running** - Make sure the ngrok tunnel is active
2. **Verify webhook URL** - Check Twilio console has the correct ngrok URL
3. **Check logs** - Look at your FastAPI server logs for errors
4. **Test webhook** - Visit `https://your-ngrok-url.ngrok.io/webhook/whatsapp/health`

### "Twilio client not configured" Error

Make sure you've set all three environment variables in `.env`:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_NUMBER`

Then restart your FastAPI server.

### Session Not Remembering Context

- Sessions expire after 30 minutes of inactivity
- Check if the user's phone number is being correctly extracted from Twilio's `From` field
- Look for `get_or_create_session` logs in the server output

### Can't Join Twilio Sandbox

- Make sure you're sending the join code to the exact number shown in Twilio console
- The format must match exactly (e.g., "join happy-dog")
- Try resetting your sandbox if it's not working

## Production Deployment

For production use, you'll need:

1. **Upgrade from Twilio Sandbox** to a production WhatsApp Business Account
   - Requires Facebook Business verification
   - Costs money but allows custom branding

2. **Deploy to a Server** with a public URL (not ngrok)
   - Heroku, AWS, DigitalOcean, Railway, etc.
   - Make sure to set environment variables

3. **Use Redis for Session Storage** instead of in-memory
   - Install: `pip install redis`
   - Update `session_store.py` to use Redis
   - Prevents session loss on server restart

4. **Add User Authentication**
   - Link phone numbers to user accounts
   - Add per-user habit lists
   - Implement privacy controls

## Future Enhancements

- [ ] **Proof Photos** - Upload images directly via WhatsApp as habit proof
- [ ] **Scheduled Reminders** - Bot sends daily reminders for incomplete habits
- [ ] **Rich Buttons** - Interactive button replies for quick actions
- [ ] **Habit Streaks** - Track consecutive days completed
- [ ] **Weekly Reports** - Automated summary messages
- [ ] **Multi-language Support** - Support for languages other than English

## Code Structure

```
backend/
├── whatsapp.py          # Twilio webhook handler
├── chat_engine.py       # Shared LLM processing logic
├── session_store.py     # Per-user conversation management
├── main.py             # FastAPI app (includes WhatsApp router)
└── cli.py              # CLI interface (still works!)
```

## Support

Having issues? Check:
- Twilio Console Logs: https://console.twilio.com/monitor/logs
- FastAPI Server Logs: Check your terminal running uvicorn
- ngrok Request Inspector: http://localhost:4040 (when ngrok is running)

## Testing Without WhatsApp

You can test the webhook locally using curl:

```bash
curl -X POST http://localhost:8000/webhook/whatsapp \
  -d "From=whatsapp:+11234567890" \
  -d "Body=add morning workout"
```

This simulates a WhatsApp message without needing Twilio.
