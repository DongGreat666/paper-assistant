# Security Policy

## Supported Deployment Model

Paper Assistant is currently designed for trusted, single-user local use.
Do not expose the application directly to the public internet or an untrusted
local network.

The current application does not provide production-ready:

- Login authentication or authorization.
- Per-user isolation for papers, conversations, annotations, and settings.
- Upload size limits, storage quotas, or strict file-content validation.
- Resource isolation for PDF parsing and other CPU, GPU, or memory-heavy tasks.
- SSRF protection for user-configurable model API base URLs.
- Encrypted or managed secret storage.
- Rate limiting, abuse prevention, or comprehensive security auditing.

## Sensitive Local Data

The following ignored files and directories may contain API keys, private
papers, generated content, or conversation history:

- `.env` and other `.env.*` files except `.env.example`.
- `data/`.
- `MyPapers/`.
- Legacy local paper directories such as `uploaded_files/` and `papers/`.
- `models/`.

Before publishing changes, run `git status` and confirm none of these local
artifacts are staged. Never include API keys in issues, logs, screenshots, or
commits. Rotate a key immediately if it may have been exposed.

## Public Deployment Requirements

Before making the service internet-facing or multi-user, implement and review:

- Authentication, authorization, and session security.
- Per-user storage and data-access boundaries.
- File size, type, quota, and malware controls.
- SSRF restrictions for outbound model requests.
- Sandboxed background jobs with CPU, memory, GPU, and timeout limits.
- Managed secret storage, HTTPS, rate limiting, and security logging.

## Reporting a Vulnerability

Do not open a public issue containing exploit details, private documents, or
API keys. Report vulnerabilities privately to `ydh2698277087@163.com` and
include the affected component, reproduction steps, impact, and suggested
mitigation.
