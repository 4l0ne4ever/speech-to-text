#!/bin/bash

# Load environment variables and run real-time demo

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Loading configuration and starting demo..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Load .env file
if [ -f .env ]; then
    echo -e "${GREEN}✓${NC} Found .env file"
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
else
    echo -e "${RED}✗${NC} .env file not found!"
    exit 1
fi

# Check for credentials file
CREDS_FILE="speech-processing-prod-9ffbefa55e2c.json"
if [ -f "$CREDS_FILE" ]; then
    echo -e "${GREEN}✓${NC} Found credentials: $CREDS_FILE"
    export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/$CREDS_FILE"
else
    echo -e "${RED}✗${NC} Credentials file not found: $CREDS_FILE"
    exit 1
fi

# Set project ID
if [ -n "$GCP_PROJECT_ID" ]; then
    echo -e "${GREEN}✓${NC} Project ID: $GCP_PROJECT_ID"
    export GOOGLE_CLOUD_PROJECT="$GCP_PROJECT_ID"
else
    echo -e "${RED}✗${NC} GCP_PROJECT_ID not set in .env"
    exit 1
fi

# Check microphone permissions
echo ""
echo -e "${YELLOW}📌 Note:${NC} Make sure microphone permissions are granted"
echo "   System Settings > Privacy & Security > Microphone"
echo ""

# Display configuration
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Configuration:"
echo "  • Project: $GOOGLE_CLOUD_PROJECT"
echo "  • Credentials: $GOOGLE_APPLICATION_CREDENTIALS"
echo "  • Language: ${SPEECH_LANGUAGE_CODE:-ja-JP}"
echo "  • Model: ${SPEECH_MODEL:-latest_long}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Activate virtual environment if exists
if [ -d "venv" ]; then
    echo -e "${GREEN}✓${NC} Activating virtual environment..."
    source venv/bin/activate
fi

# Run demo
python3 demo_simple.py
