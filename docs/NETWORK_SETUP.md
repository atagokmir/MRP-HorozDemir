# Network Access Configuration for Horoz Demir MRP System

## Overview
The Horoz Demir MRP System has been configured to allow access from devices on the local network (192.168.1.x range). This setup resolves CORS warnings and enables multi-device access during development.

## Configuration Changes Made

### 1. Next.js Frontend Configuration (`frontend/next.config.ts`)
- **CORS Headers**: Added comprehensive CORS headers to allow cross-origin requests
- **API Rewrites**: Configured proxy rules to route `/api/*` requests to the backend
- **Removed deprecated settings**: Cleaned up invalid `allowedDevOrigins` configuration

### 2. Frontend API Client (`frontend/src/lib/api-client.ts`)
- **Network IP**: Updated default API base URL to use network IP (192.168.1.172:8000)
- **CORS Support**: Maintained all existing API transformation logic

### 3. Backend Configuration (already configured)
- **Host Binding**: Backend server binds to `0.0.0.0:8000` (all network interfaces)
- **CORS Middleware**: Comprehensive CORS configuration with local network support
- **Network Ranges**: Supports 192.168.1.x, 192.168.0.x, and 10.0.0.x networks

### 4. Package.json Scripts
- **Added**: `npm run dev:network` script for easy network-enabled development

## Current Access Points

### From Network Devices:
- **Frontend**: http://192.168.1.172:3001
- **Backend API**: http://192.168.1.172:8000
- **API Documentation**: http://192.168.1.172:8000/docs
- **Health Check**: http://192.168.1.172:8000/health

### From Host Machine:
- **Frontend**: http://localhost:3001 or http://127.0.0.1:3001
- **Backend API**: http://localhost:8000 or http://127.0.0.1:8000

## Quick Start for Network Access

### Option 1: Use the automated startup script
```bash
./start_network_servers.sh
```

### Option 2: Manual startup
```bash
# Terminal 1 - Backend
cd backend
source venv-mrp/bin/activate
python -m app.main

# Terminal 2 - Frontend
cd frontend
npm run dev:network
```

## Testing Network Connectivity

### 1. Test Page
Open `/test_network_access.html` in a browser from any network device to run automated connectivity tests.

### 2. Manual Testing
From any device on the network (192.168.1.x):

```bash
# Test backend health
curl http://192.168.1.172:8000/health

# Test frontend access
curl -I http://192.168.1.172:3001

# Test API endpoint
curl "http://192.168.1.172:8000/api/v1/master-data/warehouses?page=1&page_size=5"
```

## Troubleshooting

### If you get connection refused errors:
1. **Check firewall**: Ensure ports 3001 and 8000 are not blocked
2. **Verify IP**: Confirm 192.168.1.172 is the correct host IP
3. **Network connectivity**: Ensure all devices are on the same network

### If you see CORS errors:
1. **Check origin**: Ensure the requesting domain is in the allowed list
2. **Backend logs**: Check for origin validation messages
3. **Headers**: Verify proper CORS headers are present in responses

### Common Port Issues:
- Frontend automatically selects next available port if 3000 is in use
- Backend must use port 8000 (configured in API client)
- Check with: `lsof -i :3000` and `lsof -i :8000`

## Security Considerations

### Development vs Production:
- **Development**: Allows wildcard origins with validation middleware
- **Production**: Requires explicit origin configuration

### Local Network Safety:
- Network access is restricted to local IP ranges (192.168.x.x, 10.0.x.x, 172.16.x.x)
- Origin validation middleware blocks unauthorized external requests
- Rate limiting prevents abuse

## Files Modified

1. `/frontend/next.config.ts` - CORS and proxy configuration
2. `/frontend/src/lib/api-client.ts` - API base URL updated
3. `/frontend/package.json` - Added network dev script
4. `/backend/app/config.py` - Network ranges configured
5. `/backend/app/main.py` - CORS and origin validation

## Additional Files Created

1. `/test_network_access.html` - Network connectivity test page
2. `/start_network_servers.sh` - Automated startup script
3. `/NETWORK_SETUP.md` - This documentation

## Next Steps

1. **Test from multiple devices** to ensure connectivity
2. **Configure firewall rules** if needed for production deployment
3. **Update IP addresses** if the host machine IP changes
4. **Consider SSL/TLS** for production deployment