cmake_minimum_required(VERSION 3.22)
project(QLaibLibCpp VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

option(QQL_BUILD_GUI "Build the Qt GUI application" ON)
option(QQL_ENABLE_QUTAG "Enable real QuTAG backend (requires vendor SDK)" OFF)
option(QQL_ENABLE_CHARTS "Use Qt Charts for plotting (disable to build UI stub without charts)" ON)

add_subdirectory(src)
add_subdirectory(apps)

enable_testing()
add_subdirectory(tests EXCLUDE_FROM_ALL)
