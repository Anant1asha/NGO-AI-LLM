@echo off
title AASHA Learning Ecosystem — Root Orchestrator
cd /d "%~dp0"
node scripts\aasha_root_orchestrator.js %*
pause
