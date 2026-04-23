@echo off
setlocal
cd /d "%~dp0"

set "SST_REMOTE_ROLE=controller"
set "SST_ALLOW_LAN=0"
set "SST_CONTROLLER_LIGHT=1"
set "SST_REMOTE_BOOTSTRAP=1"

call start.bat %*
