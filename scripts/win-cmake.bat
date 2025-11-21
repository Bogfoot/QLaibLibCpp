@echo off
setlocal enabledelayedexpansion

rem Adjust this to your vcpkg clone
set VCPKG_ROOT=C:\Users\LjubljanaLab\Desktop\vcpkg
set BUILD_DIR=cpp\build

set TOOLCHAIN=%VCPKG_ROOT%\scripts\buildsystems\vcpkg.cmake
set QT_PREFIX=%VCPKG_ROOT%\installed\x64-windows\share\Qt6
set QT_DIR=%QT_PREFIX%\cmake

set COINCFINDER_LIB=%CD%\coincfinder\build\coincfinder_core.lib
set TDCBASE_LIB=%CD%\DLL_64bit\tdcbase.lib

if not exist "%COINCFINDER_LIB%" (
  echo Missing coincfinder_core.lib at %COINCFINDER_LIB%
  exit /b 1
)
if not exist "%TDCBASE_LIB%" (
  echo Missing tdcbase.lib at %TDCBASE_LIB%
  exit /b 1
)

cmake -S cpp -B %BUILD_DIR% -G "Ninja" ^
  -DCMAKE_TOOLCHAIN_FILE="%TOOLCHAIN%" ^
  -DCMAKE_PREFIX_PATH="%QT_PREFIX%" ^
  -DQt6_DIR="%QT_DIR" ^
  -DQQL_BUILD_GUI=ON -DQQL_ENABLE_CHARTS=ON -DQQL_ENABLE_QUTAG=ON ^
  -DCOINCFINDER_CORE="%COINCFINDER_LIB%" ^
  -DTDCBASE_LIB="%TDCBASE_LIB%"
if errorlevel 1 exit /b 1

cmake --build %BUILD_DIR%
if errorlevel 1 exit /b 1

echo Done.
endlocal
