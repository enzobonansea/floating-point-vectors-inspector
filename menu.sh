#!/bin/bash

while true; do
    echo "Select an option:"
    echo "1. Test alloc.c"
    echo "2. Test fprate with runspec monitor"
    echo "3. Run bash"
    echo "4. Exit"

    read -p "Enter your choice: " choice

    case $choice in
        1)
            echo "Testing alloc.c ..."
            valgrind --tool=memcheck --leak-check=no --track-origins=no --log-file=/tmp/alloc.log --undef-value-errors=no --time-stamp=yes -- /usr/alloc
            /usr/memlog_parser.py /tmp/alloc.log
            /bin/bash
            ;;
        2)
            /usr/local/bin/spec/fprate.sh
            /bin/bash
            ;;
        3)
            bash
            exit 0
            ;;
        4)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid option."
            ;;
    esac
done
