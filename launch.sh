#!/bin/sh

python="python3"

# No `readlink -e` on macOS...
cd "$("$python" -c "import os; print(os.path.dirname(os.path.realpath('$0')))")"

exec "$python" ./setup.py launch -- "$@"
