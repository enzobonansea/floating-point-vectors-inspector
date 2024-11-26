FROM ubuntu:20.04

# Prevent tzdata from prompting for user input
ENV DEBIAN_FRONTEND=noninteractive

# Install necessary tools and dependencies, including Valgrind
RUN apt-get update && apt-get install -y \
    build-essential wget gcc make tzdata \
    libncurses5-dev libncursesw5-dev autotools-dev automake autoconf libtool nano libc6-dbg

# Copy your plugin source code into the container
ADD valgrind /opt/valgrind

# Set up the working directory
WORKDIR /opt/valgrind
COPY alloc.c /tmp/alloc.c
RUN gcc -o /tmp/alloc /tmp/alloc.c

RUN sed -i -e 's/\r$//' autogen.sh
RUN find . -type f -exec sed -i -e 's/\r$//' {} \;
RUN ./autogen.sh
RUN ./configure --prefix=`pwd`/inst
RUN make install
CMD ["/bin/bash"]