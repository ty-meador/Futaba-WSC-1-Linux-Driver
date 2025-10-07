#!/bin/bash
cd "{{install_dir}}/{{build_dir}}"
exec ./{{executable_name}} "$@"./