import io, os, json, re
import pdfplumber, pytesseract
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

st.set_page_config(page_title="💳 SureFinance Credit Card Parser", page_icon="💳", layout="wide")

if not groq_key:
    st.error("⚠️ Add GROQ_API_KEY to .env"); st.stop()

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)

# ---------------------------------------------------------
# CUSTOM STYLES (UI)
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

    div[data-testid="stFileUploader"] {
        background-color: #10182F;
        padding: 1em;
        border-radius: 15px;
        border: 1px solid #2b3a67;
        transition: 0.3s;
    }
    div[data-testid="stFileUploader"]:hover {
        border: 1px solid #00E6F6;
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

    section[data-testid="stSidebar"] {
        background-color: #0E1428;
        color: white;
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
st.markdown("<h1>💳 SureFinance Credit Card Statement Parser</h1>", unsafe_allow_html=True)
st.markdown("""
<div class="highlight-text">
✨ <b>AI-Powered Extraction — Summary & Transactions in One Click</b> ✨
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
def extract_text_from_pdf(file_bytes: bytes) -> str:
    texts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            # OCR fallback for unreadable (Axis-like) text
            if len(t.strip()) < 50 or not re.search(r"[A-Za-z]{3,}", t):
                img = page.to_image(resolution=300).original
                t = pytesseract.image_to_string(img)
            texts.append(t)
    return "\n".join(texts)

def query_groq(prompt: str) -> str:
    r = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1, max_tokens=1800
    )
    return r.choices[0].message.content

def clean_ai_output(response_text: str) -> dict:
    try:
        json_part = re.search(r"\{.*\}", response_text, re.S).group(0)
        return json.loads(json_part)
    except Exception:
        return {"raw_output": response_text}

def format_transactions(df: pd.DataFrame):
    if df.empty:
        return df
    df.columns = [c.lower() for c in df.columns]
    if "type" in df.columns:
        df = df.drop(columns=["type"])
    for c in df.columns:
        df[c] = df[c].astype(str).str.replace("\n", " ").str.strip()
    return df

# ---------------------------------------------------------
# SIDEBAR SETTINGS
# ---------------------------------------------------------
with st.sidebar:
    st.header("🧠 Extraction Settings")
    issuer = st.checkbox("Issuer", True)
    customer = st.checkbox("Customer Name", True)
    card_last = st.checkbox("Card Last 4", True)
    card_variant = st.checkbox("Card Variant", True)
    bill_from = st.checkbox("Billing From", True)
    bill_to = st.checkbox("Billing To", True)
    due_date = st.checkbox("Due Date", True)
    total_due = st.checkbox("Total Due", True)
    min_due = st.checkbox("Min Due", True)
    transactions = st.checkbox("Transaction Data", True)

selected_fields = [
    f for f, v in {
        "issuer": issuer, "customer_name": customer,
        "card_last_4_digits": card_last, "credit_card_variant": card_variant,
        "billing_cycle_from": bill_from, "billing_cycle_to": bill_to,
        "payment_due_date": due_date, "total_amount_due": total_due,
        "minimum_amount_due": min_due, "transaction_information": transactions
    }.items() if v
]

# ---------------------------------------------------------
# MAIN SECTION
# ---------------------------------------------------------
uploaded_file = st.file_uploader("📄 Upload Credit Card Statement (PDF)", type=["pdf"])

if uploaded_file and st.button("🚀 Extract Data"):
    with st.spinner("📄 Extracting text and analyzing with AI..."):
        pdf_text = extract_text_from_pdf(uploaded_file.read())

        prompt = f"""
Extract structured data from this credit card statement.
Return valid JSON only with keys:
{', '.join(selected_fields)}.
For each transaction, include: date, description, amount (as in PDF, e.g. "690.00 CR" if written).
Do NOT add any 'type' field or modify values.

Statement text:
{pdf_text[:7000]}
"""
        response = query_groq(prompt)
        result = clean_ai_output(response)

        # --- Show results ---
        st.markdown("### ✅ Extracted Summary")
        if "raw_output" in result:
            st.warning("⚠️ Model returned unstructured data:")
            st.text(result["raw_output"])
        else:
            summary = {k: v for k, v in result.items() if k != "transaction_information"}
            html = "<table class='result-table'><tr>"
            for key in summary.keys():
                html += f"<th>{key}</th>"
            html += "</tr><tr>"
            for value in summary.values():
                html += f"<td>{value}</td>"
            html += "</tr></table>"
            st.markdown(html, unsafe_allow_html=True)

            if "transaction_information" in result:
                tx_df = pd.DataFrame(result["transaction_information"])
                tx_df = format_transactions(tx_df)
                st.markdown("### 🧾 Transaction Details")
                st.dataframe(tx_df, use_container_width=True)

                st.download_button(
                    "💾 Download Transactions (CSV)",
                    tx_df.to_csv(index=False).encode(),
                    file_name=f"{uploaded_file.name}_transactions.csv",
                    mime="text/csv"
                )

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------
st.markdown("""
<div class="footer">
🚀 Developed with ❤️ by <b>Om</b> | AI-based Credit Card Parser | Streamlit ✨
</div>
""", unsafe_allow_html=True)
