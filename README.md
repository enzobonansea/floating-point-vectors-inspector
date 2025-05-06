# Usage
1. Download SPEC2017 on the root folder. The ISO must have the name `cpu2017-1.1.9.iso`.
2. Build container `docker build -t valgrind-memlog .`
3. Run container `docker run -it valgrind-memlog`
   
# About memcheck's customizations
- I added the files `rbtree.h`, `rbtree.c`, `memlog.h`, and `memlog.c`.
- These files implement the custom functionality for logging memory operations.
- I connected the original memcheck code with `memlog.h` to enable this functionality.
