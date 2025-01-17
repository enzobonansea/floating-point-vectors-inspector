#!/bin/bash

while true; do
    echo "Select an option:"
    echo "1. Test blender"
    echo "2. Test lbm avoiding runspec"
    echo "3. Run bash"
    echo "4. Test alloc.c"
    echo "5. Exit"
    read -p "Enter your choice (1-5): " choice

    case $choice in
        1)
            echo "Testing Blender..."
            inst/bin/valgrind --tool=memcheck --log-file=/tmp/memlog.log --undef-value-errors=no -- blender -b -noaudio -P /tmp/example.py
            echo "Analyze /tmp/memlog.log"
            /bin/bash
            ;;
        2)
            /usr/local/bin/spec/lbm.sh
            /bin/bash
            ;;
        3)
            bash
            exit 0
            ;;
        4)
            echo "Testing alloc.c ..."
            inst/bin/valgrind --tool=memcheck --log-file=/tmp/memlog.log --undef-value-errors=no -- /tmp/alloc
            echo "Analyze /tmp/memlog.log"
            /bin/bash
            ;;
        5)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid option."
            ;;
    esac
done