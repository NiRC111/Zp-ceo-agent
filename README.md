# Government Quasi-Judicial AI System — Zilla Parishad, Chandrapur

A professional Streamlit app for drafting **quasi-judicial decisions** and **orders**.

## Features
- Case + Government GR (mandatory uploads)
- OCR (Marathi, Hindi, English)
- Clause highlighting in GR
- Draft orders in Marathi & English
- Built-in placeholder seal (can upload/override)

## Deploy on Vercel
1. Push this repo to GitHub.
2. In Vercel → New Project → Import the repo.
3. Vercel detects `Dockerfile` and builds automatically.
4. Access your deployed app at `<your-vercel-url>`.

## Security
- Runs as non-root user
- PII redaction for Aadhaar, PAN, mobile numbers in previews
- Sensitive mode toggle
- No persistent storage by default

> Draft orders are **advisory only**. Final review and signature by CEO/ZP authority required.
