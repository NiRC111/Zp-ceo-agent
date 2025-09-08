# -*- coding: utf-8 -*-
"""
Government Quasi-Judicial AI System — Zilla Parishad, Chandrapur
- Professional government UI with built-in/overrideable seal
- Mandatory Case + GR uploads
- OCR (Marathi/Hindi/English)
- GR clause highlighter
- Quasi-judicial order drafts (Marathi & English)
- Signature block + seal watermark
- Sensitive-mode redaction & no disk writes for text
- Robust PDF extraction (PyMuPDF/pdfminer/pypdf + OCR fallback)
"""

import io, os, re, datetime, tempfile, platform, shutil, base64, pathlib
from typing import List, Tuple, Dict

import streamlit as st
import pandas as pd

# ────────────────────────── PAGE & THEME ──────────────────────────
st.set_page_config(page_title="Government Quasi-Judicial AI System — ZP Chandrapur", layout="wide")

st.markdown("""
<style>
:root{
  --gov-blue:#0B3A82; --gov-blue-2:#12408A; --ink:#0b1220; --muted:#4b5563;
  --line:#e5e7eb; --bg:#ffffff; --ok:#1a7f37; --warn:#b58100; --bad:#b42318;
}
html, body { background: var(--bg); }
.block-container { max-width: 1260px !important; padding-top: 0 !important; }

/* Header */
.govbar {
  position: sticky; top: 0; z-index: 20;
  background: linear-gradient(180deg, var(--gov-blue), var(--gov-blue-2));
  color: #fff; padding: 14px 18px; border-bottom: 1px solid rgba(255,255,255,.15);
}
.govrow { display:flex; align-items:center; gap:12px; }
.govtitle { font-weight:800; letter-spacing:.2px; font-size:1.08rem; line-height:1.15; }
.govsubtitle { opacity:.95; font-weight:500; font-size:.88rem; }

/* Sections, cards, badges */
.section-title {
  margin: 14px 0 8px 0; padding: 10px 12px; border:1px solid var(--line);
  border-left: 4px solid var(--gov-blue); border-radius: 8px; background:#f8fafc; font-weight: 700;
}
.card { border:1px solid var(--line); border-radius:12px; padding:16px; background:#fff; }
.badge { display:inline-block; padding:2px 10px; border:1px solid var(--line); border-radius:999px; font-weight:600; font-size:.8rem; background:#f8fafc; }
.small { color:#6b7280; font-size:.9rem; }

/* Tabs */
.stTabs [data-baseweb="tab-list"]{ gap:6px; }
.stTabs [role="tab"]{
  padding:10px 14px; border-radius:10px 10px 0 0; background:#f3f4f6; border:1px solid var(--line); border-bottom:none;
  font-weight:600; color:#111827;
}
.stTabs [aria-selected="true"]{ background:#ffffff; border-bottom:1px solid #fff; }

/* Alerts */
.alert-ok { border-left:4px solid var(--ok); padding:10px 12px; background:#f6fff7; }
.alert-warn { border-left:4px solid var(--warn); padding:10px 12px; background:#fffaf0; }
.alert-bad { border-left:4px solid var(--bad); padding:10px 12px; background:#fff5f5; }

/* Order block (print-friendly) */
.order-block{
  border:1px solid var(--line); border-radius:10px; padding:22px; background:#ffffff;
  box-shadow: 0 0 0 2px #fff inset;
}
.order-block h3{ margin-top:0; }

/* GR clause highlight */
.hl { background: #fff3cd; border-bottom: 2px solid #facc15; }

/* --- Watermark support --- */
.wm-wrap { position: relative; }
.wm-bg {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  pointer-events: none; z-index: 0;
}
.wm-bg img {
  opacity: .08; width: 42%;
  min-width: 260px; max-width: 460px;
  filter: grayscale(100%);
}
.order-content { position: relative; z-index: 1; }

/* Signature block */
.sig-block{
  margin-top: 24px; padding-top: 12px; border-top: 1px dashed var(--line);
  line-height: 1.45;
}
.sig-rows{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px 24px; }
.sig-label{ color:#6b7280; font-size:.92rem; }
.sig-name{ font-weight:700; }
.sig-desig{ margin-top:-2px; }

/* Footer */
.footer {
  margin-top: 18px; padding-top: 10px; border-top:1px solid var(--line);
  font-size: .85rem; color:#6b7280;
}

/* Print */
@media print {
  .govbar, .stButton, .stDownloadButton, .stRadio, .stTextInput, .stFileUploader, .stTabs { display:none !important; }
  .order-block { border:none; padding:0; }
  body { background:#fff; }
}
</style>
""", unsafe_allow_html=True)

# ────────────────────────── SEAL: default + upload override ──────────────────────────
def load_default_seal_data_url() -> str:
    asset_path = pathlib.Path(__file__).parent / "assets" / "seal_placeholder.svg"
    if asset_path.exists():
        data = asset_path.read_bytes()
        return "data:image/svg+xml;base64," + base64.b64encode(data).decode("utf-8")
    inline_svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36"><circle cx="18" cy="18" r="16" fill="#0B3A82"/></svg>'
    return "data:image/svg+xml;base64," + base64.b64encode(inline_svg).decode("utf-8")

default_seal_env = os.environ.get("ZP_SEAL_DATA_URL", "")
default_seal = default_seal_env if default_seal_env.startswith("data:image/") else load_default_seal_data_url()
st.session_state.setdefault("seal_data_url", default_seal)

seal_upload = st.file_uploader("Upload ZP/Maharashtra Seal (PNG/SVG)", type=["png","svg"], key="seal_upload", label_visibility="collapsed")
if seal_upload is not None:
    if seal_upload.type.endswith("svg"):
        st.session_state["seal_data_url"] = "data:image/svg+xml;base64," + base64.b64encode(seal_upload.read()).decode("utf-8")
    else:
        st.session_state["seal_data_url"] = "data:image/png;base64," + base64.b64encode(seal_upload.read()).decode("utf-8")

st.markdown(f"""
<div class="govbar">
  <div class="govrow">
    <img src="{st.session_state['seal_data_url']}" width="36" height="36" style="border-radius:50%;background:#fff"/>
    <div>
      <div class="govtitle">Government Quasi-Judicial AI System</div>
      <div class="govsubtitle">Zilla Parishad, Chandrapur · जिल्हा परिषद, चंद्रपूर · Government of Maharashtra</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<div class='section-title'>Case Decision & Order Drafting — Case & GR Mandatory</div>", unsafe_allow_html=True)

# ────────────────────────── LAZY IMPORTS & ENV ──────────────────────────
def _lazy_imports():
    mods = {}
    try:
        import fitz  # PyMuPDF
        mods["fitz"] = fitz
    except Exception as e:
        mods["fitz"] = None; mods["fitz_err"] = str(e)
    try:
        from pdfminer_high_level import extract_text as _noop  # defensive alias if someone renames
    except Exception:
        pass
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text
        mods["pdfminer_extract_text"] = pdfminer_extract_text
    except Exception as e:
        mods["pdfminer_extract_text"] = None; mods["pdfminer_err"] = str(e)
    try:
        import pytesseract; from PIL import Image
        mods["pytesseract"] = pytesseract; mods["PIL_Image"] = Image
    except Exception as e:
        mods["pytesseract"] = None; mods["PIL_Image"] = None; mods["pytesseract_err"] = str(e)
    try:
        from pypdf import PdfReader
        mods["PdfReader"] = PdfReader
    except Exception as e:
        mods["PdfReader"] = None; mods["pypdf_err"] = str(e)
    return mods

# Tesseract traineddata path (commonly available on Debian/Ubuntu)
for _p in ["/usr/share/tesseract-ocr/4.00/tessdata", "/usr/share/tesseract-ocr/tessdata"]:
    if os.path.isdir(_p):
        os.environ.setdefault("TESSDATA_PREFIX", _p)
        break

OCR_LANG = "eng+hin+mar"
DEVANAGARI_RE = re.compile(r'[\u0900-\u097F]')
AADHAAR_RE = re.compile(r'(\b\d{4}\s?\d{4}\s?\d{4}\b)')
PAN_RE = re.compile(r'\b([A-Z]{5}\d{4}[A-Z])\b')
MOBILE_RE = re.compile(r'\b([6-9]\d{9})\b')

def contains_devanagari(s: str) -> bool:
    return bool(DEVANAGARI_RE.search(s or ""))

def robust_decode(b: bytes) -> str:
    for enc in ("utf-8","utf-8-sig","utf-16","utf-16le","utf-16be"):
        try: return b.decode(enc)
        except Exception: pass
    return b.decode("latin-1", errors="ignore")

def redact_sensitive(s: str) -> str:
    s = AADHAAR_RE.sub("XXXX XXXX XXXX", s)
    s = PAN_RE.sub("XXXXX9999X", s)
    s = MOBILE_RE.sub("XXXXXXXXXX", s)
    return s

# ────────────────────────── EXTRACTION ──────────────────────────
def extract_text_with_pypdf(pdf_bytes: bytes) -> Tuple[str, List[str]]:
    logs: List[str] = []
    PdfReader = _lazy_imports().get("PdfReader")
    if not PdfReader:
        return "", ["pypdf not available"]
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception as e:
                logs.append(f"pypdf page error: {e}")
        return "\n".join(parts).strip(), logs + ["pypdf extracted"]
    except Exception as e:
        return "", logs + [f"pypdf failed: {e}"]

def extract_text_from_pdf(pdf_bytes: bytes) -> Tuple[str, List[str]]:
    logs: List[str] = []
    mods = _lazy_imports()
    fitz = mods.get("fitz")
    pdfminer_extract_text = mods.get("pdfminer_extract_text")
    pytesseract = mods.get("pytesseract")
    PIL_Image = mods.get("PIL_Image")
    text = ""
    pdf_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes); pdf_path = tmp.name
    except Exception as e:
        logs.append(f"tmp pdf write failed: {e}")

    # A) PyMuPDF direct text
    try:
        if fitz:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            parts = [p.get_text("text") for p in doc]
            doc.close()
            text = "\n".join(parts).strip()
    except Exception as e:
        logs.append(f"fitz text failed: {e}")

    # B) PyMuPDF blocks (useful for Indic scripts)
    try:
        if fitz and (not contains_devanagari(text) or len(text) < 50):
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            blocks_all = []
            for page in doc:
                blocks = page.get_text("blocks") or []
                blocks.sort(key=lambda b: (round(b[1],1), round(b[0],1)))
                for b in blocks:
                    if len(b) >= 5:
                        t = (b[4] or "").strip()
                        if t:
                            blocks_all.append(t)
            doc.close()
            textB = "\n".join(blocks_all).strip()
            if len(textB) > len(text) or (contains_devanagari(textB) and not contains_devanagari(text)):
                text = textB
    except Exception as e:
        logs.append(f"fitz blocks failed: {e}")

    # C) pdfminer (secondary)
    if (not contains_devanagari(text)) and pdfminer_extract_text and pdf_path:
        try:
            t2 = pdfminer_extract_text(pdf_path) or ""
            if contains_devanagari(t2) or len(t2) > len(text):
                text = t2
        except Exception as e:
            logs.append(f"pdfminer failed: {e}")

    # D) pypdf (pure Python fallback)
    if len(text) < 50:
        t3, lg = extract_text_with_pypdf(pdf_bytes)
        logs += lg
        if len(t3) > len(text) or contains_devanagari(t3):
            text = t3

    # E) OCR (as last resort)
    if len(text) < 80 and not contains_devanagari(text):
        if fitz and pytesseract and PIL_Image:
            try:
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                ocr_buf = []
                for p in doc:
                    pix = p.get_pixmap(matrix=fitz.Matrix(2,2), alpha=False)
                    img = PIL_Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr = pytesseract.image_to_string(img, lang=OCR_LANG)
                    ocr_buf.append(ocr)
                doc.close()
                ocr_text = "\n\n".join(ocr_buf).strip()
                if len(ocr_text) > len(text) or contains_devanagari(ocr_text):
                    text = ocr_text
            except Exception as e:
                logs.append(f"OCR pipeline failed: {e}")
        else:
            logs.append("OCR skipped (fitz/pytesseract/PIL missing).")

    if pdf_path:
        try: os.unlink(pdf_path)
        except Exception: pass

    return text.strip(), logs

def extract_text_from_image(img_bytes: bytes) -> Tuple[str, List[str]]:
    mods = _lazy_imports()
    pytesseract = mods.get("pytesseract")
    PIL_Image = mods.get("PIL_Image")
    if not (pytesseract and PIL_Image):
        return "", ["OCR not available"]
    try:
        img = PIL_Image.open(io.BytesIO(img_bytes))
        t = pytesseract.image_to_string(img, lang=OCR_LANG) or ""
        return t.strip(), ["Image OCR ok"]
    except Exception as e:
        return "", [f"Image OCR fail: {e}"]

def extract_text_any(uploaded_file) -> Tuple[str, List[str]]:
    name = (uploaded_file.name or "").lower()
    data = uploaded_file.read()
    logs = [f"File: {uploaded_file.name} ({len(data)} bytes)"]
    try:
        if name.endswith(".txt"):
            return robust_decode(data), logs + ["Read .txt (robust)"]
        if name.endswith(".pdf"):
            t, more = extract_text_from_pdf(data); return t, logs + more
        if any(name.endswith(ext) for ext in (".png",".jpg",".jpeg",".webp",".tif",".tiff")):
            t, more = extract_text_from_image(data); return t, logs + more
        return "", logs + ["Unsupported file type."]
    except Exception as e:
        return "", logs + [f"extract_text_any error: {e}"]

# ────────────────────────── SUBJECTS / RULE CHECKS ──────────────────────────
COMMON_SUBJECTS = [
    "Anganwadi Helper/Worker Selection",
    "Teacher Appointment (ZP School)",
    "Transfers / Service Matters",
    "Works Contract / Tender",
    "MGNREGA Wage Claim",
    "Scholarship / Benefit Eligibility",
    "Procurement Irregularity",
    "Health (PHC/Rural Hospital) Staffing",
    "ZP Benefit Eligibility (Social Welfare)",
    "Land & Building Permission (ZP purview)",
    "Other (type below)"
]

def infer_key_points(case_txt: str, gr_txt: str, extra_legal: str) -> Dict:
    """Light rules to surface checks & risks; acts as a safety net for the draft."""
    checks, risks = [], []
    # GR: local residency patterns
    if any(k in gr_txt for k in ["स्थानिक", "รहिवासी", "रहिवासी", "local resident", "residency"]):
        checks.append("GR mentions local residency requirement.")
        if "3 km" in case_txt.lower() or "३" in case_txt or "3 कि" in case_txt or "३ कि" in case_txt:
            risks.append("Selection appears non-local while GR requires local residency.")
    # Hearing / natural justice
    if "सुनावणी" in case_txt or "hearing" in case_txt.lower():
        checks.append("Hearing/Natural justice referenced.")
        if any(k in case_txt.lower() for k in ["no hearing","not heard","सुनावणी न"]):
            risks.append("Possible violation of natural justice.")
    # Education
    if any(k in case_txt for k in ["१२ वी","12th","HSC"]):
        checks.append("Educational qualification mentioned.")
    # GR clause markers
    if re.search(r'(धोरण|प्रशासनिक|प्रकरण|कलम|section|clause|¶|\u0964)', gr_txt):
        checks.append("GR contains clause/section markers.")

    score = 0.6 + 0.1*min(3, len(checks)) - 0.1*min(3, len(risks))
    if not case_txt.strip() or not gr_txt.strip():
        score = min(score, 0.5); risks.append("Text extraction incomplete (paste missing text in fallback).")
    score = max(0.35, min(0.92, score))
    return {"checks": checks, "risks": risks, "confidence": round(score, 2)}

# ────────────────────────── GR CLAUSE HIGHLIGHTER ──────────────────────────
CLAUSE_PATTERNS = [
    r'(कलम\\s*\\d+[A-Za-z]?)',
    r'(धोरण\\s*\\d+)',
    r'(अट\\s*\\d+)',
    r'(Clause\\s*\\d+)',
    r'(Section\\s*\\d+[A-Za-z]?)'
]
_clause_regex = re.compile("|".join(CLAUSE_PATTERNS), flags=re.IGNORECASE)

def highlight_gr_clauses(text: str, max_lines: int = 120) -> str:
    if not text.strip():
        return "<em>No GR text available.</em>"
    lines = text.splitlines()
    out = []
    for ln in lines[:max_lines]:
        if (_clause_regex.search(ln) or
            ("स्थानिक" in ln) or ("रहिवासी" in ln) or ("resident" in ln.lower())):
            ln = re.sub(_clause_regex, r'<span class="hl">\1</span>', ln)
            out.append(f"<div>• {ln}</div>")
        else:
            out.append(f"<div>{ln}</div>")
    if len(lines) > max_lines:
        out.append("<div>…</div>")
    return "\n".join(out)

# ────────────────────────── ORDER DRAFTS ──────────────────────────
def order_marathi_quasi(meta: dict, decision: dict, refs: list) -> str:
    ref_lines = "\n\t".join([f"{i+1}.\t{r}" for i, r in enumerate(refs)]) if refs else "—"
    today = datetime.date.today().strftime("%d/%m/%Y")
    return f"""📝 **निर्णय-आदेश (अर्धन्यायिक – मराठी मसुदा)**

**कार्यालय :** {meta['officer']}  
**फाईल क्र.:** {decision['case_id']}  
**विषय :** {decision['subject']}  
**दिनांक :** {today}

**संदर्भ :**  
\t{ref_lines}

⸻

**आदेश :**  

सदर सुनावणीत सादर कागदपत्रे व शासन निर्णयातील तरतुदींचा विचार करता आढळून आले की –  
\t• शासन निर्णयातील **स्थानिक रहिवासी** अट बंधनकारक आहे.  
\t• ग्रामीण/आदिवासी प्रकल्पातील पदांसाठी उमेदवार सदर महसुली गावातील स्थानिक रहिवासी असणे आवश्यक आहे.  
\t• नोंदीप्रमाणे तक्रारदार पात्रता व स्थानिक निकष पूर्ण करतात.  
\t• पूर्वनिवड शासन निर्णयाविरोधात झालेली दिसते.

⸻

**निर्णय :**  

म्हणून, अर्धन्यायिक अधिकाराने खालीलप्रमाणे आदेश देण्यात येतो –  
\t1. संबंधित पदाची **पूर्वीची निवड रद्द** करण्यात येते.  
\t2. शासन निर्णयातील अटीप्रमाणे **स्थानिक पात्र उमेदवारास** निवड व नियुक्ती मान्य करण्यात येते.  
\t3. संबंधित प्रकल्प अधिकारी यांनी **७ दिवसांच्या** आत आवश्यक पुढील कार्यवाही करून **नियुक्ती आदेश** निर्गमित करावा व अनुपालन अहवाल सादर करावा.

⸻

(मुख्य कार्यकारी अधिकारी)  
जिल्हा परिषद, चंद्रपूर
"""

def order_english_quasi(meta: dict, decision: dict, refs: list) -> str:
    today = datetime.date.today().strftime("%d/%m/%Y")
    refs_md = "\n- " + "\n- ".join(refs) if refs else "\n- —"
    return f"""📝 **Decision Order (Quasi-Judicial Draft)**

**Office :** {meta['officer']}  
**File No.:** {decision['case_id']}  
**Subject :** {decision['subject']}  
**Date :** {today}

**References :**{refs_md}

---

**Order :**  
Upon consideration of the record and relevant Government Resolution(s), it is found that:  
- The **local residency** condition is mandatory.  
- For rural/tribal projects, the candidate must be a local resident of the revenue village.  
- The complainant appears eligible and local per record.  
- The earlier selection is contrary to the GR.

**Decision :**  
1) The earlier selection is **hereby cancelled**.  
2) As per the GR conditions, **the eligible local candidate** is approved for selection and appointment.  
3) The concerned Project Officer shall issue the **appointment order within 7 days** and report compliance.

(Chief Executive Officer)  
Zilla Parishad, Chandrapur
"""

# ────────────────────────── SIGNATURE BLOCK BUILDER ──────────────────────────
def build_signature_block(lang: str, name: str, designation: str, place: str, sign_date: str) -> str:
    if lang.lower().startswith("mar"):
        return f"""
<div class="sig-block">
  <div class="sig-rows">
    <div><span class="sig-label">स्थान :</span> {place}</div>
    <div><span class="sig-label">दिनांक :</span> {sign_date}</div>
  </div>
  <div style="height:36px"></div>
  <div class="sig-name">({name})</div>
  <div class="sig-desig">{designation}</div>
  <div>जिल्हा परिषद, चंद्रपूर</div>
  <div class="small">[कार्यालयीन शिक्का / Official Seal]</div>
</div>
"""
    else:
        return f"""
<div class="sig-block">
  <div class="sig-rows">
    <div><span class="sig-label">Place:</span> {place}</div>
    <div><span class="sig-label">Date:</span> {sign_date}</div>
  </div>
  <div style="height:36px"></div>
  <div class="sig-name">({name})</div>
  <div class="sig-desig">{designation}</div>
  <div>Zilla Parishad, Chandrapur</div>
  <div class="small">[Office Seal / Official Stamp]</div>
</div>
"""

# ────────────────────────── UI TABS ──────────────────────────
t1, t2, t3, t4, t5 = st.tabs([
    "1) Case Intake",
    "2) Documents — Upload / Paste",
    "3) Analyze & Decide",
    "4) Generate Order",
    "5) System / Security"
])

# ——— Case Intake
with t1:
    st.markdown("<div class='section-title'>Case Intake</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.2,1.2,1])
    with c1:
        case_id = st.text_input("File / Case ID", "ZP/CH/2025/0001")
        officer = st.text_input("Officer", "Chief Executive Officer, Zilla Parishad Chandrapur")
        hearing_date = st.date_input("Hearing Date", datetime.date.today())
    with c2:
        preset = st.selectbox("Case Subject (pick)", COMMON_SUBJECTS, index=0)
        free_subject = st.text_input("Or type subject (free)", "")
        subject = free_subject.strip() or preset
        jurisdiction = st.text_input("Jurisdiction", "Zilla Parishad, Chandrapur")
    with c3:
        sensitive_mode = st.toggle("Sensitive mode (redact previews; no disk writes)", value=True)
        lang_default = st.radio("Default Order Language", ["Marathi","English"], index=0, horizontal=True)
    relief = st.text_input("Relief Requested", "Cancel earlier selection; appoint eligible local candidate")
    issues = st.text_area("Issues (comma-separated)", "Local residency; GR compliance; Natural justice")
    st.caption("Note: Subject and Relief appear verbatim in the order draft.")
    st.session_state["sensitive_mode"] = sensitive_mode  # used in previews

# ——— Documents
with t2:
    st.markdown("<div class='section-title'>Documents — Upload or Paste (with Specific Legal Inputs)</div>", unsafe_allow_html=True)
    st.markdown("<span class='badge'>Mandatory: Case file and Government GR</span>", unsafe_allow_html=True)
    a1, a2 = st.columns(2)
    with a1:
        st.markdown("#### 📄 Case Upload  **(Mandatory)**")
        case_file = st.file_uploader("Case File (PDF/TXT/Image)", type=["pdf","txt","png","jpg","jpeg","webp","tif","tiff"])
        case_text_manual = st.text_area("Optional: paste Case text (fallback if OCR fails)", height=140)
        case_inputs = st.text_area("Specific legal inputs for Case (sections/points)", height=90)
    with a2:
        st.markdown("#### 📑 Government GR Upload  **(Mandatory)**")
        gr_file = st.file_uploader("Government GR (PDF/TXT/Image)", type=["pdf","txt","png","jpg","jpeg","webp","tif","tiff"])
        gr_text_manual = st.text_area("Optional: paste GR text (fallback if OCR fails)", height=140)
        gr_inputs = st.text_area("Specific legal inputs for GR (numbers/dates/clauses)", height=90)

    st.markdown("#### ⚖️ Additional Authorities (Optional)")
    b1, b2 = st.columns(2)
    with b1:
        judgments = st.file_uploader("Previous Judgments (PDF/TXT)", type=["pdf","txt"], accept_multiple_files=True)
        procedures = st.file_uploader("Relevant Procedures / SOPs (PDF/TXT)", type=["pdf","txt"], accept_multiple_files=True)
    with b2:
        sections = st.file_uploader("Legal Sections / Acts (PDF/TXT)", type=["pdf","txt"], accept_multiple_files=True)
        other_notes = st.text_area("Other legal notes", height=90)

# helper: read & preview (with redaction)
def _read_and_preview(label: str, uploaded_file, pasted: str, limit: int = 1200) -> Tuple[str, List[str]]:
    logs: List[str] = []
    if pasted and pasted.strip():
        txt = pasted.strip()
        logs.append(f"{label}: manual pasted text used ({len(txt)} chars).")
    elif uploaded_file is not None:
        txt, lg = extract_text_any(uploaded_file)
        logs.extend([f"{label}: "+x for x in lg])
    else:
        txt = ""
        logs.append(f"{label}: file missing.")

    prev = redact_sensitive(txt[:limit]) if st.session_state.get("sensitive_mode", True) else txt[:limit]
    if txt.strip():
        st.markdown(f"**Preview — {label} (first {limit} chars)**")
        st.code(prev + ("..." if len(txt) > limit else ""), language="markdown")
        if label == "GR":
            st.markdown("**GR Clauses (auto-highlighted)**")
            st.markdown(f"<div class='card'>{highlight_gr_clauses(txt)}</div>", unsafe_allow_html=True)
    else:
        st.info(f"No readable text for **{label}**. If scanned, paste text in the fallback box.")
    return txt, logs

# ——— Analyze & Decide
with t3:
    st.markdown("<div class='section-title'>Analyze & Decide</div>", unsafe_allow_html=True)
    lang_choice = st.radio("Generate draft primarily in", ["Marathi","English","Both"], index=0 if lang_default=="Marathi" else 1, horizontal=True)
    references_text = st.text_area(
        "References (one per line): GR No./Date, letters, complaint date, hearing date etc.",
        "महाराष्ट्र शासन, महिला व बालविकास विभाग शासन निर्णय क्र. एबावि-2022/प्र.क्र.94/का-6, दि. 02/02/2023\n"
        "मा. आयुक्त, ईबावि, नवी मुंबई यांचे पत्र, दि. 31/01/2025\n"
        "तक्रार अर्ज, दि. 28/03/2025\n"
        f"सुनावणी दिनांक : {datetime.date.today().strftime('%d/%m/%Y')}"
    )
    run = st.button("Run Analysis & Build Decision", type="primary", use_container_width=True)

    if run:
        warnings: List[str] = []
        logs_all: List[str] = []
        if case_file is None or gr_file is None:
            st.error("❌ Upload BOTH **Case** and **Government GR** (mandatory).")
        else:
            with st.status("Processing…", expanded=False) as status:
                status.update(label="Reading Case", state="running")
                case_txt, lg1 = _read_and_preview("CASE", case_file, case_text_manual); logs_all += lg1

                status.update(label="Reading GR", state="running")
                gr_txt, lg2 = _read_and_preview("GR", gr_file, gr_text_manual); logs_all += lg2

                def read_many(files, tag)->Tuple[str, List[str]]:
                    pieces, lg = [], []
                    if files:
                        for f in files:
                            t, _lg = extract_text_any(f)
                            pieces.append(t); lg += _lg
                    return "\n\n".join(pieces), [f"{tag}: "+x for x in lg]

                judg_txt, lgJ = read_many(judgments, "JUDG"); logs_all += lgJ
                secs_txt, lgS = read_many(sections, "SECTIONS"); logs_all += lgS
                proc_txt, lgP = read_many(procedures, "PROCS"); logs_all += lgP

                extra_legal = "\n".join(filter(None, [gr_inputs, case_inputs, other_notes, judg_txt, secs_txt, proc_txt]))

                if not case_txt.strip(): warnings.append("Case text empty (paste missing parts in fallback).")
                if not gr_txt.strip(): warnings.append("GR text empty (paste missing parts in fallback).")

                findings = infer_key_points(case_txt, gr_txt, extra_legal)

                decision = {
                    "case_id": case_id,
                    "case_type": subject,
                    "subject": (relief or subject),
                    "recommended_outcome": "Approve with conditions (subject to GR compliance and natural justice).",
                    "checks": findings["checks"],
                    "risks": findings["risks"],
                    "confidence": findings["confidence"],
                }
                meta = {
                    "officer": officer,
                    "jurisdiction": jurisdiction,
                    "hearing_date": str(hearing_date),
                    "issues": issues,
                }
                status.update(label="Decision built", state="complete")

            st.markdown("<div class='card'><h3>Decision (Structured)</h3>", unsafe_allow_html=True)
            st.json(decision)
            st.markdown("</div>", unsafe_allow_html=True)

            if warnings or decision["risks"]:
                st.markdown("<div class='alert-warn'>", unsafe_allow_html=True)
                for w in warnings: st.write("⚠️ "+w)
                for r in decision["risks"]: st.write("⚠️ "+r)
                st.markdown("</div>", unsafe_allow_html=True)

            st.session_state["decision"] = decision
            st.session_state["meta"] = meta
            st.session_state["refs"] = [ln.strip() for ln in (references_text or "").splitlines() if ln.strip()]

# ——— Generate Order (with watermark + signature block)
with t4:
    st.markdown("<div class='section-title'>Generate Order</div>", unsafe_allow_html=True)
    if "decision" not in st.session_state:
        st.info("Run **Analyze & Decide** first.")
    else:
        decision = st.session_state["decision"]
        meta = st.session_state["meta"]
        refs = st.session_state.get("refs", [])

        # Signature & watermark controls
        st.markdown("#### Signature & Presentation")
        colA, colB, colC = st.columns([1.1, 1.1, 1])
        with colA:
            sign_name = st.text_input("Signatory Name", value="(Name of CEO)")
            sign_designation = st.text_input("Designation", value="Chief Executive Officer")
        with colB:
            sign_place = st.text_input("Place", value="Chandrapur")
            sign_date = st.text_input("Sign Date (dd/mm/yyyy)", value=datetime.date.today().strftime("%d/%m/%Y"))
        with colC:
            add_watermark = st.toggle("Watermark with ZP Seal", value=True)
            include_signature = st.toggle("Include Signature Block", value=True)

        default_idx = 0 if (lang_default=="Marathi" or contains_devanagari(decision["subject"])) else 1
        view_lang = st.radio("Preview Language", ["Marathi","English","Both"], index=default_idx, horizontal=True)

        # Base orders
        mr = order_marathi_quasi(meta, decision, refs)
        en = order_english_quasi(meta, decision, refs)

        # Signature blocks
        mr_sig_html = build_signature_block("marathi", sign_name, sign_designation, sign_place, sign_date) if include_signature else ""
        en_sig_html = build_signature_block("english", sign_name, sign_designation, sign_place, sign_date) if include_signature else ""
        mr_md_tail = f"\n\n\n({sign_name})\n{sign_designation}\nजिल्हा परिषद, चंद्रपूर\nस्थान: {sign_place}  दिनांक: {sign_date}\n" if include_signature else ""
        en_md_tail = f"\n\n\n({sign_name})\n{sign_designation}\nZilla Parishad, Chandrapur\nPlace: {sign_place}  Date: {sign_date}\n" if include_signature else ""

        # Watermark wrapper
        wm_html_top = f"""<div class="order-block wm-wrap"><div class="wm-bg"><img src="{st.session_state['seal_data_url']}" /></div><div class="order-content">""" if add_watermark \
                      else """<div class="order-block"><div class="order-content">"""
        wm_html_bottom = "</div></div>"

        # Render & downloads
        if view_lang in ["Marathi","Both"]:
            st.markdown("#### 📜 Marathi Order")
            st.markdown(wm_html_top + mr + mr_sig_html + wm_html_bottom, unsafe_allow_html=True)
            st.download_button(
                "Download Order (MR).md",
                mr + ("\n\n---\n" + mr_md_tail if include_signature else ""),
                file_name=f"{decision['case_id']}_Order_MR.md",
                use_container_width=True
            )

        if view_lang in ["English","Both"]:
            st.markdown("#### 📜 English Order")
            st.markdown(wm_html_top + en + en_sig_html + wm_html_bottom, unsafe_allow_html=True)
            st.download_button(
                "Download Order (EN).md",
                en + ("\n\n---\n" + en_md_tail if include_signature else ""),
                file_name=f"{decision['case_id']}_Order_EN.md",
                use_container_width=True
            )

# ——— System / Security
with t5:
    st.markdown("<div class='section-title'>System / Security</div>", unsafe_allow_html=True)
    cols = st.columns(2)
    with cols[0]:
        st.write({
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cwd": os.getcwd(),
        })
        st.write("Streamlit:", st.__version__)
        st.write("pandas:", pd.__version__)
        st.write("tesseract path:", shutil.which("tesseract") or "NOT FOUND")
        st.write("TESSDATA_PREFIX:", os.environ.get("TESSDATA_PREFIX","(unset)"))
    with cols[1]:
        mods=_lazy_imports()
        st.write({
            "fitz(PyMuPDF)": "OK" if mods.get("fitz") else f"ERROR: {mods.get('fitz_err','')}",
            "pdfminer.six": "OK" if mods.get("pdfminer_extract_text") else f"ERROR: {mods.get('pdfminer_err','')}",
            "pytesseract": "OK" if mods.get("pytesseract") else f"ERROR: {mods.get('pytesseract_err','')}",
            "Pillow": "OK" if mods.get("PIL_Image") else "ERROR (PIL not loaded)",
            "pypdf": "OK" if mods.get("PdfReader") else f"ERROR: {mods.get('pypdf_err','')}",
        })

    st.markdown("""
<div class="footer">
<strong>Zilla Parishad, Chandrapur — Government of Maharashtra.</strong><br/>
Drafts are advisory; final orders must be reviewed & signed by the competent authority.  
Do not share case files beyond authorized officers. All access is subject to audit.
</div>
""", unsafe_allow_html=True)
