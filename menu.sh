#!/bin/bash

while true; do
    echo "Select an option:"
    echo "1. Test blender"
    echo "2. Exit"
    read -p "Enter your choice (1-2): " choice

    case $choice in
        1)
            echo "Running Valgrind on Blender..."
            inst/bin/valgrind --tool=memcheck --undef-value-errors=no blender -b -noaudio -P /tmp/example.py
            
            echo ""
            echo ""
            echo "Check /tmp/malloc.log and /tmp/heap_write.log"
            /bin/bash
            ;;
        2)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid option. Please select 1 or 2."
            ;;
    esac
done