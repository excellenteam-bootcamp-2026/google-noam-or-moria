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
