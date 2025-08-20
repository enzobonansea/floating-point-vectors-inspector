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
    echo "1. Compress example"
    echo "2. Compress SPEC fprate"
    echo "3. Compress SPEC app"
    echo "4. Compress generic app (absolute path must start with /usr)"
    echo "5. Run bash"
    echo "6. Exit"

    read -p "Enter your choice: " choice

    case $choice in
        1)
            echo "Compressing example..."
            /usr/local/bin/analyze.sh /usr/alloc
            /bin/bash
            ;;
        2)
            /usr/local/bin/spec/fprate.sh
            /bin/bash
            ;;
        3)
            read -p "Enter SPEC app name: " app_name
            if [ -n "$app_name" ]; then
                cd /usr/cpu2017
                . ./shrc
                runcpu --action=run --config=memlog-monitor.cfg --size=test $app_name
            else
                echo "No app name provided."
            fi
            /bin/bash
            ;;
        4)
            read -p "Enter executable path: " executable_path
            if [ -n "$executable_path" ]; then
                echo "Compressing $executable_path ..."
                /usr/local/bin/analyze.sh $executable_path
            else
                echo "No executable path provided."
            fi
            /bin/bash
            ;;
        5)
            bash
            exit 0
            ;;
        6)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid option."
            ;;
    esac
done
