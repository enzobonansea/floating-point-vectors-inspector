#!/bin/bash

while true; do
    echo "Select an option:"
    echo "1. Test blender"
    echo "2. Test SPEC2017"
    echo "3. Run bash"
    echo "4. Exit"
    read -p "Enter your choice (1-4): " choice

    case $choice in
        1)
            echo "Running Valgrind on Blender..."
            inst/bin/valgrind --tool=memcheck --undef-value-errors=no blender -b -noaudio -P /tmp/example.py
            
            echo ""
            echo ""
            echo "Move /tmp/malloc.log and /tmp/heap_write.log to your local machine and analyze them following results\blender\test1.ipynb"
            /bin/bash
            ;;
        2)
            read -p "Which SPEC2017 app do you want to test? " user_input
            echo "Running Valgrind on the SPEC2017 app $user_input"
            cd /usr/cpu2017
            source shrc
            cd /opt/valgrind
            inst/bin/valgrind --tool=memcheck --undef-value-errors=no runcpu "$user_input"
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