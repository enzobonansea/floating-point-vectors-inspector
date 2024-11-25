# Usage
1. Build and run container with `docker build -t spec-valgrind . && docker run -it spec-valgrind`
2. The previous command will run a terminal inside the container. Now, you should run `inst/bin/valgrind --tool=memcheck /tmp/alloc`