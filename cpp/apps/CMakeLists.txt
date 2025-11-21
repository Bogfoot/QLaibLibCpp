if(NOT COINCFINDER_CORE)
    find_library(COINCFINDER_CORE NAMES coincfinder_core libcoincfinder_core
        PATHS ${CMAKE_SOURCE_DIR}/coincfinder/build ${CMAKE_SOURCE_DIR}/coincfinder/lib)
endif()

if(QQL_BUILD_GUI)
    find_package(Qt6 REQUIRED COMPONENTS Widgets)
    set(QT_VERSION_MAJOR 6 CACHE STRING "Qt major version")
    add_executable(qlaib_gui qlaib_gui.cpp)
    target_link_libraries(qlaib_gui PRIVATE qlaibcpp Qt6::Widgets ${COINCFINDER_CORE})
    if(QQL_ENABLE_CHARTS)
        target_compile_definitions(qlaib_gui PRIVATE QQL_ENABLE_CHARTS=1)
    endif()
endif()

if(QQL_ENABLE_QUTAG)
    add_executable(qlaib_record_qudag qlaib_record_qudag.cpp)
    target_link_libraries(qlaib_record_qudag PRIVATE qlaibcpp ${COINCFINDER_CORE})
endif()
