#!/bin/bash

# Install dependencies if needed
pip3 install -r backend/requirements.txt

# Run the FastAPI server from the backend directory
cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000
