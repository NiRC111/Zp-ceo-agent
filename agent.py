import io, os, datetime, tempfile
from typing import List, Tuple

import streamlit as st
import pandas as pd

st.set_page_config(page_title="ZP CEO Decision Agent", layout="wide")

# =========================
# STYLE (professional UI)
# =========================
st.markdown("""
<style>
/* tighten layout & fonts */
:root { --brand: #0b5fff; --muted:#64748b; --ok:#1a7f37; --warn:#b58100; --bad:#b42318; }
.block-container { max-width: 1180px; }
h1, h2, h3 { font-weight: 700 !important; }
hr { border: 0; border-top: 1px solid #e2e8f0; margin: 0.75rem 0 1rem 0; }
.badge { display:inline-block; padding:2px 8px; border:1px solid #e2e8f0; border-radius:999px; color:#0f172a; background:#f8fafc; font-size:0.8rem; font-weight:600; }
.note { color: var(--muted); font-size: 0.9rem; }
.ok{color:var(--ok);} .warn{color:var(--warn);} .bad{color:var(--bad);}
textarea { font-family: ui-monospace, Menlo, Consolas, monospace; }
.sidebar .sidebar-content { padding-top: 1rem !important; }
</style>
""", unsafe_allow_html=True)

st.title("🏛️ ZP Chandrapur — CEO Decision Agent")
st.caption("Mandatory: **Case File** + **Government GR**. Scanned PDFs & images supported via OCR (Marathi/Hindi/English).")

# =========================
# UTIL: lazy heavy imports
# =========================
def _try_imports():
    mods = {}
    try:
        import fitz  # PyMuPDF
        mods["fitz"] = fitz
    except Exception:
        mods["fitz"] = None
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text
        mods["pdfminer_extract_text"] = pdfminer_extract_text
    except Exception:
        mods["pdfminer_extract_text"] = None
    try:
        import pytesseract
        from PIL import Image
        mods["pytesseract"] = pytesseract
        mods["PIL_Image"] = Image
    except Exception:
        mods["pytesseract"] = None
        mods["PIL_Image"] = None
    try:
        import easyocr    # NOTE: easyocr supports en/hi (not mar), used as fallback
        mods["easyocr"] = easyocr
    except Exception:
        mods["easyocr"] = None
    return mods

OCR_LANG = "eng+hin+mar"  # tesseract languages

# =========================
# OCR / TEXT EXTRACT
# =========================
def extract_text_from_pdf(pdf_bytes: bytes, dpi: int = 220) -> Tuple[str, List[str]]:
    """
    Strategy:
      1) PyMuPDF direct text
      2) pdfminer.six extraction
      3) OCR by rendering pages (pytesseract preferred, easyocr fallback for en/hi)
    """
    logs = []
    mods = _try_imports()
    fitz = mods["fitz"]
    pdfminer_extract_text = mods["pdfminer_extract_text"]
    pytesseract = mods["pytesseract"]
    PIL_Image = mods["PIL_Image"]
    easyocr = mods["easyocr"]

    text = ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        pdf_path = tmp.name

    # 1) PyMuPDF
    try:
        if fitz is not None:
            logs.append("PyMuPDF: direct extraction.")
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            parts = [page.get_text("text") for page in doc]
            doc.close()
            text = "\n".join(parts).strip()
        else:
            logs.append("PyMuPDF not available.")
    except Exception as e:
        logs.append(f"PyMuPDF failed: {e}")

    # 2) pdfminer fallback
    if len(text) < 120 and pdfminer_extract_text is not None:
        logs.append("pdfminer.six: secondary extraction.")
        try:
            text2 = pdfminer_extract_text(pdf_path) or ""
            if len(text2) > len(text):
                text = text2
                logs.append("pdfminer improved text.")
        except Exception as e:
            logs.append(f"pdfminer failed: {e}")

    # 3) OCR rendering if still weak
    if len(text) < 120:
        logs.append("Direct text weak → OCR on rendered pages.")
        if fitz is None:
            logs.append("Cannot OCR rendered pages (PyMuPDF missing).")
        else:
            try:
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                ocr_segments = []
                for page_index in range(len(doc)):
                    page = doc[page_index]
                    zoom = dpi / 72.0
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    img_bytes = pix.tobytes("png")

                    if pytesseract is not None and PIL_Image is not None:
                        img = PIL_Image.open(io.BytesIO(img_bytes))
                        ocr = pytesseract.image_to_string(img, lang=OCR_LANG)
                        ocr_segments.append(ocr)
                    elif easyocr is not None:
                        # easyocr supports en/hi; marathi may not be fully supported
                        reader = easyocr.Reader(["en", "hi"], gpu=False)
                        res = reader.readtext(io.BytesIO(img_bytes), detail=0)
                        ocr_segments.append("\n".join(res))
                    else:
                        logs.append("No OCR engine (pytesseract/easyocr) installed.")
                        break
                doc.close()

                merged = "\n\n".join(ocr_segments).strip()
                if len(merged) > len(text):
                    text = merged
                    logs.append("OCR extracted text successfully.")
            except Exception as e:
                logs.append(f"OCR pipeline failed: {e}")

    try:
        os.unlink(pdf_path)
    except Exception:
        pass

    return text.strip(), logs

def extract_text_from_image(img_bytes: bytes) -> Tuple[str, List[str]]:
    logs = []
    mods = _try_imports()
    pytesseract = mods["pytesseract"]
    PIL_Image = mods["PIL_Image"]
    easyocr = mods["easyocr"]

    text = ""
    try:
        if pytesseract is not None and PIL_Image is not None:
            img = PIL_Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(img, lang=OCR_LANG) or ""
            logs.append(f"pytesseract OCR used ({OCR_LANG}).")
        elif easyocr is not None:
            reader = easyocr.Reader(["en", "hi"], gpu=False)
            res = reader.readtext(io.BytesIO(img_bytes), detail=0)
            text = "\n".join(res)
            logs.append("easyocr used (en/hi fallback).")
        else:
            logs.append("No OCR engine installed.")
    except Exception as e:
        logs.append(f"Image OCR failed: {e}")
    return (text or "").strip(), logs

def extract_text_any(uploaded_file) -> Tuple[str, List[str]]:
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    logs = [f"File: {uploaded_file.name} ({len(data)} bytes)"]

    if name.endswith(".txt"):
        try:
            text = data.decode("utf-8", errors="ignore")
            logs.append("Read as .txt (utf-8).")
            return text, logs
        except Exception as e:
            logs.append(f"TXT decode failed: {e}")
            return "", logs

    if name.endswith(".pdf"):
        txt, more = extract_text_from_pdf(data)
        return txt, logs + more

    if any(name.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"]):
        txt, more = extract_text_from_image(data)
        return txt, logs + more

    logs.append("Unsupported file type.")
    return "", logs

# =========================
# SIDEBAR – quick help
# =========================
with st.sidebar:
    st.markdown("### Help")
    st.write("• Upload **Case** and **Government GR** files (PDF/IMG/TXT).")
    st.write("• If OCR fails, **paste text** in the boxes provided right below each upload.")
    st.write("• Click **Generate Decision** → then **Generate Order** (EN/MR/Both).")
    st.write("• Use **Debug / OCR Logs** at bottom if something fails.")
    st.write("• OCR languages: **Marathi, Hindi, English**.")

# =========================
# CASE INTAKE
# =========================
st.markdown("## 1) Case Intake")
c1, c2 = st.columns(2)
with c1:
    case_id = st.text_input("Case ID", "ZP/CH/2025/0001")
    officer = st.text_input("Officer", "Chief Executive Officer, ZP Chandrapur")
    cause_date = st.date_input("Cause of Action Date", value=datetime.date.today())
with c2:
    case_type = st.text_input("Type of Case / Subject", "Tender appeal")
    jurisdiction = st.text_input("Jurisdiction", "Zilla Parishad, Chandrapur")
    filing_date = st.date_input("Filing Date", value=datetime.date.today())
relief = st.text_input("Requested Relief", "Set aside rejection and reconsider award")
issues = st.text_area("Issues (comma-separated)", "eligibility under Rule 12(3), natural justice hearing")
annexures = st.text_area("Annexures (one per line)", "ApplicationForm\nIDProof\nFeeReceipt")
st.markdown("<hr/>", unsafe_allow_html=True)

# =========================
# DOCUMENTS — MANDATORY
# =========================
st.markdown("## 2) Documents — Case & GR (Mandatory)")

# ---- CASE
st.markdown("#### A) Case Upload  <span class='badge'>Mandatory</span>", unsafe_allow_html=True)
case_file = st.file_uploader("📄 Upload Case File", type=["pdf","txt","png","jpg","jpeg","webp","tif","tiff"], key="case_file")
case_text_manual = st.text_area("If Case file text is not extracted, paste it here", height=160, key="case_text_manual")
case_specific = st.text_area("Specific Legal Inputs (Case) — sections/clauses/admissions", height=120, key="case_specific")

# ---- GR
st.markdown("#### B) Government GR Upload  <span class='badge'>Mandatory</span>", unsafe_allow_html=True)
gr_file = st.file_uploader("📑 Upload Government GR", type=["pdf","txt","png","jpg","jpeg","webp","tif","tiff"], key="gr_file")
gr_text_manual = st.text_area("If GR text is not extracted, paste it here", height=160, key="gr_text_manual")
gr_specific = st.text_area("Specific Legal Inputs (GR) — exact GR numbers/dates/clauses", height=120, key="gr_specific")

st.markdown("<hr/>", unsafe_allow_html=True)

# =========================
# OPTIONAL AUTHORITIES
# =========================
st.markdown("## 3) Additional Authorities (Optional)")
judgments = st.file_uploader("Upload Judgments", type=["pdf","txt"], accept_multiple_files=True)
sections = st.file_uploader("Upload Legal Sections", type=["pdf","txt"], accept_multiple_files=True)
sops = st.file_uploader("Upload SOPs", type=["pdf","txt"], accept_multiple_files=True)
other_inputs = st.text_area("Other Legal Inputs / Notes", height=120)
st.markdown("<hr/>", unsafe_allow_html=True)

# =========================
# PROCESS / OUTPUT
# =========================
st.markdown("## 4) Generate Decision & Order")
lang = st.radio("Order Language", ["English", "Marathi", "Both"], index=0, horizontal=True)

debug_lines: List[str] = []

def preview(name: str, text: str):
    if text.strip():
        st.markdown(f"**Preview — {name} (first 1,500 chars)**")
        st.code(text[:1500] + ("..." if len(text) > 1500 else ""), language="markdown")

def read_text_from_upload(label: str, uploaded_file, manual_text: str) -> str:
    """
    Returns first non-empty text:
      1) manual paste box
      2) OCR/extract from upload
    """
    if manual_text and manual_text.strip():
        debug_lines.append(f"{label}: using manual pasted text.")
        return manual_text.strip()

    if uploaded_file is not None:
        txt, logs = extract_text_any(uploaded_file)
        debug_lines.extend([f"{label}: "+ln for ln in logs])
        if txt.strip():
            debug_lines.append(f"{label}: extracted {len(txt)} chars.")
            return txt.strip()
        else:
            debug_lines.append(f"{label}: EMPTY after extraction/OCR.")
            return ""
    else:
        debug_lines.append(f"{label}: no file uploaded and no manual text.")
        return ""

if st.button("Generate Decision", type="primary", use_container_width=False):
    # Mandatory presence check
    case_txt = read_text_from_upload("CASE", case_file, case_text_manual)
    gr_txt   = read_text_from_upload("GR",   gr_file,   gr_text_manual)

    if not case_txt or not gr_txt:
        st.error("❌ Please ensure **both** Case and GR text are provided (upload and/or paste).")
    else:
        # Build minimal “retrieval” pool (for demo we just store; real system would embed & search)
        sources = []
        if case_txt: sources.append(("Case", case_txt))
        if gr_txt: sources.append(("GR", gr_txt))
        if case_specific: sources.append(("SpecificInput_Case", case_specific))
        if gr_specific: sources.append(("SpecificInput_GR", gr_specific))
        for jf in judgments or []:
            txt, logs = extract_text_any(jf); debug_lines.extend([f"JUDGMENT: "+ln for ln in logs]); 
            if txt: sources.append((f"Judgment:{jf.name}", txt))
        for sf in sections or []:
            txt, logs = extract_text_any(sf); debug_lines.extend([f"SECTION: "+ln for ln in logs]); 
            if txt: sources.append((f"Section:{sf.name}", txt))
        for sp in sops or []:
            txt, logs = extract_text_any(sp); debug_lines.extend([f"SOP: "+ln for ln in logs]); 
            if txt: sources.append((f"SOP:{sp.name}", txt))
        if other_inputs:
            sources.append(("Other", other_inputs))

        # ---- PREVIEWS
        preview("CASE", case_txt)
        preview("GR", gr_txt)

        # ---- “Decision” logic (demo rules; swap with LLM later)
        recommended = "Approve with conditions"
        risks = []
        if "hearing" in case_txt.lower() and "not" in case_txt.lower():
            risks.append("Potential violation of natural justice (hearing).")
        if len(gr_txt) < 80:
            risks.append("GR content appears short — verify correct GR attached.")

        decision = {
            "case_id": case_id,
            "case_type": case_type,
            "subject": relief or case_type,
            "recommended_outcome": recommended,
            "conditions": [
                "Comply strictly with mandatory GR requirements.",
                "Ensure natural justice: hearing opportunity before adverse action."
            ],
            "risks": risks,
            "confidence": 0.82 if not risks else 0.7,
        }
        st.success("✅ Decision generated")
        st.json(decision)

        # Enable order block
        st.session_state["decision"] = decision
        st.session_state["case_txt"] = case_txt
        st.session_state["gr_txt"] = gr_txt

# ORDER GENERATION
if "decision" in st.session_state:
    st.markdown("### Draft Order")
    today = datetime.date.today().strftime("%Y-%m-%d")
    d = st.session_state["decision"]

    # English template
    order_en = f"""**Department**: Zilla Parishad, Chandrapur
**File No.**: {d['case_id']}
**Date**: {today}
**Officer**: {officer}

**Subject**: {d['subject']}

## 1. Background / Facts
Jurisdiction: {jurisdiction}
Cause of Action: {str(st.session_state.get('cause_date', ''))}
Filing Date: {str(st.session_state.get('filing_date', ''))}

## 2. Issues for Determination
- {issues.replace(',', '\\n- ')}

## 3. Applicable Law / Policy (incl. GR)
Relevant Government Resolution(s) and sections relied upon.

## 4. Analysis and Findings (IRAC)
Based on the record and cited GRs, compliance and natural justice must be ensured.

## 5. Decision / Order
It is ordered that: {d['recommended_outcome']}.
Compliance within **7 days**.
"""

    # Marathi template
    order_mr = f"""**विभाग**: जिल्हा परिषद, चंद्रपूर
**फाइल क्रमांक**: {d['case_id']}
**दिनांक**: {today}
**अधिकारी**: {officer}

**विषय**: {d['subject']}

## १. पार्श्वभूमी / तथ्ये
अधिकारक्षेत्र: {jurisdiction}
कारवाईची कारणे: {str(st.session_state.get('cause_date', ''))}
दाखल दिनांक: {str(st.session_state.get('filing_date', ''))}

## २. निश्चित करावयाचे मुद्दे
- {issues.replace(',', '\\n- ')}

## ३. लागू कायदे / धोरण (जीआरसह)
संबंधित सरकारी ठराव व कायदे विचारात घेण्यात आले.

## ४. विश्लेषण व निष्कर्ष (IRAC)
नोंदवही व जीआरच्या आधारे, अनुपालन व नैसर्गिक न्याय सुनिश्चित करणे आवश्यक आहे.

## ५. आदेश
असे आदेशित करण्यात येते की: {d['recommended_outcome']}.
**७ दिवसांच्या** आत अनुपालन करावे.
"""

    if lang in ["English", "Both"]:
        st.subheader("📜 Order (English)")
        st.code(order_en, language="markdown")
        st.download_button("Download Order (EN).md", order_en, file_name=f"{d['case_id']}_order_EN.md")

    if lang in ["Marathi", "Both"]:
        st.subheader("📜 Order (Marathi)")
        st.code(order_mr, language="markdown")
        st.download_button("Download Order (MR).md", order_mr, file_name=f"{d['case_id']}_order_MR.md")

# DEBUG LOGS
with st.expander("🔧 Debug / OCR Logs", expanded=False):
    if debug_lines:
        st.write("\n".join(f"- {ln}" for ln in debug_lines))
    else:
        st.caption("Logs will appear here after processing.")
