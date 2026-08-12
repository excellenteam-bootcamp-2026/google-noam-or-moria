# Google Autocomplete

## Protobuf search index

The offline search data can be serialized as a binary Protocol Buffers file.
The schema is stored in `proto/search_index.proto`, and the generated Python
module is committed as `src/search_index_pb2.py`.

Install the dependencies:

```powershell
py -m pip install -r requirements.txt
```

Regenerate the Python module after changing the schema:

```powershell
py -m grpc_tools.protoc -I proto --python_out=src proto/search_index.proto
```

`src/index_storage.py` provides:

- `file_hash` for calculating the SHA-256 hash of the source archive.
- `save_search_data` for atomically writing all sentences and N-gram indexes.
- `load_search_data` for restoring `SearchData` and its archive hash.

Generated `*.pb` index files are local build artifacts and are not committed.
