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
# SETUP & CONFIG
# ---------------------------------------------------------
load_dotenv()
groq_key = os.getenv("GROQ_API_KEY")

st.set_page_config(
    page_title="💳 Credit Card Statement Parser",
    page_icon="💳",
    layout="wide"
)

# ---------------------------------------------------------
# CUSTOM STYLES (UI ONLY)
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
        letter-spacing: 0.4px;
        animation: fadeIn 1.5s ease-in-out;
        margin-top: -10px;
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
        box-shadow: 0 0 10px rgba(0, 230, 246, 0.3);
    }
    .stButton>button:hover {
        transform: scale(1.05);
        box-shadow: 0 0 20px rgba(0, 230, 246, 0.5);
    }

    .result-table {
        border-collapse: collapse;
        width: 100%;
        background-color: #11182E;
        color: #f8f8f8;
        border-radius: 12px;
        overflow: hidden;
        margin-top: 15px;
        box-shadow: 0 0 15px rgba(0, 0, 0, 0.4);
    }
    .result-table th {
        background-color: #007BFF;
        color: white;
        padding: 12px;
        text-align: center;
    }
    .result-table td {
        padding: 10px 15px;
        text-align: center;
        border: 1px solid #2a3b6b;
    }

    section[data-testid="stSidebar"] {
        background-color: #0E1428;
        color: white;
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
st.markdown("<h1>💳 Sure Financial Credit Card Statement Parser</h1>", unsafe_allow_html=True)
st.markdown("""
<div class="highlight-text">
✨ <b>Extracts summary using Groq API and transactions using local pattern recognition!</b> ✨
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# VERIFY KEY
# ---------------------------------------------------------
if not groq_key:
    st.error("⚠️ GROQ_API_KEY missing in `.env`. Please add it.")
    st.stop()

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)

# ---------------------------------------------------------
# SIDEBAR FIELD SELECTION
# ---------------------------------------------------------
with st.sidebar:
    st.header("🧠 Extraction Settings")
    st.caption("Select the fields you want to extract:")

    issuer = st.checkbox("Issuer (Bank Name)", value=True)
    customer = st.checkbox("Customer Name", value=True)
    card_last = st.checkbox("Card Last 4 Digits", value=True)
    card_variant = st.checkbox("Credit Card Variant", value=True)
    bill_from = st.checkbox("Billing Cycle From", value=True)
    bill_to = st.checkbox("Billing Cycle To", value=True)
    due_date = st.checkbox("Payment Due Date", value=True)
    total_due = st.checkbox("Total Amount Due", value=True)
    min_due = st.checkbox("Minimum Amount Due", value=True)
    transactions = st.checkbox("Transaction Information", value=True)

selected_fields = [
    f for f, v in {
        "issuer (bank name)": issuer,
        "customer name": customer,
        "card last 4 digits": card_last,
        "credit card variant": card_variant,
        "billing cycle from": bill_from,
        "billing cycle to": bill_to,
        "payment due date": due_date,
        "total amount due": total_due,
        "minimum amount due": min_due,
        "transaction information": transactions
    }.items() if v
]

# ---------------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------------
uploaded_file = st.file_uploader("📄 Upload Credit Card Statement (PDF)", type=["pdf"])

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def extract_text_from_pdf(file_bytes: bytes) -> str:
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
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=800
    )
    return completion.choices[0].message.content

def extract_transactions_regex(text: str):
    """Regex-based fallback for transaction table extraction."""
    pattern = re.compile(
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+([A-Za-z0-9\s\-\&\.,]+?)\s+(-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)"
    )
    transactions = []
    for match in pattern.findall(text):
        date, desc, amt = match
        amt_clean = amt.replace(",", "")
        transactions.append({
            "date": date.strip(),
            "description": desc.strip(),
            "amount": amt_clean,
            "type": "credit" if "-" in amt_clean else "debit"
        })
    return pd.DataFrame(transactions) if transactions else None

# ---------------------------------------------------------
# MAIN WORKFLOW
# ---------------------------------------------------------
extract_btn = st.button("🚀 Extract Data")

if extract_btn and uploaded_file:
    with st.spinner("📄 Reading and analyzing your statement..."):
        pdf_text = extract_text_from_pdf(uploaded_file.read())

        # --- Prompt for Groq (only for summary fields) ---
        prompt = f"""
You are a financial document parser.
Extract only the following fields from this credit card statement as valid JSON:
issuer, customer_name, card_last_4_digits, credit_card_variant,
billing_cycle_from, billing_cycle_to, payment_due_date,
total_amount_due, minimum_amount_due.

Return one valid JSON object. Do not include transaction data.

Statement text:
{pdf_text[:7000]}
"""
        try:
            response_text = query_groq(prompt)
        except Exception as e:
            st.error(f"❌ Groq API Error: {e}")
            st.stop()

        # Parse summary data
        try:
            json_part = response_text.split("{", 1)[1].rsplit("}", 1)[0]
            result = json.loads("{" + json_part + "}")
        except Exception:
            result = {"raw_output": response_text}

        # ---------------------------------------------------------
        # SHOW SUMMARY TABLE
        # ---------------------------------------------------------
        st.markdown("### ✅ Extracted Summary")

        if "raw_output" in result:
            st.warning("⚠️ Model returned unstructured data:")
            st.text(result["raw_output"])
        else:
            html = "<table class='result-table'><tr>"
            for key in result.keys():
                html += f"<th>{key}</th>"
            html += "</tr><tr>"
            for value in result.values():
                html += f"<td>{value}</td>"
            html += "</tr></table>"
            st.markdown(html, unsafe_allow_html=True)

        # ---------------------------------------------------------
        # TRANSACTION DATA EXTRACTION (Regex-based)
        # ---------------------------------------------------------
        if transactions:
            st.markdown("### 🧾 Transaction Details (Extracted via Regex)")
            tx_df = extract_transactions_regex(pdf_text)
            if tx_df is not None and not tx_df.empty:
                st.dataframe(tx_df, use_container_width=True)
            else:
                st.warning("⚠️ No clear transaction patterns detected.")

        # ---------------------------------------------------------
        # DOWNLOAD BUTTON
        # ---------------------------------------------------------
        df = pd.DataFrame([result])
        st.download_button(
            "💾 Download Extracted Summary (CSV)",
            df.to_csv(index=False).encode("utf-8"),
            file_name=f"{uploaded_file.name}_summary.csv",
            mime="text/csv"
        )

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------
st.markdown("""
<div class="footer">
🚀 Developed with ❤️ by <b>Om</b> | Hybrid: Groq API + Regex Parser | Streamlit ✨
</div>
""", unsafe_allow_html=True)
