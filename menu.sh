#!/bin/bash

while true; do
    echo "Select an option:"
    echo "1. Test blender"
    echo "2. Test SPEC2017"
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
            read -p "Which SPEC2017 app do you want to test? " user_input
            echo "Testing the SPEC2017 app $user_input"
            cd /usr/cpu2017
            source shrc
            cd /opt/valgrind
            inst/bin/valgrind --tool=memcheck --log-file=/tmp/memlog.log --undef-value-errors=no -- runcpu "$user_input"
            echo "Analyze /tmp/memlog.log"
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