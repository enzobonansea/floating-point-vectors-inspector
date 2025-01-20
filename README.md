# Usage
1. Download SPEC2017 on the root folder. The ISO must have the name `cpu2017-1.1.9.iso`.
2. Build container `docker build -t valgrind-memlog .`
3. Run container `docker run -it valgrind-memlog`
   
# About memcheck's customizations
Searching for the keyword "memlog" into the "valgrind" folder, you will find every line of code added or modified by me in order to customize memcheck to print every store inside big enough buffers.
