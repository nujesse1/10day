# WhatsApp Setup - Super Clear Instructions

Follow these steps EXACTLY to get your WhatsApp bot working.

---

## STEP 1: Start Your Server

Open a terminal in the project folder and run:

```bash
cd backend
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**What you should see:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:whatsapp:Twilio client initialized successfully
```

✅ **Leave this terminal running. Open a NEW terminal for the next steps.**

---

## STEP 2: Install ngrok

**Option A: Using Homebrew (recommended for Mac)**
```bash
brew install ngrok
```

**Option B: Download manually**
1. Go to: https://ngrok.com/download
2. Download for your system
3. Unzip and move to a folder in your PATH

**Verify installation:**
```bash
ngrok version
```

---

## STEP 3: Expose Your Server with ngrok

In your **NEW terminal**, run:

```bash
ngrok http 8000
```

**What you'll see:**
```
Session Status    online
Forwarding        https://abc123xyz.ngrok.io -> http://localhost:8000
```

**🔥 IMPORTANT: Copy the HTTPS URL** (looks like `https://abc123xyz.ngrok.io`)

✅ **Keep this terminal running too!**

---

## STEP 4: Configure Twilio Webhook

### 4.1: Open Twilio Console
Go to: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn

You'll see a page that says **"Send a WhatsApp Message"**

### 4.2: Join the Sandbox First (IMPORTANT!)

On that page, you'll see:
```
Join your sandbox
Send this message from WhatsApp: join <word>-<word>
To this number: +1 415 523 8886
```

**DO THIS NOW:**
1. Open WhatsApp on your phone
2. Start a new chat with: **+1 415 523 8886**
3. Send the exact message shown (e.g., "join happy-dog")
4. You should get a reply: "Joined your-sandbox-name"

### 4.3: Configure the Webhook

Now go to: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox

Scroll down to **"Sandbox Configuration"** section.

Under **"WHEN A MESSAGE COMES IN"**:
1. Paste your ngrok URL + `/webhook/whatsapp`

   **Example:** `https://abc123xyz.ngrok.io/webhook/whatsapp`

2. Make sure it says **POST** (not GET)
3. Click **Save**

**What it should look like:**
```
When a message comes in:
[https://abc123xyz.ngrok.io/webhook/whatsapp] [POST ▼]
```

---

## STEP 5: Test It!

Open WhatsApp on your phone and send a message to **+1 415 523 8886**:

```
add morning workout
```

**What should happen:**
- You send: "add morning workout"
- Bot replies: "Great, I've added the 'morning workout' habit..."

**Other things to try:**
```
show my status
complete morning workout
what habits do I have?
remove morning workout
```

---

## Troubleshooting

### Bot Not Responding?

**Check #1: Is your server running?**
```bash
# In terminal 1, you should see:
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Check #2: Is ngrok running?**
```bash
# In terminal 2, you should see:
Forwarding        https://abc123xyz.ngrok.io -> http://localhost:8000
```

**Check #3: Did you join the sandbox?**
- Send "join your-code" to +1 415 523 8886 first!

**Check #4: Is the webhook configured correctly?**
- Go to: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox
- Check the URL ends with `/webhook/whatsapp`
- Check it says POST

**Check #5: Test the webhook manually**
```bash
curl http://localhost:8000/webhook/whatsapp/health
```

You should see:
```json
{"status":"ok","twilio_configured":true,"whatsapp_number":"whatsapp:+14155238886"}
```

### "Address already in use" Error?

Kill the process using port 8000:
```bash
lsof -ti:8000 | xargs kill -9
```

Then start the server again.

### ngrok URL Changed?

**ngrok gives you a new URL every time you restart it (on free plan).**

When this happens:
1. Copy the new ngrok URL
2. Update the Twilio webhook (Step 4.3 above)
3. Test again

**To avoid this:** Upgrade to ngrok paid plan for a permanent URL.

---

## Quick Reference

| What | Where |
|------|-------|
| Twilio Console | https://console.twilio.com |
| WhatsApp Sandbox Settings | https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox |
| Your Twilio Number | +1 415 523 8886 |
| Your Account SID | (Found in Twilio Console) |
| Webhook Endpoint | `/webhook/whatsapp` |

---

## Summary

```
Terminal 1: python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
Terminal 2: ngrok http 8000
WhatsApp:   Send "join your-code" to +1 415 523 8886
Twilio:     Configure webhook: https://your-ngrok-url.ngrok.io/webhook/whatsapp
Test:       Send "add morning workout" via WhatsApp
```

---

Need help? Check the logs in Terminal 1 to see what's happening.
