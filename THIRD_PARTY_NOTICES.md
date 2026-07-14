# Third-party notices

## ECDICT

- Project: https://github.com/skywind3000/ECDICT
- Copyright: 2025 Linwei
- License: MIT License

ECDICT provides the English phonetic and lexical data used to build the local SQLite database. A copy of the license is included as `ECDICT-LICENSE.txt`.

The dictionary data itself is downloaded by the user from the pinned upstream commit and is not distributed in this repository.

## Kaikki English / Wiktextract / Wiktionary

- Data download: https://kaikki.org/dictionary/English/
- Extractor: https://github.com/tatuylonen/wiktextract
- Underlying project: https://www.wiktionary.org/
- Reuse terms: https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use

Kaikki English is an optional rolling JSONL download. The local downloader converts selected structured fields into SQLite. Neither the source JSONL nor the generated SQLite database is distributed in this repository. Users must follow the attribution and reuse terms that apply to the downloaded Wiktionary-derived data.

## Mozilla PDF.js

- Project: https://github.com/mozilla/pdf.js
- Packaged version: 6.1.200
- License: Apache License 2.0

PDF.js renders the extension's selectable PDF text layer. The pinned runtime, component assets, fonts, CMaps, WASM modules, ICC profiles, and license files are included under `extension/vendor/pdfjs/`.

## Network services

- Baidu Translate API: used only when ECDICT has no Chinese definition.
- Youdao Text Translation API: optional fallback and settings-page preview. Preview results are not written, persisted, or cached.
