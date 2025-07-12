#!/bin/bash

# Check if an executable is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <executable>"
    echo "Example: $0 /usr/alloc"
    exit 1
fi

EXECUTABLE="$1"

# Check if the executable exists and is executable
if [ ! -x "$EXECUTABLE" ]; then
    echo "Error: $EXECUTABLE is not executable or does not exist"
    exit 1
fi

# Extract the executable name (basename)
EXECUTABLE_NAME=$(basename "$EXECUTABLE")

# Generate timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Create log file path
LOG_FILE="/tmp/${EXECUTABLE_NAME}-${TIMESTAMP}.log"

echo "Running valgrind on $EXECUTABLE..."
echo "Log file: $LOG_FILE"

# Run valgrind
/opt/valgrind/inst/bin/valgrind --tool=memcheck --leak-check=no --track-origins=no --log-file="$LOG_FILE" --undef-value-errors=no --time-stamp=yes -- "$EXECUTABLE"

# Check if valgrind ran successfully
if [ $? -eq 0 ]; then
    echo "Valgrind completed successfully. Parsing log file..."
    
    # Run the memory log parser
    /usr/memlog_parser.py "$LOG_FILE"
    
    echo "Analysis complete. Log file: $LOG_FILE"
else
    echo "Valgrind failed to run"
    exit 1
fi
