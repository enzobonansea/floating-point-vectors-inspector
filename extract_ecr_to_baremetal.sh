#!/bin/bash
# Extract ECR Docker image to bare metal filesystem

set -e

# Get image tag from environment variable or fallback to default
if [ -n "$IMAGE_TAG" ]; then
  echo "Using provided IMAGE_TAG: $IMAGE_TAG"
elif [ -f ".ecr_image_tag" ]; then
  IMAGE_TAG=$(cat .ecr_image_tag)
  echo "Using IMAGE_TAG from .ecr_image_tag: $IMAGE_TAG"
else
  echo "No IMAGE_TAG provided and .ecr_image_tag file not found, using 'latest' tag."
  IMAGE_TAG="latest"
fi
ECR_IMAGE="764515255972.dkr.ecr.us-east-1.amazonaws.com/computer-science/floating-point-vectors-inspector:${IMAGE_TAG}"

echo "=== Installing Docker and AWS CLI ==="
sudo apt-get update
sudo apt-get install -y docker.io curl unzip
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
rm -rf aws/
unzip awscliv2.zip
if command -v aws >/dev/null 2>&1; then
  sudo ./aws/install --update
else
  sudo ./aws/install
fi
rm -rf awscliv2.zip aws/

echo "=== Configuring AWS credentials ==="
# Print variables for debugging (will be masked in logs)
echo "AWS_ACCESS_KEY_ID is ${AWS_ACCESS_KEY_ID:+set}"
echo "AWS_SECRET_ACCESS_KEY is ${AWS_SECRET_ACCESS_KEY:+set}"

if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
  echo "ERROR: AWS credentials not set. This script is intended for CI/CD use only."
  exit 1
fi

# Explicitly export the credentials again to ensure they're available
export AWS_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY
export AWS_DEFAULT_REGION="us-east-1"

echo "=== Logging into ECR ==="
aws ecr get-login-password --region us-east-1 | sudo docker login --username AWS --password-stdin 764515255972.dkr.ecr.us-east-1.amazonaws.com

echo "=== Pulling your image ==="
sudo docker pull $ECR_IMAGE

echo "=== Creating container (without running) ==="
CONTAINER_ID=$(sudo docker create $ECR_IMAGE)

echo "=== Extracting filesystem to /opt/hpc-app ==="
sudo mkdir -p /opt/hpc-app
sudo docker export $CONTAINER_ID | sudo tar -x -C /opt/hpc-app

echo "=== Cleaning up container ==="
sudo docker rm $CONTAINER_ID

echo "=== Setting up chroot environment ==="
# Mount essential filesystems for chroot (more robust)
sudo mkdir -p /opt/hpc-app/{dev,proc,sys,tmp}
sudo mount --rbind /dev /opt/hpc-app/dev
sudo mount --make-rslave /opt/hpc-app/dev || true
sudo mount -t proc proc /opt/hpc-app/proc
sudo mount --rbind /sys /opt/hpc-app/sys
sudo mount --make-rslave /opt/hpc-app/sys || true
sudo mount --rbind /tmp /opt/hpc-app/tmp
sudo mount --make-rslave /opt/hpc-app/tmp || true

echo "=== Creating workspace directory ==="
sudo mkdir -p /opt/hpc-app/workspace

echo "=== Setting up entry script ==="
cat << 'EOF' | sudo tee /opt/hpc-app/enter_hpc.sh
#!/bin/bash
# Entry script to run your HPC application

# Set environment variables
export PATH="/opt/valgrind/inst/bin:${PATH}"
export DEBIAN_FRONTEND=noninteractive

# Change to workspace
cd /workspace

# Run your menu
echo "Starting HPC Analysis Environment..."
echo "=================================="
/usr/local/bin/menu.sh
EOF

sudo chmod +x /opt/hpc-app/enter_hpc.sh

echo "=== Creating host entry script ==="
cat << 'EOF' | sudo tee /usr/local/bin/enter-hpc
#!/bin/bash
# Enter the HPC environment from host
set -e

echo "Entering HPC Analysis Environment..."

# Ensure chroot mounts are present (idempotent)
SUDO=""
if command -v sudo >/dev/null 2>&1; then SUDO="sudo"; fi

$SUDO mkdir -p /opt/hpc-app/{dev,proc,sys,tmp}

for d in dev sys tmp; do
  if ! mountpoint -q "/opt/hpc-app/$d"; then
    echo "Mounting /$d into chroot..."
    $SUDO mount --rbind "/$d" "/opt/hpc-app/$d"
    $SUDO mount --make-rslave "/opt/hpc-app/$d" || true
  fi
done

if ! mountpoint -q "/opt/hpc-app/proc"; then
  echo "Mounting procfs into chroot..."
  $SUDO mount -t proc proc "/opt/hpc-app/proc"
fi

$SUDO chroot /opt/hpc-app /enter_hpc.sh
EOF

sudo chmod +x /usr/local/bin/enter-hpc

echo "================================================"
echo "✅ SUCCESS! Your HPC environment is ready!"
echo "================================================"
echo ""
echo "To enter your HPC environment, run:"
echo "  enter-hpc"
echo ""
echo "Or manually:"
echo "  sudo chroot /opt/hpc-app /bin/bash"
echo "  cd /workspace"
echo "  /usr/local/bin/menu.sh"
echo ""
echo "Your application files are in: /opt/hpc-app"
echo "Workspace directory: /opt/hpc-app/workspace"