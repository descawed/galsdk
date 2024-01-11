CC = mipsel-linux-gnu-gcc
CFLAGS = -Iinclude -IPSn00bSDK/libpsn00b/include -march=mips1 -mfp32 -mno-abicalls -fno-pic -nostdlib -Wall -Wpedantic
LD = mipsel-linux-gnu-ld
LDFLAGS = --oformat binary -T ldscripts/na.ld -nostdlib

all: examples/room/ASDKX.RMD

examples/room/ASDKX.RMD: examples/room/room.o
	$(LD) $(LDFLAGS) -M -e room $^ -o $@

examples/room/room.o: examples/room/room.c
	$(CC) -c $(CFLAGS) $^ -o $@

clean:
	rm -f examples/room/ASDKX.RMD
	rm -f examples/room/room.o
