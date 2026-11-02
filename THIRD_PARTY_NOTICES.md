# Third-Party Notices

PocketCloud's own source is licensed under the MIT License in `LICENSE`. That license does not replace licenses of third-party packages or generated APK contents; each dependency retains its own terms. Recheck this list whenever a pin changes and include all relevant license/NOTICE texts in release artifacts.

| Component | Pinned version | License | Used for |
|---|---:|---|---|
| Starlette | 1.10.0 | BSD-3-Clause | Stage 1 ASGI API |
| Uvicorn | 0.54.0 | BSD-3-Clause | Stage 1 ASGI server |
| SQLAlchemy | 2.1.6 | MIT | SQLite models and transactions |
| AnyIO | 4.16.0 | MIT | Starlette async/thread support |
| Click | 8.5.0 | BSD-3-Clause | Uvicorn CLI dependency |
| h11 | 0.16.0 | MIT | Uvicorn HTTP/1.1 dependency |
| idna | 3.20 | BSD-3-Clause | AnyIO dependency |
| typing_extensions | 4.16.0 | PSF-2.0 | Python typing compatibility |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | Laptop TLS certificate and P-256 verification |
| cffi | 2.1.1 | MIT | cryptography dependency |
| pycparser | 3.12 | BSD-3-Clause | cffi dependency |
| qrcode | 8.2 | BSD-3-Clause | Terminal QR rendering |
| ZXing Android Embedded | 4.3.0 | Apache-2.0 | Native Android QR scanning |

License references: [Starlette](https://pypi.org/project/starlette/1.10.0/), [Uvicorn](https://pypi.org/project/uvicorn/0.54.0/), [SQLAlchemy](https://pypi.org/project/SQLAlchemy/2.1.6/), [cryptography](https://pypi.org/project/cryptography/50.0.2/), [cffi](https://pypi.org/project/cffi/2.1.1/), [pycparser](https://pypi.org/project/pycparser/3.12/), [qrcode source LICENSE](https://github.com/lincolnloop/python-qrcode/blob/main/LICENSE), and [ZXing Android Embedded](https://github.com/journeyapps/zxing-android-embedded). AndroidX and ZXing Core transitive artifacts are separately governed by their own Apache-2.0 notices. The final APK release process must produce a complete resolved dependency-license report, including those transitive artifacts.
