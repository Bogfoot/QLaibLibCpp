add_library(qlaib_test_support STATIC
    ../src/acquisition/MockBackend.cpp
)
target_include_directories(qlaib_test_support PUBLIC ../include)

add_executable(sample_tests sample_tests.cpp)
find_package(Qt6 REQUIRED COMPONENTS Core Test)
target_link_libraries(sample_tests PRIVATE qlaibcpp Qt6::Core Qt6::Test)

add_test(NAME sample_tests COMMAND sample_tests)
