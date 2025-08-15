#!/bin/bash
# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${SCRIPT_DIR}/.venv"

if [ -f "${VENV}/bin/activate" ]; then
    source "${VENV}/bin/activate"
else
    echo "Error: Virtual environment not found at ${VENV}"
    exit 1
fi


python3 "${SCRIPT_DIR}/src/main.py" "$@"