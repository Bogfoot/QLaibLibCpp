@echo off
setlocal enabledelayedexpansion

rem Paths relative to repo root
set REPO_ROOT=%~dp0..
set VCPKG_ROOT=%REPO_ROOT%\..\vcpkg
set BUILD_DIR=cpp\build

set TOOLCHAIN=%VCPKG_ROOT%\scripts\buildsystems\vcpkg.cmake
set QT_PREFIX=%VCPKG_ROOT%\installed\x64-windows\share\Qt6
set QT_DIR=%QT_PREFIX%\cmake

set COINCFINDER_LIB=%REPO_ROOT%\coincfinder\build\coincfinder_core.lib
set TDCBASE_LIB=%REPO_ROOT%\DLL_64bit\tdcbase.lib

if not exist "%VCPKG_ROOT%\vcpkg.exe" (
  echo vcpkg.exe not found at %VCPKG_ROOT%. Adjust VCPKG_ROOT in scripts\win-cmake.bat.
  exit /b 1
)

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
