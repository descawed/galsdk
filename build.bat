@echo off
setlocal

rem TODO: test this

if exist Pmw.py (
    del Pmw.py
)

for /f "delims=" %%i in ('poetry run python -c "import site; print(site.getsitepackages()[0])"') do set "site_packages=%%i"
set "pmw_dir=%site_packages%\Pmw\Pmw_2_1_1"
rem https://pmw.sourceforge.net/doc/dynamicloader.html
poetry run python "%pmw_dir%\bin\bundlepmw.py" "%pmw_dir%\lib"
copy /y "%pmw_dir%\lib\PmwBlt.py"
copy /y "%pmw_dir%\lib\PmwColor.py"
poetry run cxfreeze build
del Pmw.py PmwBlt.py PmwColor.py