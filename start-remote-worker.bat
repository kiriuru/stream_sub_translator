@echo off
setlocal
cd /d "%~dp0"

set "SST_REMOTE_ROLE=worker"
set "SST_ALLOW_LAN=1"
set "SST_REMOTE_BOOTSTRAP=1"

call start.bat %*
