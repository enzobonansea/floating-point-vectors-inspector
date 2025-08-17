#!/bin/bash
set -e

# Nombre de la imagen y tar
IMAGE_NAME="fpvi"
IMAGE_TAG="latest"
TAR_PATH="$HOME/${IMAGE_NAME}.tar"

echo "[1/3] Building Docker image..."
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo "[2/3] Saving image to $TAR_PATH ..."
docker save -o "$TAR_PATH" ${IMAGE_NAME}:${IMAGE_TAG}

echo "[3/3] Loading image back from $TAR_PATH ..."
docker load -i "$TAR_PATH"

echo "✅ Done. Image '${IMAGE_NAME}:${IMAGE_TAG}' is available. Run with: docker run -it --rm fpvi:latest"
