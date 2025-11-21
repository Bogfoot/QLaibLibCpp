set(QQL_SRC
    acquisition/MockBackend.cpp
    acquisition/BinReplayBackend.cpp
    metrics/Registry.cpp
    ui/MainWindow.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../include/qlaib/ui/MainWindow.h
)

if(QQL_ENABLE_QUTAG)
    list(APPEND QQL_SRC acquisition/QuTAGBackend.cpp)
endif()

add_library(qlaibcpp STATIC ${QQL_SRC})

target_include_directories(qlaibcpp PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${CMAKE_SOURCE_DIR}/coincfinder/include
)

if(QQL_ENABLE_QUTAG)
    target_compile_definitions(qlaibcpp PUBLIC QQL_ENABLE_QUTAG)
    target_include_directories(qlaibcpp PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../QuTAGC/inc)
    # Look for libtdcbase (shipped in repo root or system)
    find_library(TDCBASE_LIB NAMES tdcbase libtdcbase PATHS
        ${CMAKE_SOURCE_DIR}
        ${CMAKE_SOURCE_DIR}/..
        /usr/lib /usr/local/lib /usr/lib/x86_64-linux-gnu
    )
    if(NOT TDCBASE_LIB)
        message(FATAL_ERROR "QQL_ENABLE_QUTAG=ON but libtdcbase not found. Place libtdcbase.so in repo root or install SDK.")
    endif()
    target_link_libraries(qlaibcpp PUBLIC ${TDCBASE_LIB})
endif()

find_package(Qt6 REQUIRED COMPONENTS Core Widgets)
set(QT_VERSION_MAJOR 6 CACHE STRING "Qt major version")

if(QQL_ENABLE_CHARTS)
    find_package(Qt6 COMPONENTS Charts)
    if(NOT Qt6Charts_FOUND)
        message(WARNING "Qt Charts not found; disabling charts UI. Install qt6-charts-dev or set QQL_ENABLE_CHARTS=OFF.")
        set(QQL_ENABLE_CHARTS OFF CACHE BOOL "Charts disabled" FORCE)
    endif()
endif()

target_link_libraries(qlaibcpp
    PUBLIC Qt6::Core Qt6::Widgets
)

if(QQL_ENABLE_CHARTS)
    target_link_libraries(qlaibcpp PUBLIC Qt6::Charts)
    target_compile_definitions(qlaibcpp PUBLIC QQL_ENABLE_CHARTS=1)
endif()

# Link coincfinder core (static lib built under coincfinder/build). Prefer in-repo build over system installs.
set(_cf_local "${CMAKE_SOURCE_DIR}/coincfinder/build/libcoincfinder_core.a")
if(NOT COINCFINDER_CORE AND EXISTS ${_cf_local})
    set(COINCFINDER_CORE ${_cf_local} CACHE FILEPATH "coincfinder core static lib (local build)" FORCE)
endif()

if(NOT COINCFINDER_CORE)
    find_library(COINCFINDER_CORE NAMES coincfinder_core libcoincfinder_core
        HINTS ${CMAKE_SOURCE_DIR}/coincfinder/build
        NO_DEFAULT_PATH)
    if(NOT COINCFINDER_CORE)
        find_library(COINCFINDER_CORE NAMES coincfinder_core libcoincfinder_core
            PATHS ${CMAKE_SOURCE_DIR}/coincfinder/build ${CMAKE_SOURCE_DIR}/coincfinder/lib /usr/local/lib /usr/lib)
    endif()
    if(COINCFINDER_CORE)
        set(COINCFINDER_CORE ${COINCFINDER_CORE} CACHE FILEPATH "coincfinder core static lib")
    endif()
endif()

if(COINCFINDER_CORE)
    target_link_libraries(qlaibcpp PUBLIC ${COINCFINDER_CORE})
else()
    message(WARNING "coincfinder core library not found. Build coincfinder/build/libcoincfinder_core.a to enable replay.")
endif()
