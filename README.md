# YT Downloader

A compact Windows desktop app for downloading YouTube videos or audio with a dark, minimal interface. The app includes a video preview, format selection, download progress, and download history.

## Run from source

Requirements: Python 3.10 or newer, FFmpeg, and Deno.

```powershell
python -m pip install -r requirements.txt
python youtube_downloader.py
```

The bundled runtime components and their notices are described in [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt). YouTube and other sites may change their behavior; keep yt-dlp up to date.

## Project status

This is an MVP. The source is published for review, but the project license has not yet been selected. Until a license is added, the source is not granted for reuse or redistribution.

The standalone executable is not included in this repository. It is larger than GitHub's standard file limit and bundles a GPLv3 FFmpeg build; binary redistribution is deferred until the corresponding-source and licensing materials are prepared.

## Responsible use

Use this software only for content you have the right to download and in accordance with the relevant site's terms.
