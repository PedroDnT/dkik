#!/bin/bash
set -e

# Print the DKIK banner
echo "======================================================"
echo "  _____   _  __ ___ _  __                             "
echo " |  _ \ | |/ /|_ _| |/ /  WhatsApp Bot for TJSP       "
echo " | | | || ' /  | || ' /   São Paulo State Lawyers     "
echo " | |_| || . \  | || . \                               "
echo " |____/ |_|\_\|___|_|\_\  v0.1.0                      "
echo "======================================================"
echo ""

# Function to check if MongoDB is available
check_mongodb() {
  echo "Checking MongoDB connection..."
  python -c "
import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from os import environ

async def check_mongo():
    try:
        client = AsyncIOMotorClient(
            environ.get('MONGODB_URI'),
            serverSelectionTimeoutMS=5000
        )
        await client.admin.command('ping')
        print('MongoDB connection successful')
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f'MongoDB connection failed: {e}')
        return False

if not asyncio.run(check_mongo()):
    sys.exit(1)
"
  return $?
}

# Wait for MongoDB to be available
wait_for_mongodb() {
  local max_retries=30
  local retry=0
  
  while ! check_mongodb; do
    retry=$((retry+1))
    if [ $retry -eq $max_retries ]; then
      echo "Could not connect to MongoDB after $max_retries attempts. Exiting."
      exit 1
    fi
    
    echo "Waiting for MongoDB to be available... ($retry/$max_retries)"
    sleep 2
  done
}

# Check required environment variables
check_env_vars() {
  required_vars=("MONGODB_URI" "OPENAI_API_KEY" "TWILIO_ACCOUNT_SID" "TWILIO_AUTH_TOKEN" "TWILIO_WHATSAPP_NUMBER")
  
  for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
      echo "Error: Required environment variable $var is not set"
      exit 1
    fi
  done
  
  echo "All required environment variables are set"
}

# Create necessary directories
setup_directories() {
  mkdir -p logs
  chmod 755 logs
  echo "Created logs directory"
}

# Main entrypoint logic
main() {
  # Check environment variables
  check_env_vars
  
  # Set up directories
  setup_directories
  
  # Wait for MongoDB to be available
  wait_for_mongodb
  
  # Execute the appropriate command based on the first argument
  case "$1" in
    web)
      echo "Starting DKIK WhatsApp Bot web service..."
      exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000} --log-level ${LOG_LEVEL:-info}
      ;;
    worker)
      echo "Starting DKIK WhatsApp Bot background worker..."
      exec python worker/main.py
      ;;
    *)
      echo "Usage: $0 {web|worker}"
      echo "  web    - Start the FastAPI web service"
      echo "  worker - Start the background worker"
      exit 1
      ;;
  esac
}

# Execute main function with all arguments
main "$@"
