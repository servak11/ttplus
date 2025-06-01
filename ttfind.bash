#!/bin/bash

# Define color codes
BLUE='\033[1;34m'   # Blue (Bright)
RED='\033[0;31m'    # Red
RESET='\033[0m'     # Reset color

# Check if a search term is provided
if [ -z "$1" ]; then
    echo "ttfind - find a note in the list of ttplus tasks"
    echo "Usage: $0 <search-string>"
    exit 1
fi

# Define the JSON file
JSON_FILE="tasks.json"

# Run grep with formatting
grep "$1" "$JSON_FILE" | sed -E 's/ *"note":/\n\n===== NOTE =====\n/g; s/\\n/\n/g; s/\\t/    /g'
#grep "$1" "$JSON_FILE" | sed -E 's/"note":/${BLUE}===== NOTE =====${RESET}/g; s/\\n/\n/g; s/\\t/    /g' | while read -r line; do
#    echo -e "$line"
#done