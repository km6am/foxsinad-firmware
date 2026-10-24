@echo off
REM Windows version of ./run: start a tool with a Python that is 3.10 or
REM newer and has pyserial.
REM   run.cmd tools\flash.py
REM   run.cmd tools\foxctl.py --status
setlocal
set "HERE=%~dp0"
if "%~1"=="" (
  echo usage: run.cmd tools\flash.py ^| tools\foxctl.py [arguments]
  exit /b 2
)
set "SCRIPT=%HERE%%~1"
shift
set "ARGS="
:collect
if "%~1"=="" goto launch
set ARGS=%ARGS% %1
shift
goto collect
:launch
for %%P in (
  "%HERE%.venv\Scripts\python.exe"
  "%CONDA_PREFIX%\python.exe"
  "py.exe"
  "python.exe"
) do (
  %%P -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1 && ^
  %%P -c "import serial" >nul 2>&1 && (
    %%P "%SCRIPT%" %ARGS%
    exit /b
  )
)
echo No Python 3.10 or newer with pyserial was found. Create one with:
echo     py -m venv "%HERE%.venv"
echo     "%HERE%.venv\Scripts\python.exe" -m pip install -r "%HERE%requirements.txt"
exit /b 1
