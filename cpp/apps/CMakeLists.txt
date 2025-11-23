if(NOT COINCFINDER_CORE)
    find_library(COINCFINDER_CORE NAMES coincfinder_core libcoincfinder_core
        PATHS ${CMAKE_SOURCE_DIR}/coincfinder/build ${CMAKE_SOURCE_DIR}/coincfinder/lib)
endif()

if(QQL_BUILD_GUI)
    find_package(Qt6 REQUIRED COMPONENTS Widgets)
    set(QT_VERSION_MAJOR 6 CACHE STRING "Qt major version")
    add_executable(qlaib_gui qlaib_gui.cpp)
    target_link_libraries(qlaib_gui PRIVATE qlaibcpp Qt6::Widgets)
    if(COINCFINDER_CORE)
        target_link_libraries(qlaib_gui PRIVATE ${COINCFINDER_CORE})
    endif()
    if(QQL_ENABLE_CHARTS)
        target_compile_definitions(qlaib_gui PRIVATE QQL_ENABLE_CHARTS=1)
    endif()

    # Windows: deploy Qt runtime and vendor DLLs automatically after build.
    if(WIN32)
        option(QQL_AUTO_WDEPLOY "Run windeployqt and copy vendor DLLs after building qlaib_gui" ON)
        if(QQL_AUTO_WDEPLOY)
            # Locate windeployqt: prefer QT_ROOT, fall back to Qt6_DIR-derived bin.
            find_program(QQL_WDEPLOYQT_EXECUTABLE
                NAMES windeployqt.exe
                HINTS
                    $ENV{QT_ROOT}/bin
                    ${Qt6_DIR}/../../../bin
                    ${QT6_INSTALL_PREFIX}/bin
            )
            if(QQL_WDEPLOYQT_EXECUTABLE)
                add_custom_command(TARGET qlaib_gui POST_BUILD
                    COMMAND "${QQL_WDEPLOYQT_EXECUTABLE}" --release --compiler-runtime $<TARGET_FILE:qlaib_gui>
                    COMMENT "windeployqt qlaib_gui (Release)"
                )
            else()
                message(WARNING "windeployqt.exe not found; set QT_ROOT or QQL_WDEPLOYQT_EXECUTABLE to enable auto-deploy.")
            endif()

            # Copy vendor DLLs (quTAG/libusb/MinGW) shipped in DLL_64bit beside the exe.
            set(QQL_VENDOR_DLL_DIR "${CMAKE_SOURCE_DIR}/../DLL_64bit")
            if(EXISTS "${QQL_VENDOR_DLL_DIR}")
                file(GLOB QQL_VENDOR_DLLS "${QQL_VENDOR_DLL_DIR}/*.dll")
                if(QQL_VENDOR_DLLS)
                    add_custom_command(TARGET qlaib_gui POST_BUILD
                        COMMAND ${CMAKE_COMMAND} -E copy_if_different
                            ${QQL_VENDOR_DLLS}
                            $<TARGET_FILE_DIR:qlaib_gui>
                        COMMENT "Copying vendor DLLs from ${QQL_VENDOR_DLL_DIR}"
                    )
                endif()
            endif()
        endif()
    endif()
endif()

if(QQL_ENABLE_QUTAG)
    add_executable(qlaib_record_qudag qlaib_record_qudag.cpp)
    target_link_libraries(qlaib_record_qudag PRIVATE qlaibcpp)
    if(COINCFINDER_CORE)
        target_link_libraries(qlaib_record_qudag PRIVATE ${COINCFINDER_CORE})
    endif()
endif()
