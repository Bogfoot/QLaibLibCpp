set(QQL_SRC
    acquisition/MockBackend.cpp
    acquisition/BinReplayBackend.cpp
    metrics/Registry.cpp
    ui/MainWindow.cpp
    ${CMAKE_SOURCE_DIR}/../coincfinder/src/Coincidences.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../include/qlaib/ui/MainWindow.h
)

if(QQL_ENABLE_QUTAG)
    list(APPEND QQL_SRC acquisition/QuTAGBackend.cpp)
endif()

add_library(qlaibcpp STATIC ${QQL_SRC})

target_include_directories(qlaibcpp PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${CMAKE_SOURCE_DIR}/../coincfinder/include
)

if(QQL_ENABLE_QUTAG)
    target_compile_definitions(qlaibcpp PUBLIC QQL_ENABLE_QUTAG)
    target_include_directories(qlaibcpp PUBLIC ${CMAKE_SOURCE_DIR}/../QuTAGC/inc)
    # Look for libtdcbase (preferred in repo root/DLL_64bit/DLL_32bit or QuTAGC/lib)
    find_library(TDCBASE_LIB NAMES tdcbase libtdcbase tdcbase.lib PATHS
        ${CMAKE_SOURCE_DIR}/..                # repository root (dll/so beside checkout)
        ${CMAKE_SOURCE_DIR}/../DLL_64bit      # shipped 64-bit Windows DLLs/libs
        ${CMAKE_SOURCE_DIR}/../DLL_32bit      # shipped 32-bit Windows DLLs/libs
        ${CMAKE_SOURCE_DIR}/../QuTAGC/lib     # vendor lib dir now at repo root
        ${CMAKE_SOURCE_DIR}                   # legacy root
        /usr/lib /usr/local/lib /usr/lib/x86_64-linux-gnu
    )
    if(NOT TDCBASE_LIB)
        message(FATAL_ERROR "QQL_ENABLE_QUTAG=ON but libtdcbase not found. Place tdcbase.so/tdcbase.dll in repository root or DLL_64bit, or install the SDK.")
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

# If a prebuilt coincfinder core is available, link it; otherwise we compiled Coincidences.cpp above.
if(COINCFINDER_CORE)
    target_link_libraries(qlaibcpp PUBLIC ${COINCFINDER_CORE})
endif()
