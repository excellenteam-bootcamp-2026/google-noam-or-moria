# Stage B: profiling and C++ upgrade

## Baseline

The Python implementation was measured on the supplied archive:

- 1,504 text files
- 2,583,987 non-empty sentences
- approximately 122 MB of source text
- approximately 2.54 GB of additional working-set memory after indexing

The reproducible profiler is `profiling/profile_stage_a.py`.

| Operation | Result |
|---|---:|
| Load all sentences | 15.267 s |
| Build the full Python index | 38.729 s |
| Profiled index build for 100,000 sentences | 3.169 s |
| Seven representative online queries under `cProfile` | 2.974 s |

The online profile processed about 3.46 million candidates for the short
queries. Most online time was spent selecting the alphabetically first exact
results (`heapq.nsmallest`) and repeatedly applying `casefold`. The matcher was
called only twice and was not the dominant cost after N-gram filtering.

## Selected C++ boundary

The component selected for the C++ rewrite is the **index and candidate-search
engine**, rather than the matcher alone.

The reason is that moving only `calculate_best_match` would cross the
Python/C++ boundary once per candidate while leaving the measured bottleneck
in Python. The C++ engine will instead own compact sentence IDs, posting lists,
and Top-K candidate selection. Python will remain responsible for the CLI and
for converting the final results to `AutoCompleteData`.

The intended boundary is:

1. Offline Python code prepares normalized sentence records.
2. Records are saved in Protocol Buffers.
3. C++ loads the Protocol Buffer data and builds/loads the compact index.
4. Python sends one normalized query to C++.
5. C++ returns only a small list of candidate IDs and scores.
6. Python formats and displays at most five results.

This boundary minimizes language-crossing overhead and prepares the project
for the large-data requirement in the next Stage B tasks.

## Environment requirement

Visual Studio Community with the **Desktop development with C++** workload is
required. The workload should include:

- MSVC x64/x86 build tools
- Windows SDK
- CMake tools for Windows

The current development machine uses MSVC 19.51 and Windows SDK 10.0.26100.

## Native prototype results

The first native implementation is in `native/`. It is a C++17 DLL loaded by
Python with `ctypes`, so the Python public API and CLI remain unchanged.
Install dependencies into an ASCII-only cache path (some Windows linker tools
do not handle the Hebrew parent directory correctly), then build:

```powershell
vcpkg install --x-manifest-root=. --x-install-root=C:\vcpkg-google
cmake -S native -B native/build-protobuf -A x64 `
  -DCMAKE_PREFIX_PATH=C:\vcpkg-google\x64-windows
cmake --build native/build-protobuf --config Release
cmake --build native/build-protobuf --config Release --target RUN_TESTS
```

Run the CLI with the native index:

```powershell
python -m src.main C:\path\to\corpus --native
```

The reproducible comparison tool is `profiling/compare_native.py`. On a sample
of 100,000 real sentences, the first comparison produced:

| Operation | Python | C++ | Improvement |
|---|---:|---:|---:|
| Build index | 1.075 s | 0.708 s | 1.5x |
| Query `a` | 18.240 ms | 6.333 ms | 2.9x |
| Query `th` | 10.926 ms | 3.414 ms | 3.2x |
| Query `the` | 10.200 ms | 3.282 ms | 3.1x |
| Ten-word exact query | 0.255 ms | 0.092 ms | 2.8x |
| Ten-word query with an early typo | 0.142 ms | 0.061 ms | 2.3x |

Every native result was identical to the Python result in this comparison.
The C++ unit test and all Python unit tests also pass.

In native text mode Python keeps sentence metadata for the required output,
but it does not build duplicate Python N-gram indexes.

## Protocol Buffers and full-corpus conversion

`proto/corpus.proto` defines a versioned `CorpusChunk` containing repeated
`SentenceRecord` values. Every record preserves the ID, original text,
normalized text, source path, and line offset. `src/protobuf_store.py` converts
the text corpus as a stream and defaults to 50,000 records per file.

```powershell
python -m src.protobuf_store C:\path\to\corpus C:\path\to\new-output
```

The supplied full archive was converted and read back successfully:

| Measurement | Result |
|---|---:|
| Source sentences | 2,583,987 |
| Protobuf chunks | 52 |
| Total Protobuf size | 565.2 MiB |
| Streaming conversion time | 21.096 s |
| Full sequential read time | 10.180 s |
| First / last sentence ID | 0 / 2,583,986 |

The chunk design avoids the Protocol Buffer size limit of one enormous
message, permits sequential loading, and bounds temporary conversion memory.
All 79 `pytest` tests pass, including CLI behavior, multi-chunk round-trip,
overwrite-protection, and direct C++ loading tests.

### Direct C++ loading

The final native path does not load text files or construct Python indexes.
After conversion, run:

```powershell
python -m src.main --protobuf C:\path\to\protobuf-chunks
```

The optimized schema stores one case-folded sentence for deterministic sorting
instead of duplicating a compound key. This reduced an experimental 938.6 MiB
encoding to 565.2 MiB.

The direct C++ benchmark (`profiling/benchmark_protobuf_native.py`) produced:

| Measurement | Python baseline | C++ + Protobuf | Improvement |
|---|---:|---:|---:|
| Load and index | 52.242 s | 21.918 s | 2.4x |
| Added working-set memory | 2,539.6 MiB | 2,119.8 MiB | 16.5% less |
| Query `a` | 615.989 ms | 218.187 ms | 2.8x |
| Query `th` | 367.308 ms | 142.196 ms | 2.6x |
| Query `the` | 309.615 ms | 120.271 ms | 2.6x |
| Ten-word exact query | 22.127 ms | 7.186 ms | 3.1x |
| Early typo | 17.267 ms | 4.052 ms | 4.3x |
| Final typo | 21.747 ms | 4.545 ms | 4.8x |
| Absent long query | 5.444 ms | 0.944 ms | 5.8x |

C++ validates the format version and sequential chunk numbers while reading,
builds the indexes directly, and retains all metadata required for the final
`AutoCompleteData`. Python receives only candidate records needed for scoring
and display.
