from enum import IntEnum
from functools import partial

header = b"scf10\0\0\0\0\0"
nul = b"\0\0"
defaultchunksz = 40960
maxfs = 18446744073709551614
eca = partial(str.encode, encoding="ascii")
ecu = partial(str.encode, encoding="utf-8")
dca = partial(bytes.decode, encoding="ascii")


def tempfn(filename):
	return filename


def int2bytes(uint, bytes=8):
	return uint.to_bytes(bytes, byteorder="little", signed=False)


def bytes2int(bts):
	return int.from_bytes(bts, byteorder="little", signed=False)


def readchunks(file, chunksz=defaultchunksz):
	s = file.read(chunksz)
	while len(s) > 0:
		yield s
		s = file.read(chunksz)


class streamtypes(IntEnum):
	filepart = 0
	wholefile = 1
	localdata = 2


class filetypes(IntEnum):
	binary = 0


class encodingtypes(IntEnum):
	none = 0
