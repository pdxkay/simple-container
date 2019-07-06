# Simple File Container

Here's what I think the format should look like at this point:

* header (10 bytes)
* metadata start position (8 bytes--ulong)
* spacer (2 bytes: \0\0)
* optionally: forward metadata for streaming purposes + spacer--requires remux on changes (unimplemented...)
* data streams (binary data streams 0+)
* container uuid (16 bytes)
* spacer (2 bytes)
* stream data (0+):
  * uuid (16 bytes)
  * spacer (2 bytes)
  * type id (2 bytes)
  * spacer (2 bytes)
  * encoding id (2 bytes)
  * spacer (2 bytes)
  * offset (8 bytes, ulong)
  * spacer (2 bytes)
  * length (8 bytes, ulong)
  * spacer (2 bytes)
  * crc32 (4 bytes)
  * spacer (2 bytes)
* spacer (2 bytes)
* stream metadata length (8 bytes)
* stream metadata (bson object: `Dict[uuid, Dict[str, Union[str, bool, int, float, list, dict]]]`)
* user metadata length (8 bytes)
* user metadata (bson object: `Dict[str, Union[str, bool, int, float, list, dict]]`)
