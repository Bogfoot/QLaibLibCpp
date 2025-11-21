@echo off
setlocal enabledelayedexpansion

echo === QLaibLib CMake (Windows) ===

rem Resolve repo root (script dir one level up)
set REPO_ROOT=%~dp0..
for %%i in ("%REPO_ROOT%") do set REPO_ROOT=%%~fi

rem Set vcpkg root relative to repo (../vcpkg). Edit below if your clone is elsewhere.
for %%i in ("%REPO_ROOT%\..\vcpkg") do set VCPKG_ROOT=%%~fi

set BUILD_DIR=%REPO_ROOT%\cpp\build
set TOOLCHAIN=%VCPKG_ROOT%\scripts\buildsystems\vcpkg.cmake
rem Auto-find Qt6Config.cmake (manifest under repo, or global installed)
set QT_DIR=
for /r "%REPO_ROOT%\vcpkg_installed" %%f in (Qt6Config.cmake) do (
  if not defined QT_DIR set QT_DIR=%%~dpf
)
if not defined QT_DIR (
  for /r "%VCPKG_ROOT%\installed" %%f in (Qt6Config.cmake) do (
    if not defined QT_DIR set QT_DIR=%%~dpf
  )
)
if defined QT_DIR (
  for %%p in ("%QT_DIR%..") do set QT_PREFIX=%%~fp
) else (
  set QT_PREFIX=
)
set COINCFINDER_LIB=%REPO_ROOT%\coincfinder\build\coincfinder_core.lib
if not exist "%COINCFINDER_LIB%" set COINCFINDER_LIB=%REPO_ROOT%\coincfinder\build\libcoincfinder_core.lib
set TDCBASE_LIB=%REPO_ROOT%\DLL_64bit\tdcbase.lib
if not exist "%TDCBASE_LIB%" set TDCBASE_LIB=%REPO_ROOT%\DLL_64bit\TDCBASE.LIB

echo REPO_ROOT=%REPO_ROOT%
echo VCPKG_ROOT=%VCPKG_ROOT%

if not exist "%VCPKG_ROOT%\vcpkg.exe" (
  echo vcpkg.exe not found at %VCPKG_ROOT%. Edit scripts\win-cmake.bat to point to your vcpkg clone.
  exit /b 1
)
if not defined QT_DIR (
  echo Qt6Config.cmake not found in vcpkg_installed or vcpkg/installed. Run "vcpkg install --triplet x64-windows" from repo root to populate vcpkg_installed.
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

cmake -S %REPO_ROOT%\cpp -B %BUILD_DIR% -G "Ninja" ^
  -DCMAKE_TOOLCHAIN_FILE="%TOOLCHAIN%" ^
  -DCMAKE_PREFIX_PATH="%QT_PREFIX%" ^
  -DQt6_DIR="%QT_DIR%" ^
  -DQQL_BUILD_GUI=ON -DQQL_ENABLE_CHARTS=ON -DQQL_ENABLE_QUTAG=ON ^
  -DCOINCFINDER_CORE="%COINCFINDER_LIB%" ^
  -DTDCBASE_LIB="%TDCBASE_LIB%"
if errorlevel 1 exit /b 1

cmake --build %BUILD_DIR%
if errorlevel 1 exit /b 1

echo Done.
endlocal
