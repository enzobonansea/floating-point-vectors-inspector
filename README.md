# Usage
1. Download SPEC2017 on the root folder. The ISO must have the name `cpu2017-1.1.9.iso`.
2. Build container `docker build -t valgrind-memlog .`
3. Run container `docker run -it valgrind-memlog`

## Test
```bash
inst/bin/valgrind --tool=memcheck /tmp/alloc  > /tmp/stdout.log 2>&1
grep '^ptr_f' /tmp/stdout.log
grep '0x4a5104' /tmp/stdout.log
```