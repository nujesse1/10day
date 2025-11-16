#!/bin/bash

# Kill any existing process on port 8000
echo "🧹 Cleaning up port 8000..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

echo ""
echo "🚀 Starting Drill Sergeant WhatsApp Bot..."
echo ""
echo "📋 Next steps after server starts:"
echo "   1. Open a NEW terminal"
echo "   2. Run: ngrok http 8000"
echo "   3. Copy the https://....ngrok.io URL"
echo "   4. Go to: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox"
echo "   5. Paste your URL + /whatsapp in the webhook field"
echo "   6. Send a WhatsApp message to test!"
echo ""
echo "📖 Full guide: See WHATSAPP_SETUP.md"
echo ""
echo "─────────────────────────────────────────────────────────"
echo ""

# Start the server
cd backend && python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
