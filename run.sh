#!/bin/bash

# Color definitions for gorgeous terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${PURPLE}====================================================${NC}"
echo -e "${PURPLE}             STREAMSAVE DOWNLOADER LAUNCH           ${NC}"
echo -e "${PURPLE}====================================================${NC}"

# 1. Verify python3 availability
if ! command -v python3 &> /dev/null
then
    echo -e "${RED}Error: python3 is not installed on your system.${NC}"
    echo -e "Please install Python 3 and try again."
    exit 1
fi

# 2. Initialize python3 virtual environment
if [ ! -d "venv" ]; then
    echo -e "${BLUE}[1/3] Creating Python Virtual Environment (venv)...${NC}"
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to initialize virtual environment.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Virtual environment created successfully.${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists.${NC}"
fi

# 3. Enable virtual environment
source venv/bin/activate

# 4. Synchronize packages
echo -e "${BLUE}[2/3] Syncing dependencies (Flask, yt-dlp, requests)...${NC}"
pip install --upgrade pip
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install dependencies.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Dependencies synchronized successfully.${NC}"

# 5. Boot Flask Application
echo -e "${BLUE}[3/3] Starting Flask Application on Port 5001...${NC}"
echo -e "${YELLOW}===================================================="
echo -e "🚀 StreamSave is active and ready!"
echo -e "👉 Open your web browser and navigate to:"
echo -e "   http://127.0.0.1:5001"
echo -e "====================================================${NC}"
echo -e "${BLUE}To shutdown the server, press Ctrl+C in this window.${NC}"
echo ""

python3 app.py
