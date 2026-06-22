#!/bin/bash
# Customer Voice Dashboard - Cron Scraper Wrapper
# This script is intended to be run by cron to scrape recent reviews periodically.

# Change to the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure we're in the right directory and the script exists
if [ ! -f "main.py" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Error: main.py not found in $SCRIPT_DIR" >> cron.log
    exit 1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting cron scrape job..." >> cron.log

# Activate the virtual environment from the parent directory
source ../.venv/bin/activate

# Run the python scraper in cron mode to fetch the newest data
echo "$(date '+%Y-%m-%d %H:%M:%S') - Running incremental (cron) fetch..." >> cron.log
python3 main.py --cron >> cron.log 2>&1

# Run the python scraper in backfill mode to fetch a chunk of historical data
echo "$(date '+%Y-%m-%d %H:%M:%S') - Running historical backfill fetch..." >> cron.log
python3 main.py --backfill >> cron.log 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S') - Cron scrape job completed." >> cron.log
