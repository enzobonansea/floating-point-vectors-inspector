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
            /usr/local/bin/analyze.sh /usr/alloc
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
