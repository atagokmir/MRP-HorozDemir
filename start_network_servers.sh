#!/bin/bash

# Horoz Demir MRP System - Network Server Startup Script
# This script starts both frontend and backend servers configured for local network access

echo "🚀 Starting Horoz Demir MRP System for Network Access"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get current IP address
IP_ADDRESS=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
echo -e "${BLUE}📍 Detected IP Address: ${IP_ADDRESS}${NC}"

# Function to check if port is available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        return 1
    else
        return 0
    fi
}

# Check if backend port is available
if ! check_port 8000; then
    echo -e "${YELLOW}⚠️  Port 8000 is already in use. Attempting to kill existing process...${NC}"
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

# Check if frontend port is available
if ! check_port 3000; then
    echo -e "${YELLOW}⚠️  Port 3000 is already in use. Frontend will use next available port.${NC}"
fi

echo ""
echo -e "${BLUE}🔧 Configuration Summary:${NC}"
echo -e "Frontend: http://${IP_ADDRESS}:3000 (or next available port)"
echo -e "Backend:  http://${IP_ADDRESS}:8000"
echo -e "Network range configured: 192.168.1.x, 192.168.0.x, 10.0.0.x"
echo ""

# Start backend server
echo -e "${GREEN}🟢 Starting Backend Server...${NC}"
cd backend
source venv-mrp/bin/activate
python -m app.main &
BACKEND_PID=$!
echo -e "${GREEN}✅ Backend started with PID: ${BACKEND_PID}${NC}"

# Wait for backend to start
echo -e "${YELLOW}⏳ Waiting for backend to initialize...${NC}"
sleep 5

# Test backend health
if curl -s "http://localhost:8000/health" > /dev/null; then
    echo -e "${GREEN}✅ Backend health check passed${NC}"
else
    echo -e "${RED}❌ Backend health check failed${NC}"
fi

# Start frontend server
echo -e "${GREEN}🟢 Starting Frontend Server...${NC}"
cd ../frontend
npm run dev -- --hostname 0.0.0.0 &
FRONTEND_PID=$!
echo -e "${GREEN}✅ Frontend started with PID: ${FRONTEND_PID}${NC}"

# Wait for frontend to start
echo -e "${YELLOW}⏳ Waiting for frontend to initialize...${NC}"
sleep 8

echo ""
echo -e "${GREEN}🎉 Servers Started Successfully!${NC}"
echo -e "${BLUE}📱 Access Points:${NC}"
echo -e "   • Frontend: http://${IP_ADDRESS}:3000"
echo -e "   • Backend API: http://${IP_ADDRESS}:8000"
echo -e "   • API Documentation: http://${IP_ADDRESS}:8000/docs"
echo -e "   • Health Check: http://${IP_ADDRESS}:8000/health"
echo ""
echo -e "${BLUE}🧪 Testing:${NC}"
echo -e "   • Open test_network_access.html in a browser on another device"
echo -e "   • Or access the frontend directly from another device on your network"
echo ""
echo -e "${YELLOW}💡 Tips:${NC}"
echo -e "   • Make sure your firewall allows connections on ports 3000 and 8000"
echo -e "   • Other devices should be on the same network (192.168.1.x range)"
echo -e "   • Press Ctrl+C to stop both servers"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down servers...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}✅ Servers stopped${NC}"
    exit 0
}

# Set trap to cleanup on exit
trap cleanup INT TERM

# Keep script running and monitor servers
echo -e "${BLUE}📊 Monitoring servers... Press Ctrl+C to stop${NC}"
while true; do
    # Check if processes are still running
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${RED}❌ Backend server stopped unexpectedly${NC}"
        break
    fi
    
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo -e "${RED}❌ Frontend server stopped unexpectedly${NC}"
        break
    fi
    
    sleep 30
    echo -e "${BLUE}📊 Servers running... ($(date))${NC}"
done

cleanup