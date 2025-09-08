# Security Notes

- App runs as **non-root** user.
- OCR languages: English, Hindi, Marathi (Devanagari).
- Uploaded files processed in-memory (no permanent storage).
- Previews redact Aadhaar, PAN, mobile numbers.
- `.streamlit/config.toml` enables XSRF protection and SameSite cookies.
- Seal can be overridden via environment variable (`ZP_SEAL_DATA_URL`).
- Drafts are advisory only; final orders require human review.
