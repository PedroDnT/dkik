#!/bin/bash
set -e

# DKIK - WhatsApp Bot for São Paulo State Lawyers (TJSP)
# Local development setup script

# Print banner
echo "======================================================"
echo "  _____   _  __ ___ _  __                             "
echo " |  _ \ | |/ /|_ _| |/ /  WhatsApp Bot for TJSP       "
echo " | | | || ' /  | || ' /   São Paulo State Lawyers     "
echo " | |_| || . \  | || . \                               "
echo " |____/ |_|\_\|___|_|\_\  Setup Script                "
echo "======================================================"
echo ""

# Check if script is run from project root
if [ ! -f "requirements.txt" ]; then
  echo "Error: This script must be run from the project root directory."
  echo "Please run: bash scripts/setup.sh"
  exit 1
fi

# Check Python version
echo "Checking Python version..."
if command -v python3 &>/dev/null; then
  PYTHON="python3"
elif command -v python &>/dev/null; then
  PYTHON="python"
else
  echo "Error: Python not found. Please install Python 3.8 or higher."
  exit 1
fi

# Check Python version is 3.8+
PY_VERSION=$($PYTHON -c "import sys; print('{}.{}'.format(sys.version_info.major, sys.version_info.minor))")
PY_MAJOR=$(echo $PY_VERSION | cut -d. -f1)
PY_MINOR=$(echo $PY_VERSION | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]); then
  echo "Error: Python 3.8 or higher is required. Found Python $PY_VERSION."
  exit 1
fi

echo "Found Python $PY_VERSION"

# Create virtual environment
echo -e "\nSetting up virtual environment..."
if [ -d ".venv" ]; then
  echo "Virtual environment already exists."
  read -p "Do you want to recreate it? (y/N): " recreate
  if [[ $recreate == [Yy]* ]]; then
    echo "Removing existing virtual environment..."
    rm -rf .venv
    $PYTHON -m venv .venv
    echo "Virtual environment recreated."
  fi
else
  $PYTHON -m venv .venv
  echo "Virtual environment created."
fi

# Activate virtual environment
echo -e "\nActivating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
  # Windows
  source .venv/Scripts/activate
else
  # Linux/Mac
  source .venv/bin/activate
fi

# Install dependencies
echo -e "\nInstalling dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create directories
echo -e "\nCreating necessary directories..."
mkdir -p logs

# Create .env file if it doesn't exist
echo -e "\nSetting up environment variables..."
if [ -f ".env" ]; then
  echo ".env file already exists."
  read -p "Do you want to overwrite it? (y/N): " overwrite
  if [[ ! $overwrite == [Yy]* ]]; then
    echo "Keeping existing .env file."
  else
    create_env=true
  fi
else
  create_env=true
fi

if [ "$create_env" = true ]; then
  echo "Creating .env file..."
  cat > .env << EOF
# Twilio WhatsApp Configuration
TWILIO_ACCOUNT_SID=ACb0572cd4a114e8f916e788f358aa0906
TWILIO_AUTH_TOKEN=2e6675e67d29a4e014a9240e3e965230
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# OpenAI Configuration
OPENAI_API_KEY=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
OPENAI_MODEL=gpt-4-turbo-preview

# DataJud API Configuration
DATAJUD_API_KEY=cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==
DATAJUD_API_BASE_URL=https://api.datajud.cnj.jus.br/v1

# MongoDB Configuration
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/dkik
MONGODB_DB_NAME=dkik

# FastAPI Configuration
PORT=8000
HOST=0.0.0.0
DEBUG=True
LOG_LEVEL=INFO

# Background Worker Configuration
WORKER_POLLING_INTERVAL_MINUTES=15
WORKER_MAX_CONCURRENT_TASKS=10

# Security Configuration
ALLOWED_PHONE_NUMBERS=+5511999998888,+5511999997777
JWT_SECRET=change_this_to_a_secure_random_string
JWT_ALGORITHM=HS256
JWT_EXPIRATION_DAYS=30

# Notification Settings
MAX_NOTIFICATIONS_PER_DAY=10
NOTIFICATION_START_HOUR=8
NOTIFICATION_END_HOUR=20
EOF
  echo ".env file created. Please edit it with your actual credentials."
fi

# Check MongoDB connection
echo -e "\nChecking MongoDB connection..."
if $PYTHON -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv
import os

async def check_mongo():
    load_dotenv()
    try:
        uri = os.getenv('MONGODB_URI')
        if not uri:
            print('Error: MONGODB_URI not set in .env file')
            return False
        
        print(f'Connecting to MongoDB: {uri}')
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        await client.admin.command('ping')
        print('MongoDB connection successful!')
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f'MongoDB connection failed: {e}')
        return False

asyncio.run(check_mongo())
" 2>/dev/null; then
  mongo_ok=true
else
  mongo_ok=false
  echo "MongoDB connection failed. Please update your .env file with the correct MONGODB_URI."
fi

# Setup complete
echo -e "\n======================================================"
echo "DKIK WhatsApp Bot setup complete!"
echo "======================================================"
echo ""
echo "Next steps:"
echo "1. Edit the .env file with your actual credentials"
if [ "$mongo_ok" = false ]; then
  echo "2. Set up a MongoDB instance and update MONGODB_URI in .env"
fi
echo "3. Run the application with: uvicorn app.main:app --reload"
echo "4. Run the worker with: python worker/main.py"
echo ""
echo "For Twilio webhook setup:"
echo "1. Use ngrok to expose your local server: ngrok http 8000"
echo "2. Configure the Twilio webhook URL to your ngrok URL + /webhook"
echo ""
echo "Happy coding!"
echo "======================================================"

# Keep the virtual environment active
echo -e "\nVirtual environment is now active. To deactivate, run 'deactivate'"
