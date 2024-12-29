CC = mipsel-linux-gnu-gcc
CFLAGS = -Iinclude -march=mips1 -mfp32 -mno-abicalls -Wa,-mno-pdr -fno-pic -fno-ident -nostdlib -Wall -Wextra -Wpedantic
LD = mipsel-linux-gnu-ld
LDFLAGS = --oformat binary -T ldscripts/na.ld -s -static -nostdlib -z defs --unresolved-symbols=report-all

all: examples/room/ASDKX.RMD

examples/room/ASDKX.RMD: examples/room/room.o
	$(LD) $(LDFLAGS) -M -e room $^ -o $@

examples/room/room.o: examples/room/room.c
	$(CC) -c $(CFLAGS) $^ -o $@

clean:
	rm -f examples/room/ASDKX.RMD
	rm -f examples/room/room.o
