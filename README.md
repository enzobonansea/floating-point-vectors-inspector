# Floating-Point Vectors Inspector

A customized Valgrind tool that logs all floating-point writes to large buffers and analyzes their compressibility using an innovative compression technique.

## 🚀 CI/CD with GitHub Workflows

### Automated Build and Push (build.yml)
This workflow automatically triggers on every push to the `main` branch:

1. **Checkout Code**: Fetches the repository including GitLab submodules using SSH deploy keys
2. **Generate Image Tag**: Creates a unique tag using commit hashes from both main repo and submodules
3. **Update Configuration**: Automatically updates `menu.sh` with commit information
4. **Build Docker Image**: Constructs the container with all dependencies
5. **Push to ECR**: Uploads the image to AWS Elastic Container Registry with both versioned and `latest` tags

### Manual Deployment (deploy.yml)
This workflow allows manual deployment to EC2 instances:

1. **Workflow Dispatch**: Manually triggered with customizable parameters:
   - `tag`: Specify which image version to deploy (default: `latest`)
   - `baremetal_host`: Optional IP address override for deployment target
2. **Connectivity Check**: Verifies the target host is reachable
3. **Deploy**: Copies deployment script and executes it on the remote host

## 🖥️ Local Setup

### Prerequisites

#### For Linux:
- Docker Engine (20.10+)
- Git with submodule support
- Bash shell
- SPEC CPU2017 ISO file (`cpu2017-1.1.9.iso`)

#### For WSL2 (Windows Subsystem for Linux):
- WSL2 with Ubuntu 20.04+ or similar distribution
- Docker Desktop for Windows with WSL2 backend enabled
- Git configured in WSL2
- SPEC CPU2017 ISO file accessible from WSL2

### Installation Using install.sh

The `install.sh` script automates the local build process:

```bash
# 1. Clone the repository with submodules
git clone --recursive https://github.com/enzobonansea/floating-point-vectors-inspector.git
cd floating-point-vectors-inspector

# 2. Place the SPEC2017 ISO in the root directory
cp /path/to/cpu2017-1.1.9.iso .

# 3. Make the installation script executable
chmod +x install.sh

# 4. Run the installation script
./install.sh
```

#### What install.sh does:

1. **Retrieves commit information** from main repository and submodules
2. **Updates menu.sh** with actual commit hashes (replacing placeholders)
3. **Builds Docker image** with tag `fpvi:latest`
4. **Saves image** to `~/fpvi.tar` for portability
5. **Loads image** back into Docker for immediate use
6. **Restores original menu.sh** (removes temporary commit info)

### WSL2-Specific Setup

```bash
# Ensure Docker Desktop is running and WSL2 integration is enabled
docker --version

# If using Windows paths, convert them for WSL2
# Example: C:\Users\YourName\cpu2017-1.1.9.iso becomes /mnt/c/Users/YourName/cpu2017-1.1.9.iso
cp /mnt/c/path/to/cpu2017-1.1.9.iso .

# Run the installation
./install.sh
```

### Running the Container

After successful installation:

```bash
# Run the container interactively
docker run -it --rm fpvi:latest

# Or with volume mounting for persistent data
docker run -it --rm -v $(pwd)/output:/workspace/output fpvi:latest

# For WSL2, ensure proper path conversion
docker run -it --rm -v /mnt/c/your/windows/path:/workspace/output fpvi:latest
```

## 📁 Manual Setup (Alternative)

If you prefer manual setup without the install.sh script:

```bash
# 1. Download SPEC2017 ISO
# Place cpu2017-1.1.9.iso in the root folder

# 2. Build container manually
docker build -t valgrind-memlog .

# 3. Run container
docker run -it valgrind-memlog
```

## 🔧 About Memcheck Customizations

- Added files: `rbtree.h`, `rbtree.c`, `memlog.h`, and `memlog.c`
- These files implement custom functionality for logging memory operations
- Connected the original memcheck code with `memlog.h` to enable this functionality

## 🐛 Troubleshooting

### Common Issues on WSL2:
- **Docker not found**: Ensure Docker Desktop is running and WSL2 integration is enabled in Docker Desktop settings
- **Permission denied**: Run `chmod +x install.sh` to make the script executable
- **Path issues**: Use WSL2 paths (`/mnt/c/...`) instead of Windows paths (`C:\...`)

### Common Issues on Linux:
- **Docker permission denied**: Add your user to the docker group: `sudo usermod -aG docker $USER` and re-login
- **Submodule errors**: Ensure you have proper SSH keys configured for GitLab access
- **ISO file not found**: Verify the SPEC2017 ISO is named exactly `cpu2017-1.1.9.iso`
