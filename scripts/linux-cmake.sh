#!/usr/bin/env bash
set -euo pipefail

# Adjust these as needed
BUILD_DIR="cpp/build"

# Locate Qt6 automatically (no vcpkg dependency)
QT_PREFIX="${QT_PREFIX:-}"
QT_DIR="${Qt6_DIR:-}"
if [[ -z "$QT_DIR" ]]; then
  candidates=(
    "${QT_PREFIX:+$QT_PREFIX}/cmake/Qt6"
    /usr/lib/x86_64-linux-gnu/cmake/Qt6
    /usr/lib64/cmake/Qt6
    /usr/lib/qt6/cmake
    /usr/local/lib/cmake/Qt6
    /opt/Qt/*/gcc_64/lib/cmake/Qt6
    /opt/Qt6*/lib/cmake/Qt6
  )
  for c in "${candidates[@]}"; do
    if compgen -G "$c/Qt6Config.cmake" > /dev/null; then
      QT_DIR=$(ls -d $c 2>/dev/null | head -n1)
      QT_PREFIX=$(cd "$QT_DIR/.." && pwd)
      break
    fi
  done
fi

if [[ -z "$QT_DIR" ]] || [[ ! -f "$QT_DIR/Qt6Config.cmake" ]]; then
  echo "Qt6Config.cmake not found. Set QT_PREFIX or Qt6_DIR env." >&2
  exit 1
fi

COINCFINDER_LIB="$(pwd)/coincfinder/build/libcoincfinder_core.a"
TDCBASE_LIB="$(pwd)/libtdcbase.so"

if [[ ! -f "$COINCFINDER_LIB" ]]; then
  echo "Missing coincfinder_core.a at $COINCFINDER_LIB" >&2
  exit 1
fi
if [[ ! -f "$TDCBASE_LIB" ]]; then
  echo "Missing libtdcbase.so at $TDCBASE_LIB" >&2
  exit 1
fi

cmake -S cpp -B "$BUILD_DIR" -G Ninja \
  -DCMAKE_PREFIX_PATH="$QT_PREFIX" \
  -DQt6_DIR="$QT_DIR" \
  -DQQL_BUILD_GUI=ON -DQQL_ENABLE_CHARTS=ON -DQQL_ENABLE_QUTAG=ON \
  -DCOINCFINDER_CORE="$COINCFINDER_LIB" \
  -DTDCBASE_LIB="$TDCBASE_LIB"

cmake --build "$BUILD_DIR"
