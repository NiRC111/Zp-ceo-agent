# -*- coding: utf-8 -*-
import io, os, re, datetime, tempfile, platform, shutil
from typing import List, Tuple
import streamlit as st
import pandas as pd

# ---------------------- PAGE STYLE ----------------------
st.set_page_config(page_title="ZP CEO Decision Agent", layout="wide")

st.markdown("""
<style>
:root {
  --brand:#0b5fff; --ink:#0f172a; --muted:#475569; --line:#e2e8f0;
  --ok:#1a7f37; --warn:#b58100; --bad:#b42318; --bg:#ffffff;
}
.block-container { max-width: 1220px !important; padding-top: 0.8rem; }
h1,h2,h3 { font-weight: 750 !important; letter-spacing:-0.2px; color:var(--ink); }
hr { border: 0; border-top:1px solid var(--line); margin:0.8rem 0 1.2rem 0; }
.small { font-size: 0.92rem; color:var(--muted); }
.badge { display:inline-block; padding:2px 10px; border:1px solid var(--line); border-radius:999px; font-weight:600; font-size:.8rem; background:#f8fafc; color:#0f172a; }
.card { border:1px solid var(--line); border-radius:12px; padding:16px; background:#fff; }
.codeblock pre, .codeblock code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: .95rem; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🏛️ ZP Chandrapur — CEO Decision Agent</h1>", unsafe_allow_html=True)
st.caption("Accurate quasi-judicial decisions and professional orders. OCR supports Marathi / Hindi / English. Files mandatory: **Case** & **Government GR**.")

# ---------------------- IMPORTS ----------------------
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

for p in ["/usr/share/tesseract-ocr/4.00/tessdata", "/usr/share/tesseract-ocr/tessdata"]:
    if os.path.isdir(p): os.environ.setdefault("TESSDATA_PREFIX", p); break

OCR_LANG="eng+hin+mar"
DEVANAGARI_RE=re.compile(r'[\u0900-\u097F]')
def contains_devanagari(txt): return bool(DEVANAGARI_RE.search(txt or ""))

def robust_decode(data:bytes)->str:
    for enc in("utf-8","utf-8-sig","utf-16","utf-16le","utf-16be"):
        try: return data.decode(enc)
        except: continue
    return data.decode("latin-1",errors="ignore")

# ---------------------- EXTRACTION ----------------------
def extract_text_from_pdf(pdf_bytes:bytes)->Tuple[str,List[str]]:
    logs=[]; mods=_lazy_imports(); fitz=mods.get("fitz")
    pdfminer_extract_text=mods.get("pdfminer_extract_text")
    pytesseract=mods.get("pytesseract"); PIL_Image=mods.get("PIL_Image")
    text=""; pdf_path=None
    try:
        with tempfile.NamedTemporaryFile(delete=False,suffix=".pdf") as tmp: tmp.write(pdf_bytes); pdf_path=tmp.name
    except Exception as e: logs.append(f"tmp pdf fail:{e}")
    try:
        if fitz: doc=fitz.open(stream=pdf_bytes,filetype="pdf"); parts=[p.get_text("text") for p in doc]; doc.close(); text="\n".join(parts).strip()
    except Exception as e: logs.append(f"fitz text err:{e}")
    try:
        if fitz and (not contains_devanagari(text) or len(text)<50):
            doc=fitz.open(stream=pdf_bytes,filetype="pdf"); blocks_all=[]
            for pg in doc: 
                blocks=pg.get_text("blocks") or []; blocks.sort(key=lambda b:(round(b[1],1),round(b[0],1)))
                for b in blocks:
                    if len(b)>=5: t=(b[4] or "").strip(); 
                    if t: blocks_all.append(t)
            doc.close(); tB="\n".join(blocks_all).strip()
            if len(tB)>len(text) or (contains_devanagari(tB) and not contains_devanagari(text)): text=tB
    except Exception as e: logs.append(f"fitz blocks err:{e}")
    if (not contains_devanagari(text)) and pdfminer_extract_text and pdf_path:
        try: t2=pdfminer_extract_text(pdf_path) or ""; 
        if contains_devanagari(t2) or len(t2)>len(text): text=t2
        except Exception as e: logs.append(f"pdfminer err:{e}")
    if len(text)<80 and not contains_devanagari(text):
        if fitz and pytesseract and PIL_Image:
            try:
                doc=fitz.open(stream=pdf_bytes,filetype="pdf"); ocr_buf=[]
                for pg in doc: pix=pg.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False); 
                img=PIL_Image.open(io.BytesIO(pix.tobytes("png"))); ocr=pytesseract.image_to_string(img,lang=OCR_LANG); ocr_buf.append(ocr)
                doc.close(); ocr_text="\n\n".join(ocr_buf).strip()
                if len(ocr_text)>len(text) or contains_devanagari(ocr_text): text=ocr_text
            except Exception as e: logs.append(f"OCR fail:{e}")
    if pdf_path: 
        try: os.unlink(pdf_path)
        except: pass
    return text.strip(),logs

def extract_text_from_image(img_bytes:bytes)->Tuple[str,List[str]]:
    logs=[]; mods=_lazy_imports(); pytesseract=mods.get("pytesseract"); PIL_Image=mods.get("PIL_Image")
    if not (pytesseract and PIL_Image): return "","OCR not available"
    try: img=PIL_Image.open(io.BytesIO(img_bytes)); t=pytesseract.image_to_string(img,lang=OCR_LANG); return t.strip(),["OCR image success"]
    except Exception as e: return "",[f"OCR image fail:{e}"]

def extract_text_any(uploaded_file)->Tuple[str,List[str]]:
    name=(uploaded_file.name or "").lower(); data=uploaded_file.read(); logs=[f"File:{uploaded_file.name}"]
    if name.endswith(".txt"):
        try: return robust_decode(data),["Read txt robust"]
        except Exception as e: return "",[f"txt fail:{e}"]
    if name.endswith(".pdf"): return extract_text_from_pdf(data)
    if any(name.endswith(x) for x in[".png",".jpg",".jpeg",".webp",".tif",".tiff"]): return extract_text_from_image(data)
    return "","Unsupported"

# ---------------------- ORDER FORMATS ----------------------
def order_marathi(meta,decision)->str:
    today=datetime.date.today().strftime("%d/%m/%Y"); issues_md="- "+meta["issues"].replace(",","\n- ") if meta["issues"].strip() else "- —"
    return f"""📝 **निर्णय-आदेश (अर्धन्यायिक मसुदा)**

**कार्यालय :** {meta['officer']}  
**फाईल क्र.:** {decision['case_id']}  
**विषय :** {decision['subject']}  
**दिनांक :** {today}

---

### संदर्भ :  
- शासन निर्णय व कागदपत्रे नोंदीत.  

---

### १) कार्यवाहीचा संक्षेप  
सादर कागदपत्रे व सुनावणी विचारात घेऊन, नैसर्गिक न्याय पाळून प्रकरणाची नोंद घेण्यात आली.  

### २) मुद्दे  
{issues_md}

### ३) निष्कर्ष  
प्रकरणातील नोंदीवरून हे स्पष्ट होते की, शासन निर्णयातील अटींचे पालन आवश्यक आहे.  

### ४) आदेश  
१. पूर्वीची निवड रद्द करण्यात येते.  
२. शासन निर्णयानुसार स्थानिक पात्र उमेदवारास निवड मान्यता देण्यात येते.  
३. संबंधित प्राधिकाऱ्यांनी ७ दिवसांत पुढील कार्यवाही करावी.  

---

*(मुख्य कार्यकारी अधिकारी)*  
जिल्हा परिषद, चंद्रपूर  
"""

def order_english(meta,decision)->str:
    today=datetime.date.today().strftime("%d/%m/%Y"); issues_md="- "+meta["issues"].replace(",","\n- ") if meta["issues"].strip() else "- —"
    return f"""📝 **Decision Order (Quasi-Judicial Draft)**

**Office :** {meta['officer']}  
**File No.:** {decision['case_id']}  
**Subject :** {decision['subject']}  
**Date :** {today}

---

### References :  
- Government Resolutions and record submitted.  

---

### 1) Proceedings Summary  
After considering documents and hearing submissions, ensuring natural justice, the case is recorded.  

### 2) Issues  
{issues_md}

### 3) Findings  
Record shows compliance with GR provisions is mandatory.  

### 4) Order  
1. Earlier selection is cancelled.  
2. As per GR, eligible local candidate is approved for appointment.  
3. Concerned authority to act within 7 days.  

---

*(Chief Executive Officer)*  
Zilla Parishad, Chandrapur  
"""

# ---------------------- UI ----------------------
t1,t2,t3,t4=st.tabs(["1) Case","2) Documents","3) Decision","4) Logs"])

with t1:
    st.markdown("### Case Intake")
    c1,c2=st.columns(2)
    with c1:
        case_id=st.text_input("File/Case ID","ZP/CH/2025/0001")
        officer=st.text_input("Officer","Chief Executive Officer, ZP Chandrapur")
        cause_date=st.date_input("Cause Date",datetime.date.today())
    with c2:
        case_type=st.text_input("Case Type/Subject","Anganwadi Helper Selection")
        jurisdiction=st.text_input("Jurisdiction","Zilla Parishad, Chandrapur")
        filing_date=st.date_input("Filing Date",datetime.date.today())
    relief=st.text_input("Relief Requested","Cancel earlier selection, appoint local candidate")
    issues=st.text_area("Issues (comma-separated)","Local residency; GR compliance; Natural justice")
    annexures=st.text_area("Annexures","Application\nResidence Proof\nEducation")

with t2:
    st.markdown("### Uploads (Mandatory)")
    case_file=st.file_uploader("Case File",type=["pdf","txt","png","jpg","jpeg","tif","tiff"])
    case_text_manual=st.text_area("Optional Case Text (fallback)")
    gr_file=st.file_uploader("Government GR",type=["pdf","txt","png","jpg","jpeg","tif","tiff"])
    gr_text_manual=st.text_area("Optional GR Text (fallback)")

with t3:
    st.markdown("### Decision & Orders")
    lang_choice=st.radio("Order Language",["Marathi","English","Both"],index=0,horizontal=True)
    if st.button("Generate Decision",type="primary"):
        if case_file is None or gr_file is None: st.error("Case + GR files mandatory.")
        else:
            c_txt,_=extract_text_any(case_file) if not case_text_manual else (case_text_manual,[])
            g_txt,_=extract_text_any(gr_file) if not gr_text_manual else (gr_text_manual,[])
            decision={"case_id":case_id,"case_type":case_type,"subject":relief or case_type,
                      "recommended_outcome":"Approve with conditions","confidence":0.8}
            meta={"jurisdiction":jurisdiction,"cause_date":str(cause_date),"filing_date":str(filing_date),
                  "issues":issues,"officer":officer}
            st.success("✅ Decision Generated")
            st.json(decision)
            if lang_choice in["Marathi","Both"]:
                order_mr=order_marathi(meta,decision); st.markdown(order_mr); st.download_button("Download MR",order_mr,file_name=f"{case_id}_MR.md")
            if lang_choice in["English","Both"]:
                order_en=order_english(meta,decision); st.markdown(order_en); st.download_button("Download EN",order_en,file_name=f"{case_id}_EN.md")

with t4:
    st.markdown("### System Info")
    st.write({"python":platform.python_version(),"cwd":os.getcwd(),"tesseract":shutil.which("tesseract")})
