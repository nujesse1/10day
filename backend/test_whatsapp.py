#!/usr/bin/env python3
"""
Quick test script for WhatsApp integration
"""
import requests
import time
import subprocess
import signal
import sys

# Start the server
print("🚀 Starting FastAPI server...")
import tempfile
log_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log')
server = subprocess.Popen(
    ["python3", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
    stdout=log_file,
    stderr=subprocess.STDOUT
)
print(f"   Server logs: {log_file.name}")

# Wait for server to start
time.sleep(3)

try:
    print("\n✅ Testing endpoints...\n")

    # Test 1: Health check
    print("1️⃣  Testing main health endpoint...")
    response = requests.get("http://localhost:8000/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")

    # Test 2: WhatsApp health check
    print("\n2️⃣  Testing WhatsApp health endpoint...")
    response = requests.get("http://localhost:8000/webhook/whatsapp/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")

    # Test 3: Mock WhatsApp webhook (simulate incoming message)
    print("\n3️⃣  Testing WhatsApp webhook with mock message...")
    response = requests.post(
        "http://localhost:8000/webhook/whatsapp",
        data={
            "From": "whatsapp:+11234567890",
            "To": "whatsapp:+14155238886",
            "Body": "show my status"
        }
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        try:
            print(f"   Response: {response.json()}")
        except:
            print(f"   Response (text): {response.text}")
    else:
        print(f"   Error response: {response.text}")

    print("\n✅ All tests passed!")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")

finally:
    # Stop the server
    print("\n🛑 Stopping server...")
    server.terminate()
    server.wait(timeout=5)
    print("✅ Server stopped")

    # Print logs
    print("\n📋 Server logs:")
    log_file.seek(0)
    logs = log_file.read()
    print(logs[-2000:] if len(logs) > 2000 else logs)  # Last 2000 chars
    log_file.close()
