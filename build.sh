#!/usr/bin/env bash
set -euo pipefail

rm -f Pmw.py
site_packages=$(poetry run python -c "import site; print(site.getsitepackages()[0])")
pmw_dir="$site_packages/Pmw/Pmw_2_1_1" # hard-coded for now
# https://pmw.sourceforge.net/doc/dynamicloader.html
poetry run python "$pmw_dir/bin/bundlepmw.py" "$pmw_dir/lib"
cp -f "$pmw_dir/lib/PmwBlt.py" .
cp -f "$pmw_dir/lib/PmwColor.py" .
poetry run cxfreeze build
rm -f Pmw.py PmwBlt.py PmwColor.py