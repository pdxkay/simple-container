# simple container format
# an easy to use file container

import bson
from uuid import UUID, uuid4
from binascii import crc32
from .exceptions import *
from .util import *

"""
Here's how a container is laid out:
* magic number
* spacer
* metadata start position (1 ulong, 2^64-1 bytes max)
* spacer
* optionally: forward metadata for streaming purposes + spacer--requires remux on changes
* data channels (binary streams)
* fixed container data
  * container uuid
  * binary stream
    * uuid
    * type id
    * encoding id
    * ranges (start + len)
    * crc32
* stream metadata (stream name-value pairs, for data on stream content)
* user metadata (generic name-value pairs)
"""


class SimpleContainerStream:
	def __init__(self, streamid=None, typeid=filetypes.binary, encodingid=encodingtypes.none, streamtype=streamtypes.filepart):
		# stream metadata
		self.id = uuid4() if streamid is None else streamid
		self.typeid = typeid
		self.encodingid = encodingid
		self.offset = -1
		self.length = -1
		self.checksum = 0
		
		# type of stream: is it data? is it part of a file?
		self.type = streamtype
		
		# if (whole or part of) a file/container:
		self.filename = None
		self.fileoffset = 0
		self.filelength = 0
		# if data: (should always be bytes)
		self.data = None
	
	def read(self):
		return b"".join(self.readchunked())
	
	def readchunked(self, chunksz=defaultchunksz, computecrc32=None):
		if computecrc32 is None:
			computecrc32 = self.checksum is None
		
		if self.type is streamtypes.localdata:
			if computecrc32:
				self.checksum = crc32(self.data)
			
			if len(self.data) != self.length:
				raise StreamError("localdata stream with incorrect length")
			
			yield self.data
		
		elif self.type is streamtypes.wholefile:
			with open(self.filename, "rb") as file:
				cs = 0
				for chunk in readchunks(file, chunksz=chunksz):
					if computecrc32:
						cs = crc32(chunk, cs)
					yield chunk
				
			if computecrc32:
				self.checksum = cs
		
		elif self.type is streamtypes.filepart:
			with open(self.filename, "rb") as file:
				if self.offset > 0:
					file.seek(self.offset)
				
				cs = 0
				
				if self.length <= 0:
					for chunk in readchunks(file, chunksz=chunksz):
						if computecrc32:
							cs = crc32(chunk, cs)
						yield chunk
				
				else:
					length = self.length
					while length > chunksz:
						chunk = file.read(chunksz)
						if computecrc32:
							cs = crc32(chunk, cs)
						yield chunk
						length -= chunksz
					
					if length > 0:
						chunk = file.read(length)
						if computecrc32:
							cs = crc32(chunk, cs)
						yield chunk
			
			if computecrc32:
				self.checksum = cs
	
	@classmethod
	def fromcontainer(cls, filename, buuid, btypeid, bencid, boffset, blen, bchecksum):
		stream = cls(UUID(bytes=buuid),
		             typeid=filetypes(bytes2int(btypeid)),
		             encodingid=encodingtypes(bytes2int(bencid)),
		             streamtype=streamtypes.filepart)
		stream.offset = bytes2int(boffset)
		stream.length = bytes2int(blen)
		stream.filename = filename
		stream.fileoffset = stream.offset  # same file
		stream.filelength = stream.length  # same file
		return stream


class SimpleContainer:
	@classmethod
	def open(cls, filename):
		with open(filename, "rb") as con:
			head = con.read(10)
			if head != header:
				raise ContainerError("Incorrect file format: malformed header")
			
			datapos = bytes2int(con.read(8))
			con.seek(con.tell() + datapos)
			conuuid = UUID(bytes=con.read(16))
			s = con.read(2)
			if s != nul:
				raise ContainerError("File format error: incorrect container uuid marker")
			
			streams = []
			
			while True:
				streamid = con.read(2)
				if streamid == nul:
					break  # end of stream list
				if streamid == b"":
					raise ContainerError("File format error: malformed stream list (reached eof)")
				
				streamid += con.read(14)
				stream = [streamid]
				if con.read(2) != nul:
					raise ContainerError("File format error: incorrect stream uuid marker")
				
				stream.append(con.read(2))  # stream type id
				if con.read(2) != nul:
					raise ContainerError("File format error: incorrect stream uuid marker")
				
				stream.append(con.read(2))  # stream encoding id
				if con.read(2) != nul:
					raise ContainerError("File format error: incorrect stream uuid marker")
				
				stream.append(con.read(8))  # stream offset
				if con.read(2) != nul:
					raise ContainerError("File format error: incorrect stream offset")
				
				stream.append(con.read(8))  # stream length
				if con.read(2) != nul:
					raise ContainerError("File format error: incorrect stream length")
				
				stream.append(con.read(4))  # stream crc
				if con.read(2) != nul:
					raise ContainerError("File format error: incorrect stream crc defition")
				
				streams.append(stream)
			
			streammetalen = bytes2int(con.read(8))
			streammetadata = bson.loads(con.read(streammetalen))
			
			metalen = bytes2int(con.read(8))
			metadata = bson.loads(con.read(metalen))
			
			container = cls(filename)
			container.uuid = conuuid
			container.streams = list(SimpleContainerStream.fromcontainer(filename, *s) for s in streams)
			container.steammeta = streammetadata
			container.metadata = metadata
			
			return container
	
	@classmethod
	def create(cls, filename):
		pass
	
	def __init__(self, filename):
		self.filename = filename
		self.streams = []
		self.streammeta = {}
		self.metadata = {}
		self.uuid = None
		self.webop = False
		
		# a temp file is necessary if you are remuxing or writing with streams that are in
		# the container that you're writing...otherwise it'll get truncated and the whole
		# thing will erupt in a fiery spectacle and you'll lose data
		self.usetemp = True
	
	def readstream(self, streamid):
		try:
			offset, length = next((s[1], s[2]) for s in self.streams if s[0] == streamid)
		except StopIteration:
			raise StreamError(f"Stream '{streamid}' not found in container.")
		
		with open(self.filename, "rb") as container:
			container.seek(offset)
			return container.read(length)
	
	def chunkedstream(self, streamid, chunksz=defaultchunksz):
		try:
			offset, length = next((s[1], s[2]) for s in self.streams if s[0] == streamid)
		except StopIteration:
			raise StreamError(f"Stream '{streamid}' not found in container.")
		
		with open(self.filename, "rb") as container:
			container.seek(offset)
			
			while chunksz > length:
				yield container.read(chunksz)
				length -= chunksz
			
			if length > 0:
				yield container.read(length)
	
	def savemeta(self):
		pass
	
	def write(self):
		fn = tempfn(self.filename) if self.usetemp else self.filename
		with open(fn, "wb") as container:
			# write header
			container.write(header)
			
			# write metadata start position
			streamlen = sum(s.length for s in self.streams)
			if streamlen > maxfs:
				raise ContainerError(f"File size {streamlen}b greater than maximum file size {maxfs}b.")
			container.write(int2bytes(streamlen, bytes=8))
			
			# write stream data, set stream obj offset and len in NEW container
			for stream in self.streams:
				streamstart = container.tell()
				for chunk in stream.readchunked(computecrc32=True):
					container.write(chunk)
				stream.offset = streamstart
				stream.length = container.tell() - streamstart
			
			# write container uuid
			if self.uuid is None:
				self.uuid = uuid4()
			container.write(self.uuid.bytes)
			container.write(nul)
			
			# write list of stream metadata
			for stream in self.streams:
				container.write(stream.id.bytes)
				container.write(nul)
				container.write(int2bytes(stream.typeid.value, bytes=2))
				container.write(nul)
				container.write(int2bytes(stream.encodingid.value, bytes=2))
				container.write(nul)
				container.write(int2bytes(stream.offset, bytes=8))
				container.write(nul)
				container.write(int2bytes(stream.length, bytes=8))
				container.write(nul)
				container.write(int2bytes(stream.checksum, bytes=4))
				container.write(nul)
			
			# write stream terminator nul
			container.write(nul)
			
			# convert stream metadata to bson
			streammeta = bson.dumps(self.streammeta)
			# write stream metadata bson length
			container.write(int2bytes(len(streammeta), bytes=8))
			# write stream metadata bson
			container.write(streammeta)
			
			# convert user metadata to bson
			meta = bson.dumps(self.metadata)
			# write user metadata bson length
			container.write(int2bytes(len(meta), bytes=8))
			# write user metadata bson
			container.write(meta)
