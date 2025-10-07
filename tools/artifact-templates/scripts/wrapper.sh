#!/bin/bash
# Futaba RC Driver Wrapper
cd "{{install_dir}}/build"
exec ./{{executable_name}} "$@"