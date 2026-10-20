#!/bin/bash
# Usage: ./fix_pattern.sh <file_path>

python3 ./fix_pattern.py "$1" "$1.fixed"
mv "$1.fixed" "$1"

