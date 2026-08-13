# Google Autocomplete

Autocomplete for a large text corpus. The program returns up to five source
lines, including their source path, line number, and score. Search is
case-insensitive, treats punctuation as word separators, and supports one
character correction.

## Architecture

The project has one persistent data flow:

```text
text corpus -> chunked Protobuf corpus -> native C++ index cache -> search
```

1. The text corpus is converted once to bounded `corpus-*.pb` Protobuf chunks.
2. On the first native run, C++ reads those chunks, builds the unigram, bigram,
   and trigram indexes, then saves a native cache beside them.
3. On later runs, C++ validates the chunk fingerprint and loads the fully built
   index cache directly. It does not rebuild Python or C++ N-gram dictionaries.
4. Python keeps the CLI, normalization, one-edit scoring, and public
   `get_best_k_completions(prefix)` API. C++ owns sentence storage, candidate
   indexes, and exact Top-K selection.

The cache defaults to `.autocomplete-native-index.cache` inside the Protobuf
directory. It is local build output and is intentionally ignored by Git. Use
`--cache PATH` to place it elsewhere. If a chunk changes, the fingerprint no
longer matches and the index is rebuilt safely.

## Requirements

- Python 3.10+
- Visual Studio Community with **Desktop development with C++**
- MSVC, Windows SDK, CMake, and vcpkg

Install Python dependencies from `project`:

```powershell
python -m pip install -r requirements-dev.txt
```

Build the C++ library and run C++ tests:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_native.ps1
```

## Convert the corpus once

```powershell
python -m src.protobuf_store `
  "C:\path\to\corpus" `
  "C:\path\to\protobuf-output"
```

The conversion creates numbered chunks of 50,000 sentences by default.

## Run

```powershell
python -m src.main --protobuf "C:\path\to\protobuf-output"
```

The first run creates the native cache. Later runs reuse it automatically.

- Enter searches using the text accumulated so far.
- `#` resets the query.
- `Ctrl+C` exits.

## Run the personalized product

Install the optional official Google Gemini SDK and configure the API key:

```powershell
python -m pip install -r requirements-stage-c.txt
$env:GEMINI_API_KEY = "your-Google-AI-Studio-key"
```

Run the complete product on the Protobuf corpus and persistent native index:

```powershell
python -m src.main `
  --protobuf "C:\path\to\protobuf-output" `
  --personalized `
  --user-id "noam"
```

The user flow is:

1. Type text and press Enter to get up to five suggestions.
2. Continue typing and press Enter again, or enter `#` to reset.
3. Enter `:select 2` to select suggestion 2 and save that explicit choice.
4. Future searches use the recent selected sentences for personalized ranking.

The original match score always remains the primary ranking criterion. Gemini
only changes the order of results that have the same score, so personalization
cannot replace a more relevant exact result with a weaker fuzzy result.

The local demonstration history is stored in `.autocomplete-history.json` and
is ignored by Git. The file keeps at most 100 entries per user. Gemini receives
only recent queries, selected sentence text, and a bounded candidate pool; it
does not receive user IDs, file paths, offsets, or the whole corpus.

If the SDK, API key, network, quota, or Gemini response is unavailable, the
product remains operational and returns the original non-personalized top five.
This fallback is intentional and covered by tests.

## Tests

```powershell
python -m pytest -q
```

`STAGE_B.md` contains profiling methodology and benchmark results.
`STAGE_C.md` contains the three Google-only personalization approaches, cost
model, privacy/reliability boundary, and the Gemini reranking POC.
