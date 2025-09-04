import io, os, sys, shutil, datetime, tempfile, platform
from typing import List, Tuple

import streamlit as st
import pandas as pd

# =============== BASIC PAGE SETUP (cannot crash) ===============
st.set_page_config(page_title="ZP CEO Decision Agent (OCR)", layout="wide")
st.title("🏛️ ZP Chandrapur — CEO Decision Agent")
st.caption("Mandatory: **Case File** + **Government GR** (files only). OCR: Marathi/Hindi/English via Tesseract. Paste boxes are optional.")

# =============== ENV PREP: Make Tesseract discoverable ===============
# Try common tessdata locations used on Streamlit (Debian 11)
_TESSDATA_CANDIDATES = [
    "/usr/share/tesseract-ocr/4.00/tessdata",
    "/usr/share/tesseract-ocr/tessdata",
    "/usr/share/share/tessdata",  # unlikely, but harmless
]
for p in _TESSDATA_CANDIDATES:
    if os.path.isdir(p):
        os.environ.setdefault("TESSDATA_PREFIX", p)
        break

# =============== VERY DEFENSIVE LAZY IMPORTS ===============
def _lazy_imports():
    mods = {}
    # PyMuPDF (fitz) for PDF text & page raster
    try:
        import fitz
        mods["fitz"] = fitz
    except Exception as e:
        mods["fitz"] = None
        mods["fitz_err"] = str(e)

    # pdfminer.six as secondary extractor
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text
        mods["pdfminer_extract_text"] = pdfminer_extract_text
    except Exception as e:
        mods["pdfminer_extract_text"] = None
        mods["pdfminer_err"] = str(e)

    # pytesseract + PIL for OCR
    try:
        import pytesseract
        from PIL import Image
        mods["pytesseract"] = pytesseract
        mods["PIL_Image"] = Image
    except Exception as e:
        mods["pytesseract"] = None
        mods["PIL_Image"] = None
        mods["pytesseract_err"] = str(e)

    return mods

OCR_LANG = "eng+hin+mar"  # Devanagari + Latin

# =============== DIAGNOSTICS PANEL (TOP) ===============
with st.expander("🧪 Environment Check (auto)", expanded=True):
    cols = st.columns(2)

    with cols[0]:
        st.markdown("**Runtime**")
        st.write({
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cwd": os.getcwd(),
        })
        st.write("**Streamlit**:", st.__version__)
        st.write("**pandas**:", pd.__version__)

        # Binary paths
        tesseract_bin = shutil.which("tesseract")
        st.write("**tesseract path**:", tesseract_bin or "NOT FOUND")
        st.write("**TESSDATA_PREFIX**:", os.environ.get("TESSDATA_PREFIX", "(unset)"))

    mods = _lazy_imports()
    with cols[1]:
        st.markdown("**Python imports**")
        st.write({
            "fitz(PyMuPDF)": "OK" if mods.get("fitz") else f"ERROR: {mods.get('fitz_err','')}",
            "pdfminer.six": "OK" if mods.get("pdfminer_extract_text") else f"ERROR: {mods.get('pdfminer_err','')}",
            "pytesseract": "OK" if mods.get("pytesseract") else f"ERROR: {mods.get('pytesseract_err','')}",
            "Pillow": "OK" if mods.get("PIL_Image") else "ERROR (PIL not loaded)",
        })

        # Try reading tesseract version & langs
        tesseract_status = {}
        if mods.get("pytesseract"):
            try:
                v = mods["pytesseract"].get_tesseract_version()
                tesseract_status["version"] = str(v)
            except Exception as e:
                tesseract_status["version_error"] = str(e)

            # List languages (best-effort; won't crash app if fails)
            try:
                from subprocess import run, PIPE
                out = run(["tesseract", "--list-langs"], stdout=PIPE, stderr=PIPE, text=True)
                tesseract_status["langs_head"] = "\n".join(out.stdout.splitlines()[:15]) or out.stderr[:300]
            except Exception as e:
                tesseract_status["langs_error"] = str(e)

        st.write("**Tesseract**:", tesseract_status or "pytesseract not loaded")

# =============== HELP SIDEBAR ===============
with st.sidebar:
    st.markdown("### Help")
    st.write("• Upload **Case** and **Government GR** — files are mandatory.")
    st.write("• If OCR yields no text, paste into optional boxes.")
    st.write("• Click **Generate Decision** → then review **Order** (EN/MR/Both).")
    st.write("• Use this page’s **Environment Check** and **Debug Logs** if anything goes wrong.")

# =============== CASE INTAKE ===============
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

# =============== DOCUMENTS (MANDATORY FILES) ===============
st.markdown("## 2) Documents — Case & GR (Mandatory)")

st.markdown("#### A) Case Upload  <span class='badge'>Mandatory (file)</span>", unsafe_allow_html=True)
case_file = st.file_uploader("📄 Upload Case File", type=["pdf","txt","png","jpg","jpeg","webp","tif","tiff"], key="case_file")
case_text_manual = st.text_area("Optional: paste Case text (use only if OCR fails)", height=140, key="case_text_manual")
case_specific = st.text_area("Specific Legal Inputs (Case) — sections/clauses/admissions (optional)", height=100, key="case_specific")

st.markdown("#### B) Government GR Upload  <span class='badge'>Mandatory (file)</span>", unsafe_allow_html=True)
gr_file = st.file_uploader("📑 Upload Government GR", type=["pdf","txt","png","jpg","jpeg","webp","tif","tiff"], key="gr_file")
gr_text_manual = st.text_area("Optional: paste GR text (use only if OCR fails)", height=140, key="gr_text_manual")
gr_specific = st.text_area("Specific Legal Inputs (GR) — exact GR numbers/dates/clauses (optional)", height=100, key="gr_specific")

st.markdown("<hr/>", unsafe_allow_html=True)

# =============== OPTIONAL AUTHORITIES ===============
st.markdown("## 3) Additional Authorities (Optional)")
judgments = st.file_uploader("Upload Judgments", type=["pdf","txt"], accept_multiple_files=True)
sections = st.file_uploader("Upload Legal Sections", type=["pdf","txt"], accept_multiple_files=True)
sops = st.file_uploader("Upload SOPs", type=["pdf","txt"], accept_multiple_files=True)
other_inputs = st.text_area("Other Legal Inputs / Notes", height=100)
st.markdown("<hr/>", unsafe_allow_html=True)

# =============== OCR / EXTRACTION LAYER (DEFENSIVE) ===============
def extract_text_from_pdf(pdf_bytes: bytes, dpi: int = 220) -> Tuple[str, List[str]]:
    logs: List[str] = []
    mods = _lazy_imports()
    fitz = mods.get("fitz")
    pdfminer_extract_text = mods.get("pdfminer_extract_text")
    pytesseract = mods.get("pytesseract")
    PIL_Image = mods.get("PIL_Image")

    text = ""
    # Save for pdfminer (needs a path)
    pdf_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            pdf_path = tmp.name
    except Exception as e:
        logs.append(f"tmp pdf write failed: {e}")

    # 1) PyMuPDF direct
    try:
        if fitz is not None:
            logs.append("PyMuPDF: direct extraction.")
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            parts = []
            for page in doc:
                try:
                    parts.append(page.get_text("text"))
                except Exception as e:
                    logs.append(f"fitz page.get_text error: {e}")
            doc.close()
            text = "\n".join(parts).strip()
        else:
            logs.append(f"PyMuPDF not available ({mods.get('fitz_err','')}).")
    except Exception as e:
        logs.append(f"PyMuPDF failed: {e}")

    # 2) pdfminer fallback
    if (not text) and pdfminer_extract_text is not None and pdf_path:
        logs.append("pdfminer: secondary extraction.")
        try:
            t2 = pdfminer_extract_text(pdf_path) or ""
            if len(t2) > len(text):
                text = t2
                logs.append("pdfminer extracted text.")
        except Exception as e:
            logs.append(f"pdfminer failed: {e}")

    # 3) OCR (only if still weak)
    if len(text) < 120:
        if fitz is None:
            logs.append("OCR skipped (fitz missing for raster).")
        elif (pytesseract is None or PIL_Image is None):
            logs.append("OCR skipped (pytesseract/PIL missing).")
        else:
            logs.append("OCR: rasterize pages → Tesseract (eng+hin+mar)")
            try:
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                ocr_buf = []
                for p in doc:
                    zoom = dpi / 72.0
                    mat = fitz.Matrix(zoom, zoom)
                    pix = p.get_pixmap(matrix=mat, alpha=False)
                    img_bytes = pix.tobytes("png")
                    img = PIL_Image.open(io.BytesIO(img_bytes))
                    try:
                        ocr = pytesseract.image_to_string(img, lang="eng+hin+mar")
                        ocr_buf.append(ocr)
                    except Exception as e:
                        logs.append(f"tesseract page OCR error: {e}")
                doc.close()
                ocr_text = "\n\n".join(ocr_buf).strip()
                if len(ocr_text) > len(text):
                    text = ocr_text
                    logs.append("OCR extracted text.")
            except Exception as e:
                logs.append(f"OCR pipeline failed: {e}")

    # cleanup
    if pdf_path:
        try: os.unlink(pdf_path)
        except Exception: pass

    return text.strip(), logs

def extract_text_from_image(img_bytes: bytes) -> Tuple[str, List[str]]:
    logs: List[str] = []
    mods = _lazy_imports()
    pytesseract = mods.get("pytesseract")
    PIL_Image = mods.get("PIL_Image")

    text = ""
    if pytesseract is None or PIL_Image is None:
        logs.append("Image OCR skipped (pytesseract/PIL missing).")
        return "", logs

    try:
        img = PIL_Image.open(io.BytesIO(img_bytes))
        text = pytesseract.image_to_string(img, lang="eng+hin+mar") or ""
        logs.append("Image OCR via Tesseract succeeded.")
    except Exception as e:
        logs.append(f"Image OCR failed: {e}")

    return text.strip(), logs

def extract_text_any(uploaded_file) -> Tuple[str, List[str]]:
    name = (uploaded_file.name or "").lower()
    data = uploaded_file.read()
    logs = [f"File: {uploaded_file.name} ({len(data)} bytes)"]

    try:
        if name.endswith(".txt"):
            text = data.decode("utf-8", errors="ignore")
            logs.append("Read as .txt (utf-8).")
            return text, logs

        if name.endswith(".pdf"):
            txt, more = extract_text_from_pdf(data)
            return txt, logs + more

        if any(name.endswith(ext) for ext in (".png",".jpg",".jpeg",".webp",".tif",".tiff")):
            txt, more = extract_text_from_image(data)
            return txt, logs + more

        logs.append("Unsupported file type.")
        return "", logs
    except Exception as e:
        logs.append(f"extract_text_any error: {e}")
        return "", logs

# =============== UTILS & PREVIEW ===============
debug_lines: List[str] = []

def preview(name: str, text: str):
    if text.strip():
        st.markdown(f"**Preview — {name} (first 1,500 chars)**")
        st.code(text[:1500] + ("..." if len(text) > 1500 else ""), language="markdown")

def read_text_from_upload(label: str, uploaded_file, manual_text: str) -> str:
    """
    Priority:
      1) Optional manual text
      2) OCR/extract from file
      3) Empty string (if OCR fails)
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
        debug_lines.append(f"{label}: file missing (should be mandatory).")
        return ""

# =============== GENERATE DECISION ===============
st.markdown("## 4) Generate Decision & Order")
lang = st.radio("Order Language", ["English", "Marathi", "Both"], index=0, horizontal=True)

if st.button("Generate Decision", type="primary"):
    if case_file is None or gr_file is None:
        st.error("❌ Please upload both **Case File** and **Government GR** (files are mandatory).")
    else:
        case_txt = read_text_from_upload("CASE", case_file, case_text_manual)
        gr_txt   = read_text_from_upload("GR",   gr_file,   gr_text_manual)

        missing_case_text = not case_txt.strip()
        missing_gr_text   = not gr_txt.strip()

        warnings = []
        if missing_case_text:
            warnings.append("Case file text not extracted (OCR couldn’t read). Paste it in the optional Case box if available.")
        if missing_gr_text:
            warnings.append("GR text not extracted (OCR couldn’t read). Paste it in the optional GR box if available.")

        # Simple rules → swap to LLM later if needed
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

        if case_txt.strip(): preview("CASE", case_txt)
        if gr_txt.strip():   preview("GR", gr_txt)

        st.session_state["decision"] = decision
        st.session_state["officer"] = officer
        st.session_state["jurisdiction"] = jurisdiction
        st.session_state["issues"] = issues
        st.session_state["cause_date"] = str(cause_date)
        st.session_state["filing_date"] = str(filing_date)

# =============== GENERATE ORDER ===============
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

    lang = st.radio("Preview language", ["English", "Marathi", "Both"], index=0, horizontal=True, key="preview_lang")

    if lang in ["English", "Both"]:
        st.subheader("📜 Order (English)")
        st.code(order_en, language="markdown")
        st.download_button("Download Order (EN).md", order_en, file_name=f"{d['case_id']}_order_EN.md")

    if lang in ["Marathi", "Both"]:
        st.subheader("📜 Order (Marathi)")
        st.code(order_mr, language="markdown")
        st.download_button("Download Order (MR).md", order_mr, file_name=f"{d['case_id']}_order_MR.md")

# =============== DEBUG LOGS ===============
with st.expander("🔧 Debug / OCR Logs", expanded=False):
    if len(globals().get("debug_lines", [])) > 0:
        st.write("\n".join(f"- {ln}" for ln in debug_lines))
    else:
        st.caption("Logs will appear here after processing.")
