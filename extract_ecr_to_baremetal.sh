#!/bin/bash
# Extract ECR Docker image to bare metal filesystem

set -e

# Replace with your actual image tag from ECR
ECR_IMAGE="764515255972.dkr.ecr.eu-north-1.amazonaws.com/computer-science/floating-point-vectors-inspector:main-a813abf_pyc-5bfcdef"

# Or use latest if you want the most recent
# ECR_IMAGE="764515255972.dkr.ecr.eu-north-1.amazonaws.com/computer-science/floating-point-vectors-inspector:latest"

echo "=== Installing Docker and AWS CLI ==="
sudo apt-get update
sudo apt-get install -y docker.io awscli

echo "=== Logging into ECR ==="
aws ecr get-login-password --region eu-north-1 | sudo docker login --username AWS --password-stdin 764515255972.dkr.ecr.eu-north-1.amazonaws.com

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
# Mount essential filesystems for chroot
sudo mount --bind /dev /opt/hpc-app/dev
sudo mount --bind /proc /opt/hpc-app/proc
sudo mount --bind /sys /opt/hpc-app/sys
sudo mount --bind /tmp /opt/hpc-app/tmp

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

echo "Entering HPC Analysis Environment..."
sudo chroot /opt/hpc-app /enter_hpc.sh
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