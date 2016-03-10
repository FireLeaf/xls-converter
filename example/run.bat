echo start
@echo off
set path=.\bin\lua;.\bin\py;%path%

set BIN_ROOT=..\converter
set LUA_PATH=%BIN_ROOT%/?.lua
lua %BIN_ROOT%\main.lua config.lua files alias scripts output

pause