# cmake_minimum_required(VERSION <specify CMake version here>)
project(csurm)

set(CMAKE_CXX_STANDARD 14)

find_package(PythonLibs REQUIRED)
include_directories(${PYTHON_INCLUDE_DIRS})

add_executable(csurm main.cpp Scheduler.h Scheduler.cpp Protocol.cpp Protocol.h)
target_link_libraries(csurm ${PYTHON_LIBRARIES})
