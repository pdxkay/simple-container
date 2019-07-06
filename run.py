#!/usr/bin/env python

#from simplecontainer.tool import main
from simplecontainer.container import *


def test_create():
	cont = SimpleContainer("test.cont")
	stream = SimpleContainerStream()
	stream.type = streamtypes.localdata
	stream.data = b"hello woooooooooorld!!"
	stream.length = len(stream.data)
	cont.streams.append(stream)
	cont.write()


def test_read():
	cont = SimpleContainer.open("test.cont")
	print("filename", cont.filename)
	print("uuid", cont.uuid)
	print("webop", cont.webop)
	print("streams", cont.streams)
	for i in range(len(cont.streams)):
		stream = cont.streams[i]
		print(f"   stream {i}")
		print("   id", stream.id)
		print("   typeid", stream.typeid)
		print("   encodingid", stream.encodingid)
		print("   id", stream.id)
		print("   offset", stream.offset)
		print("   length", stream.length)
		print("   checksum", stream.checksum)
		print("   type", stream.type)
		print(stream.read())
		print()
	print("streammeta", cont.streammeta)
	print("metadata", cont.metadata)



if __name__ == "__main__":
	test_read()
	#main()
