# Google Autocomplete

The project returns up to five matching lines from a text corpus. Matching is
case-insensitive, ignores punctuation and repeated whitespace, and supports up
to one character correction according to the assignment scoring rules.

## Algorithm

The offline stage loads non-empty lines from the corpus and builds unigram,
bigram, and trigram indexes. The online stage normalizes user input, searches
exact candidates first, expands to fuzzy candidates only when necessary, then
ranks and returns the best five completions.

`src/matcher.py` scores one candidate sentence. `src/autocomplete.py` selects
candidates and orders the final results. `src/main.py` provides the CLI.

## Run tests

From the `project` directory:

```powershell
python -m unittest discover -s tests -v
```

## Protobuf search index

Offline search data can be serialized as a Protocol Buffers file so later runs
can restore the index instead of rebuilding it. The schema is
`proto/search_index.proto`, and its generated module is
`src/search_index_pb2.py`.

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

Regenerate the generated Python module after changing the schema:

```powershell
py -m grpc_tools.protoc -I proto --python_out=src proto/search_index.proto
```

`src/index_storage.py` calculates the archive SHA-256 hash and saves/loads the
sentences and N-gram indexes. Generated `*.pb` files are local artifacts and
are not committed.

## Performance notes

Corpus indexing is intentionally an offline cost. Very short queries can have
many candidates; the staged exact-before-fuzzy search and Top-5 selection limit
the online work.
