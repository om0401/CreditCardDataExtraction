import io
import os
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
st.markdown("<h1>💳 Sure Financial Credit Card Parser</h1>", unsafe_allow_html=True)
st.markdown("""
<div class="highlight-text">
✨ <b>AI-powered parsing — structured summary & transactions in one click</b> ✨
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# VERIFY API KEY
# ---------------------------------------------------------
if not groq_key:
    st.error("⚠️ GROQ_API_KEY missing in `.env`. Please add it.")
    st.stop()

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)

# ---------------------------------------------------------
# SIDEBAR SETTINGS
# ---------------------------------------------------------
with st.sidebar:
    st.header("🧠 Extraction Settings")
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
        "issuer": issuer,
        "customer_name": customer,
        "card_last_4_digits": card_last,
        "credit_card_variant": card_variant,
        "billing_cycle_from": bill_from,
        "billing_cycle_to": bill_to,
        "payment_due_date": due_date,
        "total_amount_due": total_due,
        "minimum_amount_due": min_due,
        "transaction_information": transactions
    }.items() if v
]

# ---------------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------------
uploaded_file = st.file_uploader("📄 Upload Credit Card Statement (PDF)", type=["pdf"])

# ---------------------------------------------------------
# FUNCTIONS
# ---------------------------------------------------------
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from each page using pdfplumber + OCR fallback"""
    texts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if not t or len(t.strip()) < 40:
                img = page.to_image(resolution=300).original
                t = pytesseract.image_to_string(img)
            texts.append(t)
    return "\n".join(texts)

def query_groq_for_json(pdf_text: str) -> dict:
    """Ask Groq model to return structured JSON data."""
    prompt = f"""
You are a financial data extraction system.
From this credit card statement, extract the following fields:
{', '.join(selected_fields)}.

For "transaction_information", return a list of dictionaries with keys:
["date", "description", "amount", "type (credit/debit)"].

Return a **valid JSON** object only, no markdown or explanations.

Statement text:
{pdf_text[:7000]}
"""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1500
    )
    response_text = response.choices[0].message.content

    # Extract JSON safely
    try:
        json_part = response_text.split("{", 1)[1].rsplit("}", 1)[0]
        result = json.loads("{" + json_part + "}")
        return result
    except Exception:
        return {"raw_output": response_text}

# ---------------------------------------------------------
# MAIN WORKFLOW
# ---------------------------------------------------------
extract_btn = st.button("🚀 Extract Data")

if extract_btn and uploaded_file:
    with st.spinner("📄 Reading and analyzing your statement..."):
        pdf_text = extract_text_from_pdf(uploaded_file.read())

        result = query_groq_for_json(pdf_text)

        # SUMMARY TABLE
        st.markdown("### ✅ Extracted Summary")
        if "raw_output" in result:
            st.warning("⚠️ Model returned unstructured data:")
            st.text(result["raw_output"])
        else:
            summary_result = {k: v for k, v in result.items() if k != "transaction_information"}

            html = "<table class='result-table'><tr>"
            for key in summary_result.keys():
                html += f"<th>{key}</th>"
            html += "</tr><tr>"
            for value in summary_result.values():
                html += f"<td>{value}</td>"
            html += "</tr></table>"
            st.markdown(html, unsafe_allow_html=True)

            # TRANSACTION TABLE
            if "transaction_information" in result and isinstance(result["transaction_information"], list):
                st.markdown("### 🧾 Transaction Details")
                tx_df = pd.DataFrame(result["transaction_information"])
                st.dataframe(tx_df, use_container_width=True)

                # Optional CSV download
                st.download_button(
                    "📥 Download Transactions (CSV)",
                    tx_df.to_csv(index=False).encode("utf-8"),
                    file_name=f"{uploaded_file.name}_transactions.csv",
                    mime="text/csv"
                )

        # DOWNLOAD SUMMARY
        df_summary = pd.DataFrame([result])
        st.download_button(
            "💾 Download Summary (CSV)",
            df_summary.to_csv(index=False).encode("utf-8"),
            file_name=f"{uploaded_file.name}_summary.csv",
            mime="text/csv"
        )

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------
st.markdown("""
<div class="footer">
🚀 Developed with ❤️ by <b>Om</b> | AI Extraction Powered by <b>Groq Llama-3.1</b> | Streamlit ✨
</div>
""", unsafe_allow_html=True)
