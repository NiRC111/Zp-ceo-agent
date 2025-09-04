import io, os, datetime, tempfile
from typing import List, Tuple

import streamlit as st
import pandas as pd

# --------------------
# App Setup / Styling
# --------------------
st.set_page_config(page_title="ZP CEO Decision Agent (OCR)", layout="wide")

st.markdown("""
<style>
:root { --brand:#0b5fff; --muted:#64748b; --ok:#1a7f37; --warn:#b58100; --bad:#b42318; }
.block-container { max-width: 1180px; }
h1, h2, h3 { font-weight: 700 !important; }
hr { border: 0; border-top: 1px solid #e2e8f0; margin: 0.75rem 0 1rem 0; }
.badge { display:inline-block; padding:2px 8px; border:1px solid #e2e8f0; border-radius:999px; color:#0f172a; background:#f8fafc; font-size:0.8rem; font-weight:600; }
.note { color: var(--muted); font-size: 0.9rem; }
.ok{color:var(--ok);} .warn{color:var(--warn);} .bad{color:var(--bad);}
textarea { font-family: ui-monospace, Menlo, Consolas, monospace; }
</style>
""", unsafe_allow_html=True)

st.title("🏛️ ZP Chandrapur — CEO Decision Agent")
st.caption("Mandatory: **Case File** + **Government GR** (files only). OCR supports Marathi/Hindi/English. Paste boxes below uploads are optional.")

# --------------------
# Lazy Imports Helper
# --------------------
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
        import easyocr    # fallback OCR (en/hi)
        mods["easyocr"] = easyocr
    except Exception:
        mods["easyocr"] = None
    return mods

OCR_LANG = "eng+hin+mar"  # tesseract language pack selection

# --------------------
# OCR / Extraction
# --------------------
def extract_text_from_pdf(pdf_bytes: bytes, dpi: int = 220) -> Tuple[str, List[str]]:
    """
    Robust PDF text extraction:
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

    # 1) PyMuPDF direct
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

    # 3) OCR on rendered pages
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
                        # easyocr supports en/hi (Marathi not fully supported)
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

# --------------------
# Sidebar Help
# --------------------
with st.sidebar:
    st.markdown("### Help")
    st.write("• Upload **Case** and **Government GR** files (PDF/IMG/TXT).")
    st.write("• Paste boxes are **optional**; use only if OCR fails.")
    st.write("• Click **Generate Decision** → then review and **Download Order** (EN/MR/Both).")
    st.write("• Use **Debug / OCR Logs** at bottom if something fails.")
    st.write("• OCR languages: Marathi/Hindi/English.")

# --------------------
# Case Intake
# --------------------
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

# --------------------
# Documents — Mandatory
# --------------------
st.markdown("## 2) Documents — Case & GR (Mandatory)")

# CASE (file mandatory; text optional)
st.markdown("#### A) Case Upload  <span class='badge'>Mandatory (file)</span>", unsafe_allow_html=True)
case_file = st.file_uploader("📄 Upload Case File", type=["pdf","txt","png","jpg","jpeg","webp","tif","tiff"], key="case_file")
case_text_manual = st.text_area("Optional: paste Case text (use only if OCR fails)", height=160, key="case_text_manual")
case_specific = st.text_area("Specific Legal Inputs (Case) — sections/clauses/admissions (optional)", height=120, key="case_specific")

# GR (file mandatory; text optional)
st.markdown("#### B) Government GR Upload  <span class='badge'>Mandatory (file)</span>", unsafe_allow_html=True)
gr_file = st.file_uploader("📑 Upload Government GR", type=["pdf","txt","png","jpg","jpeg","webp","tif","tiff"], key="gr_file")
gr_text_manual = st.text_area("Optional: paste GR text (use only if OCR fails)", height=160, key="gr_text_manual")
gr_specific = st.text_area("Specific Legal Inputs (GR) — exact GR numbers/dates/clauses (optional)", height=120, key="gr_specific")

st.markdown("<hr/>", unsafe_allow_html=True)

# --------------------
# Optional Authorities
# --------------------
st.markdown("## 3) Additional Authorities (Optional)")
judgments = st.file_uploader("Upload Judgments", type=["pdf","txt"], accept_multiple_files=True)
sections = st.file_uploader("Upload Legal Sections", type=["pdf","txt"], accept_multiple_files=True)
sops = st.file_uploader("Upload SOPs", type=["pdf","txt"], accept_multiple_files=True)
other_inputs = st.text_area("Other Legal Inputs / Notes", height=120)
st.markdown("<hr/>", unsafe_allow_html=True)

# --------------------
# Helpers
# --------------------
debug_lines: List[str] = []

def preview(name: str, text: str):
    if text.strip():
        st.markdown(f"**Preview — {name} (first 1,500 chars)**")
        st.code(text[:1500] + ("..." if len(text) > 1500 else ""), language="markdown")

def read_text_from_upload(label: str, uploaded_file, manual_text: str) -> str:
    """
    Order of preference:
      1) manual pasted text (optional)
      2) OCR/extract from uploaded file
      3) empty string (if OCR fails)
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
        debug_lines.append(f"{label}: no file uploaded.")
        return ""

# --------------------
# Generate Decision
# --------------------
st.markdown("## 4) Generate Decision & Order")
lang = st.radio("Order Language", ["English", "Marathi", "Both"], index=0, horizontal=True)

if st.button("Generate Decision", type="primary"):
    # Only files are mandatory
    if case_file is None or gr_file is None:
        st.error("❌ Please upload both **Case File** and **Government GR** (files are mandatory).")
    else:
        # Try to read OCR/text; paste fields are optional
        case_txt = read_text_from_upload("CASE", case_file, case_text_manual)
        gr_txt   = read_text_from_upload("GR",   gr_file,   gr_text_manual)

        missing_case_text = (not case_txt.strip())
        missing_gr_text   = (not gr_txt.strip())

        warnings = []
        if missing_case_text:
            warnings.append("Case file text not extracted (OCR could not read). You can paste it in the optional Case box.")
        if missing_gr_text:
            warnings.append("GR text not extracted (OCR could not read). You can paste it in the optional GR box.")

        # Decision (rule-based baseline; swap with LLM if desired)
        recommended = "Approve with conditions"
        risks = []
        if "hearing" in case_txt.lower() and "not" in case_txt.lower():
            risks.append("Potential violation of natural justice (hearing).")
        if len(gr_txt) < 80 and not missing_gr_text:
            risks.append("GR content appears short — verify correct GR attached.")

        decision = {
            "case_id": case_id,
            "case_type": case_type,
            "subject": relief or case_type,
            "recommended_outcome": recommended,
            "conditions": [
                "Comply strictly with mandatory GR requirements.",
                "Ensure natural justice: provide hearing opportunity before adverse action."
            ],
            "risks": risks + warnings,
            "confidence": 0.45 if (missing_case_text or missing_gr_text) else 0.82,
        }

        for w in warnings:
            st.warning("⚠️ " + w)

        st.success("✅ Decision generated")
        st.json(decision)

        # Previews (if text exists)
        if case_txt.strip(): preview("CASE", case_txt)
        if gr_txt.strip():   preview("GR", gr_txt)

        # Store for order generation
        st.session_state["decision"] = decision
        st.session_state["case_txt"] = case_txt
        st.session_state["gr_txt"] = gr_txt
        st.session_state["officer"] = officer
        st.session_state["jurisdiction"] = jurisdiction
        st.session_state["issues"] = issues
        st.session_state["cause_date"] = str(cause_date)
        st.session_state["filing_date"] = str(filing_date)

# --------------------
# Generate Order
# --------------------
if "decision" in st.session_state:
    st.markdown("### Draft Order")
    today = datetime.date.today().strftime("%Y-%m-%d")
    d = st.session_state["decision"]

    officer_s = st.session_state.get("officer", "Chief Executive Officer, ZP Chandrapur")
    jurisdiction_s = st.session_state.get("jurisdiction", "Zilla Parishad, Chandrapur")
    issues_s = st.session_state.get("issues", "")
    cause_s = st.session_state.get("cause_date", "")
    filing_s = st.session_state.get("filing_date", "")

    order_en = f"""**Department**: Zilla Parishad, Chandrapur
**File No.**: {d['case_id']}
**Date**: {today}
**Officer**: {officer_s}

**Subject**: {d['subject']}

## 1. Background / Facts
Jurisdiction: {jurisdiction_s}
Cause of Action: {cause_s}
Filing Date: {filing_s}

## 2. Issues for Determination
- {issues_s.replace(',', '\\n- ')}

## 3. Applicable Law / Policy (incl. GR)
Relevant Government Resolution(s) and sections relied upon.

## 4. Analysis and Findings (IRAC)
Based on the record and cited GRs, compliance and natural justice must be ensured.

## 5. Decision / Order
It is ordered that: {d['recommended_outcome']}.
Compliance within **7 days**.
"""

    order_mr = f"""**विभाग**: जिल्हा परिषद, चंद्रपूर
**फाइल क्रमांक**: {d['case_id']}
**दिनांक**: {today}
**अधिकारी**: {officer_s}

**विषय**: {d['subject']}

## १. पार्श्वभूमी / तथ्ये
अधिकारक्षेत्र: {jurisdiction_s}
कारवाईची कारणे: {cause_s}
दाखल दिनांक: {filing_s}

## २. निश्चित करावयाचे मुद्दे
- {issues_s.replace(',', '\\n- ')}

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

# --------------------
# Debug / OCR Logs
# --------------------
with st.expander("🔧 Debug / OCR Logs", expanded=False):
    if debug_lines:
        st.write("\n".join(f"- {ln}" for ln in debug_lines))
    else:
        st.caption("Logs will appear here after processing.")
