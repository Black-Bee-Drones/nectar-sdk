#!/bin/bash
set -e

REPO_URL="https://github.com/Black-Bee-Drones/nectar-sdk.git"
DEFAULT_WORKSPACE="$HOME/ros2_ws"
DEFAULT_BRANCH="main"
VALID_BRANCHES=("main" "dev")

# --- Banner ---

echo ""
echo "  ╔══════════════════════════════════╗"
echo "  ║       Nectar SDK Bootstrap       ║"
echo "  ╚══════════════════════════════════╝"
echo ""

# --- Checks ---

if [[ $EUID -eq 0 ]]; then
    echo "[ERROR] Do not run as root. The script will use sudo when needed."
    exit 1
fi

if ! grep -qiE 'ubuntu|debian' /etc/os-release 2>/dev/null; then
    echo "[WARN]  Only tested on Ubuntu/Debian."
    read -p "  Continue anyway? (y/N): " -n 1 -r && echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then exit 1; fi
    echo ""
fi

# --- Interactive prompts (skipped in non-interactive mode) ---

if [[ "${NON_INTERACTIVE:-}" == "true" ]]; then
    WORKSPACE="${ROS2_WORKSPACE:-$DEFAULT_WORKSPACE}"
    BRANCH="${NECTAR_BRANCH:-$DEFAULT_BRANCH}"
else
    # Workspace path
    echo "  Where should the ROS 2 workspace be created?"
    read -p "  Workspace path [${DEFAULT_WORKSPACE}]: " input_ws
    WORKSPACE="${input_ws:-$DEFAULT_WORKSPACE}"

    # Expand ~ if the user typed it
    WORKSPACE="${WORKSPACE/#\~/$HOME}"

    # Validate: must be an absolute path
    if [[ "$WORKSPACE" != /* ]]; then
        echo "[ERROR] Workspace path must be absolute (e.g. /home/$USER/ros2_ws)."
        exit 1
    fi

    echo ""

    # Branch
    echo "  Which branch to install?"
    echo "    1) main   (stable release)"
    echo "    2) dev    (latest development)"
    read -p "  Select [1]: " input_branch
    input_branch="${input_branch:-1}"

    case "$input_branch" in
        1|main)  BRANCH="main" ;;
        2|dev)   BRANCH="dev" ;;
        *)
            echo "[ERROR] Invalid option: ${input_branch}. Choose 1 or 2."
            exit 1
            ;;
    esac

    echo ""

    # Confirm
    echo "  ─────────────────────────────────"
    echo "  Workspace:  ${WORKSPACE}"
    echo "  Branch:     ${BRANCH}"
    echo "  Repository: ${REPO_URL}"
    echo "  ─────────────────────────────────"
    echo ""
    read -p "  Proceed with installation? (Y/n): " -n 1 -r && echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        echo "  Cancelled."
        exit 0
    fi
    echo ""
fi

PROJECT_DIR="${WORKSPACE}/src/nectar-sdk"

# --- Install git if missing ---

if ! command -v git &>/dev/null; then
    echo "[INFO]  Installing git..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq git
fi

# --- Clone into workspace ---

mkdir -p "${WORKSPACE}/src"

if [ -d "$PROJECT_DIR" ]; then
    echo "[INFO]  Repository already exists at ${PROJECT_DIR}, updating..."
    cd "$PROJECT_DIR" && git checkout "$BRANCH" && git pull origin "$BRANCH"
else
    echo "[INFO]  Cloning into ${PROJECT_DIR}..."
    git clone -b "$BRANCH" "$REPO_URL" "$PROJECT_DIR"
fi

# --- Delegate to full installer ---

echo "[INFO]  Starting full installation..."
echo ""
cd "$PROJECT_DIR"
exec ./scripts/setup.sh full-install
