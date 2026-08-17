# M1.47 C/Python Buffer Contract

Foreign calls use pointer-plus-length byte views with explicit status and
closed S3 error payloads. Borrowed views end at call return. Retained data is
copied into S3-owned storage. UTF-8 strings are length-delimited; bytes and
slices do not imply ownership transfer. Every acquired Python buffer is
released exactly once.
