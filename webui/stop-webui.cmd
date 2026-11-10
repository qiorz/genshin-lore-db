@echo off
rem 统一入口在项目根目录，这里只做转发
call "%~dp0..\stop.cmd" %*
