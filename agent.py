# -*- coding: utf-8 -*-
import io, os, re, datetime, tempfile, platform, shutil
from typing import List, Tuple
import streamlit as st
import pandas as pd

# ────────────────────────── PAGE STYLE ──────────────────────────
st.set_page_config(page_title="ZP CEO Decision Agent", layout="wide")
st.markdown("""
<style>
:root { --brand:#0b5fff; --ink:#0f172a; --muted:#475569; --line:#e2e8f0; --bg:#ffffff; }
.block-container { max-width: 1220px !important; padding-top: .8rem; }
h1,h2,h3 { font-weight: 750 !important; color: var(--ink); letter-spacing:-.2px; }
hr { border:0; border-top:1px solid var(--line); margin:.8rem 0 1.2rem 0; }
.badge { display:inline-block; padding:2px 10px; border:1px solid var(--line); border-radius:999px; font-weight:600; font-size:.8rem; background:#f8fafc; }
.card { border:1px solid var(--line); border-radius:12px; padding:16px; background:#fff; }
.codeblock pre, .codeblock code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size:.95rem; }
.stTabs [data-baseweb="tab-list"]{ gap:6px; }
.stTabs [role="tab"]{ padding:10px 14px; border-radius:10px 10px 0 0; background:#f8fafc; border:1px solid var(--line); border-bottom:none; }
.stTabs [aria-selected="true"]{ background:#fff; border-bottom:1px solid #fff; }
.small { color:#64748b; font-size:.92rem; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🏛️ ZP Chandrapur — CEO Decision Agent</h1>", unsafe_allow_html=True)
st.caption("Quasi-judicial decisions and professional orders. OCR supports Marathi / Hindi / English. Files mandatory: **Case** & **Government GR**.")

# ────────────────────────── IMPORTS / ENV ──────────────────────────
def _lazy_imports():
    mods = {}
    try:
        import fitz; mods["fitz"]=fitz
    except Exception as e: mods["fitz"]=None; mods["fitz_err"]=str(e)
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text
        mods["pdfminer_extract_text"]=pdfminer_extract_text
    except Exception as e: mods["pdfminer_extract_text"]=None; mods["pdfminer_err"]=str(e)
    try:
        import pytesseract; from PIL import Image
        mods["pytesseract"]=pytesseract; mods["PIL_Image"]=Image
    except Exception as e: mods["pytesseract"]=None; mods["PIL_Image"]=None; mods["pytesseract_err"]=str(e)
    return mods

# help tesseract find languages
for p in ["/usr/share/tesseract-ocr/4.00/tessdata", "/usr/share/tesseract-ocr/tessdata"]:
    if os.path.isdir(p): os.environ.setdefault("TESSDATA_PREFIX", p); break

OCR_LANG = "eng+hin+mar"
DEVANAGARI_RE = re.compile(r'[\u0900-\u097F]')
def contains_devanagari(txt: str) -> bool: return bool(DEVANAGARI_RE.search(txt or ""))

def robust_decode(data: bytes) -> str:
    for enc in ("utf-8","utf-8-sig","utf-16","utf-16le","utf-16be"):
        try: return data.decode(enc)
        except Exception: pass
    return data.decode("latin-1", errors="ignore")

# ────────────────────────── EXTRACTION ──────────────────────────
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

    # A) PyMuPDF "text"
    try:
        if fitz:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            parts = [p.get_text("text") for p in doc]
            doc.close()
            text = "\n".join(parts).strip()
    except Exception as e:
        logs.append(f"fitz text failed: {e}")

    # B) PyMuPDF blocks reconstruct (helps Indic PDFs)
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
                        if t: blocks_all.append(t)
            doc.close()
            textB = "\n".join(blocks_all).strip()
            if len(textB) > len(text) or (contains_devanagari(textB) and not contains_devanagari(text)):
                text = textB
    except Exception as e:
        logs.append(f"fitz blocks failed: {e}")

    # C) pdfminer as secondary
    if (not contains_devanagari(text)) and pdfminer_extract_text and pdf_path:
        try:
            t2 = pdfminer_extract_text(pdf_path) or ""
            if contains_devanagari(t2) or len(t2) > len(text):
                text = t2
        except Exception as e:
            logs.append(f"pdfminer failed: {e}")

    # D) OCR only if still weak
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
    pytesseract = mods.get("pytesseract"); PIL_Image = mods.get("PIL_Image")
    if not (pytesseract and PIL_Image): return "", ["OCR not available"]
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

# ────────────────────────── ORDER FORMATS ──────────────────────────
def order_marathi_quasi(meta: dict, decision: dict, refs: list) -> str:
    """Exact, formal Marathi order in your requested style."""
    # Format references list
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

# ────────────────────────── UI (Tabs) ──────────────────────────
t1, t2, t3, t4 = st.tabs(["1) Case", "2) Documents", "3) Decision & Order", "4) System/Logs"])

with t1:
    st.markdown("### Case Intake")
    c1, c2 = st.columns(2)
    with c1:
        case_id = st.text_input("File/Case ID", "ZP/CH/2025/0001")
        officer = st.text_input("Officer", "Chief Executive Officer, ZP Chandrapur")
        cause_date = st.date_input("Cause of Action Date", datetime.date.today())
    with c2:
        case_type = st.text_input("Case Type / Subject", "Anganwadi Helper Selection – Nanakpathar (Jiwati)")
        jurisdiction = st.text_input("Jurisdiction", "Zilla Parishad, Chandrapur")
        filing_date = st.date_input("Filing Date", datetime.date.today())
    relief = st.text_input("Requested Relief", "Cancel earlier selection; appoint eligible local candidate")
    issues = st.text_area("Issues (comma-separated)", "Local residency; GR compliance; Natural justice")
    annexures = st.text_area("Annexures (one per line)", "Application\nResidence Proof\nEducation Certificates")

with t2:
    st.markdown("### Uploads (Mandatory)")
    st.markdown("<span class='badge'>Files are mandatory; text boxes are optional fallback</span>", unsafe_allow_html=True)
    st.markdown("#### A) Case Upload  <span class='badge'>Mandatory</span>", unsafe_allow_html=True)
    case_file = st.file_uploader("📄 Case File (PDF/TXT/Image)", type=["pdf","txt","png","jpg","jpeg","webp","tif","tiff"])
    case_text_manual = st.text_area("Optional: paste Case text (use only if OCR fails)", height=140)
    st.markdown("#### B) Government GR Upload  <span class='badge'>Mandatory</span>", unsafe_allow_html=True)
    gr_file = st.file_uploader("📑 Government GR (PDF/TXT/Image)", type=["pdf","txt","png","jpg","jpeg","webp","tif","tiff"])
    gr_text_manual = st.text_area("Optional: paste GR text (use only if OCR fails)", height=140)

with t3:
    st.markdown("### Generate Decision & Order")
    lang_choice = st.radio("Order Language", ["Marathi", "English", "Both"], index=0, horizontal=True)
    references_text = st.text_area("References (one per line) — e.g., GR number/date, letters, hearing date", 
                                   "महाराष्ट्र शासन, महिला व बालविकास विभाग शासन निर्णय क्र. एबावि-2022/प्र.क्र.94/का-6, दि. 02/02/2023\n"
                                   "मा. आयुक्त, ईबावि सेवा, नवी मुंबई यांचे पत्र, दि. 31/01/2025\n"
                                   "तक्रार अर्ज, दि. 28/03/2025\n"
                                   "सुनावणी दिनांक : 13/05/2025")
    generate = st.button("Generate Decision", type="primary", use_container_width=True)

    debug_lines: List[str] = []

    def read_text(label: str, uploaded_file, manual_text: str) -> str:
        if manual_text and manual_text.strip():
            debug_lines.append(f"{label}: using manual pasted text.")
            return manual_text.strip()
        if uploaded_file is None:
            debug_lines.append(f"{label}: file missing.")
            return ""
        t, logs = extract_text_any(uploaded_file)
        debug_lines.extend([f"{label}: "+ln for ln in logs])
        return (t or "").strip()

    if generate:
        # enforce mandatory files
        if case_file is None or gr_file is None:
            st.error("❌ Please upload BOTH: Case file and Government GR.")
        else:
            case_txt = read_text("CASE", case_file, case_text_manual)
            gr_txt   = read_text("GR",   gr_file,   gr_text_manual)

            # decision (structured; rules can be replaced by LLM later)
            decision = {
                "case_id": case_id,
                "case_type": case_type,
                "subject": relief or case_type,
                "recommended_outcome": "Approve with conditions",
                "confidence": 0.86 if (case_txt or gr_txt) else 0.45,
            }
            meta = {
                "officer": officer,
                "jurisdiction": jurisdiction,
                "cause_date": str(cause_date),
                "filing_date": str(filing_date),
                "issues": issues,
            }
            st.success("✅ Decision generated")
            st.json(decision)

            # build reference list
            refs = [ln.strip() for ln in (references_text or "").splitlines() if ln.strip()]

            # Orders
            if lang_choice in ["Marathi", "Both"]:
                order_mr = order_marathi_quasi(
                    {
                        "officer": officer,
                        "jurisdiction": jurisdiction,
                        "cause_date": str(cause_date),
                        "filing_date": str(filing_date),
                        "issues": issues,
                    },
                    decision,
                    refs
                )
                st.markdown("#### 📜 Marathi Order")
                st.markdown(order_mr)
                st.download_button("Download Order (MR).md", order_mr, file_name=f"{case_id}_Order_MR.md", use_container_width=True)

            if lang_choice in ["English", "Both"]:
                order_en = order_english_quasi(
                    {
                        "officer": officer,
                        "jurisdiction": jurisdiction,
                        "cause_date": str(cause_date),
                        "filing_date": str(filing_date),
                        "issues": issues,
                    },
                    decision,
                    refs
                )
                st.markdown("#### 📜 English Order")
                st.markdown(order_en)
                st.download_button("Download Order (EN).md", order_en, file_name=f"{case_id}_Order_EN.md", use_container_width=True)

with t4:
    st.markdown("### System / Environment")
    st.write({
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cwd": os.getcwd(),
    })
    st.write("Streamlit:", st.__version__)
    st.write("pandas:", pd.__version__)
    st.write("tesseract path:", shutil.which("tesseract") or "NOT FOUND")
    st.write("TESSDATA_PREFIX:", os.environ.get("TESSDATA_PREFIX","(unset)"))

    st.markdown("#### Quick import check")
    mods = _lazy_imports()
    st.write({
        "fitz(PyMuPDF)": "OK" if mods.get("fitz") else f"ERROR: {mods.get('fitz_err','')}",
        "pdfminer.six": "OK" if mods.get("pdfminer_extract_text") else f"ERROR: {mods.get('pdfminer_err','')}",
        "pytesseract": "OK" if mods.get("pytesseract") else f"ERROR: {mods.get('pytesseract_err','')}",
        "Pillow": "OK" if mods.get("PIL_Image") else "ERROR (PIL not loaded)",
    })
