if st.button("Generate Decision", type="primary", use_container_width=False):
    # Only file uploads are mandatory now
    if case_file is None or gr_file is None:
        st.error("❌ Please upload both **Case File** and **Government GR** (files are mandatory).")
    else:
        # Try to read OCR/text (manual box remains optional)
        case_txt = read_text_from_upload("CASE", case_file, case_text_manual)
        gr_txt   = read_text_from_upload("GR",   gr_file,   gr_text_manual)

        # Soft handling if OCR yields nothing
        missing_case_text = (not case_txt.strip())
        missing_gr_text   = (not gr_txt.strip())

        warnings = []
        if missing_case_text:
            warnings.append("Case file text not extracted. Consider pasting in the Case text box.")
        if missing_gr_text:
            warnings.append("GR text not extracted. Consider pasting in the GR text box.")

        # Build decision even if text missing (very low confidence)
        recommended = "Approve with conditions"
        risks = []
        if missing_case_text or missing_gr_text:
            risks.append("Primary text content missing for analysis (OCR yielded no text).")

        decision = {
            "case_id": case_id,
            "case_type": case_type,
            "subject": relief or case_type,
            "recommended_outcome": recommended,
            "conditions": [
                "Comply strictly with mandatory GR requirements.",
                "Ensure natural justice: hearing opportunity before adverse action."
            ],
            "risks": risks + warnings,
            "confidence": 0.45 if (missing_case_text or missing_gr_text) else 0.82,
        }

        if warnings:
            for w in warnings:
                st.warning("⚠️ " + w)

        st.success("✅ Decision generated")
        st.json(decision)

        # Previews if we have any text
        if case_txt.strip(): preview("CASE", case_txt)
        if gr_txt.strip():   preview("GR", gr_txt)

        # Enable order block
        st.session_state["decision"] = decision
        st.session_state["case_txt"] = case_txt
        st.session_state["gr_txt"] = gr_txt
