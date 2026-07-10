@echo off
setlocal
set /p PYTHON_EXE=<"%~dp0python-path.txt"
"%PYTHON_EXE%" -u "%~dp0native_host.py" %*

