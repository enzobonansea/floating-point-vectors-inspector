#!/bin/bash
set -e

# Nombre de la imagen y tar
IMAGE_NAME="fpvi"
IMAGE_TAG="latest"
TAR_PATH="$HOME/${IMAGE_NAME}.tar"

# Get commit information for placeholders
echo "[1/4] Getting commit information..."
MAIN_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
PY_COMPRESS_COMMIT=$(git -C py-Compress-Simulator rev-parse --short HEAD 2>/dev/null || echo "no-submodule")

# Update menu.sh with commit information
echo "Updating menu.sh with commit information..."
if [ -f menu.sh ]; then
    cp menu.sh menu.sh.bak
    sed -i "s/MAIN_COMMIT_PLACEHOLDER/$MAIN_COMMIT/g" menu.sh
    sed -i "s/PY_COMPRESS_COMMIT_PLACEHOLDER/$PY_COMPRESS_COMMIT/g" menu.sh
    echo "Updated menu.sh with main commit: $MAIN_COMMIT and py-compress commit: $PY_COMPRESS_COMMIT"
fi

echo "[2/4] Building Docker image..."
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo "[3/4] Saving image to $TAR_PATH ..."
docker save -o "$TAR_PATH" ${IMAGE_NAME}:${IMAGE_TAG}

echo "[4/4] Loading image back from $TAR_PATH ..."
docker load -i "$TAR_PATH"

# Restore original menu.sh if backup exists
if [ -f menu.sh.bak ]; then
    mv menu.sh.bak menu.sh
    echo "Restored original menu.sh"
fi

echo "✅ Done. Image '${IMAGE_NAME}:${IMAGE_TAG}' is available. Run with: docker run -it --rm fpvi:latest"
