#!/bin/bash

##
# The "tools" scripts are run only in a build environment and thus have checks preventing them from
# running outside of a properly configured venv; The Main entry point to the driver (main.py)
# DOES NOT HAVE SUCH CHECKS. This is because once it is built into a stand-alone executable the check
# is guaranteed to fail. So when developing always test using "sudo ./run.sh" (this script) to guarantee
# mitigate against inconsistencies between the production driver and your dev environment.
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
