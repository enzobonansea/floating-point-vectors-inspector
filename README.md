# Usage
1. Build and run container with `docker build -t spec-valgrind . && docker run -it spec-valgrind`
2. The previous command will run a terminal inside the container. Now, you should run `inst/bin/valgrind --tool=memcheck /tmp/alloc`
3. Check mallocs with `nano /tmp/malloc.log` and save the addresses of interest
4. If `ADDRESS` is of our interest, we can check the intermediate writes with `grep -i 'ADDRESS' /tmp/heap_write.log`
