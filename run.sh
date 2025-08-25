#!/bin/bash

##
# Why this script exists and WHY YOU NEED TO USE IT
#
# - The "tools" scripts have checks preventing them from running outside of a properly configured venv
# - The Main entry point to the driver (main.py) DOES NOT HAVE SUCH CHECKS.
# - This is because once the driver is built into a stand-alone executable that check is guaranteed to fail.
# - The check is guaranteed to fail because the stand-alone executable does not rely on an external python interpreter.
# - So when developing always test using "sudo ./run.sh" (this script) to mitigate against inconsistencies between the production driver and your dev environment.
# (if one is complaining about dependencies and the other isn't then congratulations, you've likely found your issue.)
##

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${SCRIPT_DIR}/.venv"

if [ -f "${VENV}/bin/activate" ]; then
    source "${VENV}/bin/activate"
else
    echo "Error: Virtual environment not found at ${VENV}"
    echo "Please create a virtual environment with minimum python version 3.11.0"
    echo "python3 -m venv venv"
    exit 1
fi

python3 "${SCRIPT_DIR}/src/main.py" "$@"
