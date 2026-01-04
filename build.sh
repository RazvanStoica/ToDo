#!/bin/bash
set -e

# Build script for ToDo app
# Runs tests and builds Docker image only if tests pass

# Configuration
IMAGE_NAME="${IMAGE_NAME:-todo-app}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== ToDo App Build System ===${NC}"
echo ""

# Step 1: Check for required tools
echo -e "${YELLOW}[1/4] Checking requirements...${NC}"
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}Error: python3 is required${NC}"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo -e "${RED}Error: docker is required${NC}"; exit 1; }
echo -e "${GREEN}Requirements satisfied${NC}"
echo ""

# Step 2: Install test dependencies
echo -e "${YELLOW}[2/4] Installing test dependencies...${NC}"
if [ -d "venv" ]; then
    source venv/bin/activate
else
    python3 -m venv venv
    source venv/bin/activate
fi
pip install -q -r requirements.txt pytest pytest-cov
echo -e "${GREEN}Dependencies installed${NC}"
echo ""

# Step 3: Run tests
echo -e "${YELLOW}[3/4] Running tests...${NC}"
if python -m pytest test_server.py -v --tb=short; then
    echo ""
    echo -e "${GREEN}All tests passed!${NC}"
else
    echo ""
    echo -e "${RED}Tests failed! Build aborted.${NC}"
    exit 1
fi
echo ""

# Step 4: Build Docker image
echo -e "${YELLOW}[4/4] Building Docker image...${NC}"
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .

echo ""
echo -e "${GREEN}=== Build Complete ===${NC}"
echo -e "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "To run the container:"
echo "  docker run -p 3000:3000 ${IMAGE_NAME}:${IMAGE_TAG}"
