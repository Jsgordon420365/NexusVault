#!/bin/bash
# Usage: ./vault_search.sh "search term"
# This simulates a Claude "Skill" searching your persistent memory.

SEARCH_TERM=$1
echo "### Results for: $SEARCH_TERM"
echo "---"

# Search concepts and code, returning only the top 5 most relevant file links
grep -ril "$SEARCH_TERM" 03_Concepts 04_Code | head -n 5 | sed 's/^/- [[/' | sed 's/$/]]/'
