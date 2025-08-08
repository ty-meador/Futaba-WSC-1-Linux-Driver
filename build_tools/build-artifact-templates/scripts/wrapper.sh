#!/bin/bash
# Futaba RC Driver Wrapper
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/{{executable_path}}" "$@"