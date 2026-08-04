# Local data directories

- `bronze/` contains immutable original source artifacts.
- `working/` contains temporary extracted and transformed files.
- `rejected/` contains optional rejected-record exports.

Dataset files are excluded from Git because they are large and may be
recreated or downloaded through the pipeline.