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

Visual Studio Community is installed, but its C++ compiler is not currently
installed. Add the **Desktop development with C++** workload in Visual Studio
Installer before compiling the native component. The workload should include:

- MSVC x64/x86 build tools
- Windows SDK
- CMake tools for Windows

The Protocol Buffer compiler/runtime will be configured after the native
compiler is available.

## Native prototype results

The first native implementation is in `native/`. It is a C++17 DLL loaded by
Python with `ctypes`, so the Python public API and CLI remain unchanged. Build
it from the `project` directory with:

```powershell
cmake -S native -B native/build -A x64
cmake --build native/build --config Release
cmake --build native/build --config Release --target RUN_TESTS
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
The C++ unit test and all 55 discoverable Python unit tests also pass.

In native mode Python keeps sentence metadata for the required output, but it
does not build duplicate Python N-gram indexes. The next step is Protocol
Buffers, allowing the C++ engine to load records directly and avoiding the
per-sentence Python-to-C++ initialization boundary.
