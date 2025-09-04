import streamlit as st
import datetime
import pandas as pd

# -------------------
# Page Config
# -------------------
st.set_page_config(page_title="ZP CEO Decision Agent", layout="wide")

st.title("🏛️ ZP Chandrapur — CEO Decision Agent")
st.caption("Mandatory: Case File + Government GR. Others optional.")

# -------------------
# Case Intake
# -------------------
st.header("1) Case Intake")
col1, col2 = st.columns(2)
with col1:
    case_id = st.text_input("Case ID", "ZP/CH/2025/0001")
    officer = st.text_input("Officer", "Chief Executive Officer, ZP Chandrapur")
    cause_date = st.date_input("Cause of Action Date", value=datetime.date.today())
with col2:
    case_type = st.text_input("Type of Case / Subject", "Tender appeal")
    jurisdiction = st.text_input("Jurisdiction", "Zilla Parishad, Chandrapur")
    filing_date = st.date_input("Filing Date", value=datetime.date.today())

relief = st.text_input("Requested Relief", "Set aside rejection and reconsider award")
issues = st.text_area("Issues (comma-separated)", "eligibility under Rule 12(3), natural justice hearing")
annexures = st.text_area("Annexures (one per line)", "ApplicationForm\nIDProof\nFeeReceipt")

# -------------------
# Documents Upload
# -------------------
st.header("2) Documents Upload (Mandatory)")
case_file = st.file_uploader("📄 Upload Case File", type=["pdf", "txt", "png", "jpg", "jpeg"])
gr_file = st.file_uploader("📑 Upload Government GR", type=["pdf", "txt", "png", "jpg", "jpeg"])
case_specific = st.text_area("Specific Legal Inputs (Case)")
gr_specific = st.text_area("Specific Legal Inputs (GR)")

# -------------------
# Optional Authorities
# -------------------
st.header("3) Additional Authorities (Optional)")
judgments = st.file_uploader("Upload Judgments", type=["pdf", "txt"], accept_multiple_files=True)
sections = st.file_uploader("Upload Legal Sections", type=["pdf", "txt"], accept_multiple_files=True)
sops = st.file_uploader("Upload SOPs", type=["pdf", "txt"], accept_multiple_files=True)
other_inputs = st.text_area("Other Legal Inputs / Notes")

# -------------------
# Generate Decision & Order
# -------------------
st.header("4) Generate Decision and Order")
lang = st.radio("Select Order Language", ["English", "Marathi", "Both"], index=0)

if st.button("Generate Decision"):
    if not case_file or not gr_file:
        st.error("❌ Please upload both Case File and Government GR.")
    else:
        # Demo AI Decision (replace later with real AI call)
        decision = {
            "case_id": case_id,
            "case_type": case_type,
            "subject": relief,
            "recommended_outcome": "Approve with conditions",
            "conditions": ["Comply with mandatory GR requirements", "Provide natural justice hearing"],
            "confidence": 0.82
        }
        st.success("✅ Decision Generated")
        st.json(decision)

        # Draft Orders
        today = datetime.date.today().strftime("%Y-%m-%d")
        order_text_en = f"""
Department: Zilla Parishad, Chandrapur
File No.: {case_id}
Date: {today}
Officer: {officer}

Subject: {relief}

Decision: The application is approved in principle subject to compliance with cited GRs and ensuring natural justice.
"""
        order_text_mr = f"""
विभाग: जिल्हा परिषद, चंद्रपूर
फाइल क्रमांक: {case_id}
दिनांक: {today}
अधिकारी: {officer}

विषय: {relief}

आदेश: अर्ज तत्त्वतः मंजूर करण्यात येत असून संबंधित जीआरचे पालन व नैसर्गिक न्याय दिल्यानंतर अंतिम निर्णय करण्यात येईल.
"""

        if lang in ["English", "Both"]:
            st.subheader("📜 Order (English)")
            st.text(order_text_en)
        if lang in ["Marathi", "Both"]:
            st.subheader("📜 Order (Marathi)")
            st.text(order_text_mr)

        # Citations (demo only)
        df = pd.DataFrame([
            {"Source": "Government GR", "Clause": gr_specific or "N/A"},
            {"Source": "Case File", "Clause": case_specific or "N/A"}
        ])
        st.subheader("📊 Citations")
        st.dataframe(df)
