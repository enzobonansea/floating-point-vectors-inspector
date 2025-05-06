#!/bin/bash

while true; do
    echo "Select an option:"
    echo "1. Test alloc.c"
    echo "2. Run bash"
    echo "3. Exit"
    echo "4. Test lbm avoiding runspec"
    echo "5. Test namd avoiding runspec"
    echo "6. Test bwaves avoiding runspec"
    echo "7. Test nab avoiding runspec"
    echo "8. Test wrf avoiding runspec"
    echo "9. Test fotonik with runspec monitor"
    echo "10. Test fprate with runspec monitor"

    read -p "Enter your choice: " choice

    case $choice in
        1)
            echo "Testing alloc.c ..."
            inst/bin/valgrind --tool=memcheck --leak-check=no --track-origins=no --log-file=/tmp/memlog.log --undef-value-errors=no --time-stamp=yes -- /usr/alloc
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
        7)
            /usr/local/bin/spec/nab.sh
            /bin/bash
            ;;
        8)
            /usr/local/bin/spec/wrf.sh
            /bin/bash
            ;;
        9)
            /usr/local/bin/spec/fotonik.sh
            /bin/bash
            ;;
        10)
            /usr/local/bin/spec/fprate.sh
            /bin/bash
            ;;
        *)
            echo "Invalid option."
            ;;
    esac
done
