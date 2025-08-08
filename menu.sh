#!/bin/bash

# Repository version information (will be updated during CI build)
MAIN_REPO_COMMIT="MAIN_COMMIT_PLACEHOLDER"
PY_COMPRESS_COMMIT="PY_COMPRESS_COMMIT_PLACEHOLDER"

# Display version information
echo "===== Repository Information ====="
echo "floating-point-vectors-inspector commit: $MAIN_REPO_COMMIT"
echo "py-Compress-Simulator commit: $PY_COMPRESS_COMMIT"
echo "Build tag: fpvi-${MAIN_REPO_COMMIT}_pycs-${PY_COMPRESS_COMMIT}"

echo -e "\n"
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
