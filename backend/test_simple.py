#!/usr/bin/env python3
"""
Simple manual test - just check if everything loads
"""

print("1️⃣  Testing imports...")
try:
    from main import app
    print("   ✅ Main app imports successfully")
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)

print("\n2️⃣  Testing chat engine...")
try:
    from chat_engine import process_user_input, create_new_conversation
    print("   ✅ Chat engine imports successfully")
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)

print("\n3️⃣  Testing session store...")
try:
    from session_store import get_or_create_session, update_session
    print("   ✅ Session store imports successfully")
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)

print("\n4️⃣  Testing WhatsApp module...")
try:
    from whatsapp import router, twilio_client
    print(f"   ✅ WhatsApp module imports successfully")
    print(f"   ✅ Twilio client configured: {twilio_client is not None}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)

print("\n5️⃣  Testing conversation flow (without sending messages)...")
try:
    # Create a test conversation
    history = create_new_conversation()
    print(f"   ✅ Created conversation with {len(history)} messages")

    # Test processing (this will call OpenAI but not send WhatsApp messages)
    response, updated_history = process_user_input("add morning workout", history, verbose=False)
    print(f"   ✅ Processed message, got response: {response[:50]}...")
    print(f"   ✅ History now has {len(updated_history)} messages")
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n✅ All tests passed!")
print("\nTo test with real WhatsApp:")
print("1. Start the server: python3 -m uvicorn main:app --reload")
print("2. Expose it with ngrok: ngrok http 8000")
print("3. Configure Twilio webhook to your ngrok URL")
print("4. Send a WhatsApp message to your Twilio number")
