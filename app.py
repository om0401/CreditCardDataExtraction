import io
import os
import re
import json
import pdfplumber
import pytesseract
from PIL import Image
import pandas as pd
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

# ---------------------------------------------------------
# SETUP
# ---------------------------------------------------------
load_dotenv()
groq_key = os.getenv("GROQ_API_KEY")

st.set_page_config(
    page_title="💳 Credit Card Statement Parser",
    page_icon="💳",
    layout="wide"
)

# ---------------------------------------------------------
# CUSTOM STYLES
# ---------------------------------------------------------
st.markdown("""
<style>
    .main {
        background: linear-gradient(135deg, #0A0F24 0%, #1B2C78 100%);
        color: #FFFFFF;
        font-family: 'Poppins', sans-serif;
    }
    h1 {
        color: #00E6F6 !important;
        text-align: center;
        font-weight: 800 !important;
        font-size: 2.4em !important;
        margin-bottom: 0.3em !important;
    }
    .highlight-text {
        text-align: center;
        font-size: 22px;
        font-weight: 800;
        background: linear-gradient(90deg, #00E6F6, #007BFF);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 25px;
    }
    .stButton>button {
        background: linear-gradient(90deg, #00E6F6 0%, #007BFF 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.6em 1.5em;
        font-weight: 600;
        transition: 0.2s;
    }
    .stButton>button:hover {
        transform: scale(1.05);
        box-shadow: 0 0 20px rgba(0, 230, 246, 0.5);
    }
    .footer {
        text-align: center;
        font-size: 15px;
        color: #00E6F6;
        margin-top: 40px;
        font-weight: 600;
        animation: pulseGlow 2.5s infinite alternate;
    }
    @keyframes pulseGlow {
        0% {text-shadow: 0 0 8px #00E6F6;}
        50% {text-shadow: 0 0 18px #007BFF;}
        100% {text-shadow: 0 0 8px #00E6F6;}
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------
st.markdown("<h1>💳 Sure Financial Credit Card Parser</h1>", unsafe_allow_html=True)
st.markdown("""
<div class="highlight-text">
<b>AI + Python Hybrid Parser for Credit Card Statements</b><br>
✨ Auto extracts summary & transaction data — even when model output is unstructured ✨
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# VERIFY KEY
# ---------------------------------------------------------
if not groq_key:
    st.error("⚠️ GROQ_API_KEY missing in `.env`")
    st.stop()

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)

# ---------------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------------
uploaded_file = st.file_uploader("📄 Upload Credit Card Statement (PDF)", type=["pdf"])

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF, fallback to OCR if needed."""
    texts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if not t or len(t.strip()) < 40:
                img = page.to_image(resolution=300).original
                t = pytesseract.image_to_string(img)
            texts.append(t)
    return "\n".join(texts)

def query_groq(prompt: str) -> str:
    """Send query to Groq model."""
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1000
    )
    return completion.choices[0].message.content

def fallback_transaction_parser(raw_text: str) -> pd.DataFrame:
    """
    Fallback transaction extraction using regex patterns.
    Matches lines with date, description, and amount.
    """
    pattern = re.compile(
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+([A-Za-z0-9\s\-\&\.,]+?)\s+(-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)"
    )
    transactions = []
    for match in pattern.findall(raw_text):
        date, desc, amt = match
        transactions.append({
            "date": date.strip(),
            "description": desc.strip(),
            "amount": amt.strip(),
            "type": "credit" if "-" in amt else "debit"
        })
    return pd.DataFrame(transactions) if transactions else pd.DataFrame()

# ---------------------------------------------------------
# MAIN LOGIC
# ---------------------------------------------------------
extract_btn = st.button("🚀 Extract Data")

if extract_btn and uploaded_file:
    with st.spinner("📄 Processing your statement..."):
        pdf_bytes = uploaded_file.read()
        pdf_text = extract_text_from_pdf(pdf_bytes)

        # --- API Prompt ---
        prompt = f"""
You are an expert financial document parser.
Extract the following information as JSON:
issuer, customer_name, card_last_4_digits, credit_card_variant,
billing_cycle_from, billing_cycle_to, payment_due_date,
total_amount_due, minimum_amount_due, transaction_information
(transaction_information should be a list of objects with
["date","description","amount","type"]).

Return valid JSON only, no explanations.

Statement text:
{pdf_text[:7000]}
"""
        try:
            response_text = query_groq(prompt)
        except Exception as e:
            st.error(f"❌ Groq API Error: {e}")
            st.stop()

        # Try JSON parsing
        try:
            json_part = response_text.split("{", 1)[1].rsplit("}", 1)[0]
            result = json.loads("{" + json_part + "}")
            structured = True
        except Exception:
            structured = False
            result = {"raw_output": response_text}

        # ---------------------------------------------------------
        # DISPLAY
        # ---------------------------------------------------------
        st.markdown("### ✅ Extracted Results")

        if structured and "transaction_information" in result:
            # --- Summary ---
            summary_data = {
                k: v for k, v in result.items()
                if k != "transaction_information"
            }
            st.markdown("#### 📋 Statement Summary")
            st.dataframe(pd.DataFrame([summary_data]), use_container_width=True)

            # --- Transactions ---
            tx_data = result["transaction_information"]
            if isinstance(tx_data, list) and len(tx_data) > 0:
                st.markdown("#### 🧾 Transaction Details")
                tx_df = pd.DataFrame(tx_data)
                st.dataframe(tx_df, use_container_width=True)
            else:
                st.info("No structured transaction data found.")
        else:
            # --- Fallback mode ---
            st.warning("⚠️ Model returned unstructured output — fallback parsing activated.")
            st.markdown("#### 📋 Extracted Summary (Text Mode)")
            summary_lines = [line for line in pdf_text.split("\n") if any(x in line.lower() for x in [
                "bank", "due", "amount", "name", "credit card"
            ])]
            summary_text = "\n".join(summary_lines[:15])
            st.text(summary_text.strip())

            st.markdown("#### 🧾 Extracted Transaction Table (Regex Mode)")
            tx_df = fallback_transaction_parser(pdf_text)
            if not tx_df.empty:
                st.dataframe(tx_df, use_container_width=True)
            else:
                st.info("No transaction patterns detected. Try clearer PDF text.")

        # --- Download buttons ---
        if structured:
            df = pd.DataFrame([result])
            st.download_button(
                "💾 Download Summary (CSV)",
                df.to_csv(index=False).encode("utf-8"),
                file_name="statement_summary.csv",
                mime="text/csv"
            )

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------
st.markdown("""
<div class="footer">
🚀 Developed with ❤️ by <b>Om</b> | Hybrid Parsing using <b>Groq Llama-3.1</b> + Regex AI | Streamlit ✨
</div>
""", unsafe_allow_html=True)
