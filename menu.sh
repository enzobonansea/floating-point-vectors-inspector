#!/bin/bash

while true; do
    echo "Select an option:"
    echo "1. Test blender"
    echo "2. Test lbm avoiding runspec"
    echo "3. Test namd avoiding runspec"
    echo "4. Test bwaves avoiding runspec"
    echo "5. Run bash"
    echo "6. Test alloc.c"
    echo "7. Exit"
    read -p "Enter your choice: " choice

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
            /usr/local/bin/spec/namd.sh
            /bin/bash
            ;;
        4)
            /usr/local/bin/spec/bwaves.sh
            /bin/bash
            ;;
        5)
            bash
            exit 0
            ;;
        6)
            echo "Testing alloc.c ..."
            inst/bin/valgrind --tool=memcheck --log-file=/tmp/memlog.log --undef-value-errors=no -- /tmp/alloc
            echo "Analyze /tmp/memlog.log"
            /bin/bash
            ;;
        7)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid option."
            ;;
    esac
done