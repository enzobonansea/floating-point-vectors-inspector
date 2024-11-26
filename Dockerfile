# Setup
FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y build-essential wget gcc make libncurses5-dev libncursesw5-dev autotools-dev automake autoconf libtool nano libc6-dbg grep blender alsa-utils

# Prepare Valgrind source
ADD valgrind /opt/valgrind
WORKDIR /opt/valgrind

# Normalize line endings
RUN sed -i -e 's/\r$//' autogen.sh && find . -type f -exec sed -i -e 's/\r$//' {} \;

# Configure and build Valgrind
RUN ./autogen.sh && ./configure --prefix=`pwd`/inst && make install

# Test programs
COPY alloc.c /tmp/alloc.c
RUN gcc -o /tmp/alloc /tmp/alloc.c
COPY example.py /tmp/example.py

# Init container
COPY menu.sh /usr/local/bin/menu.sh
RUN chmod +x /usr/local/bin/menu.sh
CMD ["/usr/local/bin/menu.sh"]