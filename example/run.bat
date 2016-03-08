echo start
@echo off
set path=.\bin\lua;.\bin\py;%path%
set ROOT=..\converter
set LUA_PATH=..\converter
lua ..\converter\main.lua config.lua files alias scripts output

pause
