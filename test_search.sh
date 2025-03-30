#!/bin/bash

# Test search functionality in Django application
SERVER_URL="http://localhost:8083"
SEARCH_TERMS=("10X" "MX" "AT" "mouse" "human" "COMPLETED" "1049")

echo "=== Testing Search Functionality ==="
echo

for term in "${SEARCH_TERMS[@]}"; do
    echo "Testing search for term: $term"
    
    # Use curl to make a request and capture the response
    RESPONSE=$(curl -s "${SERVER_URL}/?search=${term}")
    
    # Check if response contains data
    if [[ $RESPONSE == *"No items found"* ]]; then
        echo "ERROR: No results found for term '$term'"
    else
        # Count number of rows in the table body
        # Extract the table body content
        TABLE_BODY=$(echo "$RESPONSE" | grep -o '<tbody>.*</tbody>' | sed 's/<tbody>//;s/<\/tbody>//')
        
        # Count the number of rows
        ROW_COUNT=$(echo "$TABLE_BODY" | grep -o '<tr' | wc -l)
        
        echo "SUCCESS: Found $ROW_COUNT results for term '$term'"
        
        # Extract a couple of results for verification
        echo "Sample results:"
        echo "$RESPONSE" | grep -o '<td>[^<]*</td>' | head -n 10 | sed 's/<td>//g;s/<\/td>//g' | nl
    fi
    
    echo "----------------------------------------"
done

# Test combined search with filters
echo "Testing search with filters:"
FILTERED_SEARCH="${SERVER_URL}/?search=10X&organism=mouse"
RESPONSE=$(curl -s "$FILTERED_SEARCH")

# Count number of rows
TABLE_BODY=$(echo "$RESPONSE" | grep -o '<tbody>.*</tbody>' | sed 's/<tbody>//;s/<\/tbody>//')
ROW_COUNT=$(echo "$TABLE_BODY" | grep -o '<tr' | wc -l)

echo "Combined search for '10X' with organism 'mouse' found $ROW_COUNT results"
echo "----------------------------------------"

echo "=== Search Test Complete ===" 