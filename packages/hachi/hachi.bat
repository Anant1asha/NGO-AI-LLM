@echo off
REM Hachi CLI wrapper - delegates to the installed script in .venv
"%~dp0.venv\Scripts\hachi.exe" %*
