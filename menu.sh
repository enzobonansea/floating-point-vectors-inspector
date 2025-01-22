#!/bin/bash

while true; do
    echo "Select an option:"
    echo "1. Test alloc.c"
    echo "2. Run bash"
    echo "3. Exit"
    echo "4. Test lbm avoiding runspec"
    echo "5. Test namd avoiding runspec"
    echo "6. Test bwaves avoiding runspec"

    read -p "Enter your choice: " choice

    case $choice in
        1)
            echo "Testing alloc.c ..."
            inst/bin/valgrind --tool=memcheck --log-file=/tmp/memlog.log --undef-value-errors=no -- /usr/alloc
            echo "Analyze /tmp/memlog.log"
            /bin/bash
            ;;
        2)
            bash
            exit 0
            ;;
        3)
            echo "Exiting..."
            exit 0
            ;;
        4)
            /usr/local/bin/spec/lbm.sh
            /bin/bash
            ;;
        5)
            /usr/local/bin/spec/namd.sh
            /bin/bash
            ;;
        6)
            /usr/local/bin/spec/bwaves.sh
            /bin/bash
            ;;
        *)
            echo "Invalid option."
            ;;
    esac
done
