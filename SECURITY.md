# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x   | ✅ |

## Reporting a vulnerability

Please do **not** report security vulnerabilities through public GitHub issues.

Instead, use GitHub's private vulnerability reporting:
**Security → Report a vulnerability** on this repository
(https://github.com/sunnydachs/demo-video-generator/security/advisories/new).

You can expect an initial response within 7 days. Please include:

- A description of the issue and its impact
- Steps to reproduce (a manifest / command line is ideal)
- Any known workarounds

## Scope notes

`demo-video-generator` is a local CLI tool. It reads a manifest file and
screenshots from disk, calls a local VOICEVOX engine (default
`http://127.0.0.1:50021`), and shells out to `ffmpeg`. Areas of particular
interest:

- Path handling of manifest-provided `image` paths
- ffmpeg command construction
- Anything that could make the tool reach unintended network endpoints
