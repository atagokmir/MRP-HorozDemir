#!/bin/bash

# Horoz Demir MRP System - Quick API Test Script
# Run this script to test core functionality

BASE_URL="http://localhost:8000/api/v1"

echo "=== Testing Horoz Demir MRP System ==="

# 1. Health Check
echo "1. Health Check:"
curl -s "$BASE_URL/../health" | jq '.'

# 2. Login and get token
echo -e "\n2. User Login:"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin@example.com", "password": "admin123"}')

echo $LOGIN_RESPONSE | jq '.'

# Extract token
TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.data.access_token')

if [ "$TOKEN" = "null" ]; then
    echo "Login failed! Cannot continue testing."
    exit 1
fi

# 3. Get current user info
echo -e "\n3. Current User Info:"
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/auth/me" | jq '.'

# 4. Get products
echo -e "\n4. Products List:"
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/master-data/products" | jq '.data.items[0:2]'

# 5. Get warehouses
echo -e "\n5. Warehouses List:"
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/master-data/warehouses" | jq '.data.items[0:2]'

# 6. Get inventory items
echo -e "\n6. Inventory Items:"
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/inventory/items" | jq '.data.items[0:2]'

# 7. Check stock availability
echo -e "\n7. Stock Availability Check (Product ID 1):"
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/inventory/availability/1" | jq '.'

# 8. Test stock-in operation
echo -e "\n8. Stock-In Operation:"
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "$BASE_URL/inventory/stock-in" \
  -d '{
    "product_id": 1,
    "warehouse_id": 1,
    "quantity": 100,
    "unit_cost": 25.50,
    "batch_number": "TEST-BATCH-001",
    "quality_status": "APPROVED",
    "notes": "API Test Batch"
  }' | jq '.'

# 9. Check availability after stock-in
echo -e "\n9. Stock Availability After Stock-In:"
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/inventory/availability/1" | jq '.'

echo -e "\n=== API Testing Complete ==="