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
from datetime import datetime

# ---------------------------------------------------------
# SETUP & CONFIG
# ---------------------------------------------------------
load_dotenv()
groq_key = os.getenv("GROQ_API_KEY")

st.set_page_config(
    page_title="💳 SureFinance Credit Card Parser",
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
        margin-top: -10px;
        margin-bottom: 25px;
    }
    div[data-testid="stFileUploader"] {
        background-color: #10182F;
        padding: 1em;
        border-radius: 15px;
        border: 1px solid #2b3a67;
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
st.markdown("<h1>💳 SureFinance Credit Card Statement Parser</h1>", unsafe_allow_html=True)
st.markdown("""
<div class="highlight-text">
✨ <b>Now extracts transactions, due amounts & card details with AI precision!</b> ✨
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
    card_variant = st.checkbox("Credit Card Variant", value=True)
    card_last = st.checkbox("Card Last 4 Digits", value=True)
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
        "credit card variant": card_variant,
        "card last 4 digits": card_last,
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

# ---------------------------------------------------------
# MAIN WORKFLOW
# ---------------------------------------------------------
extract_btn = st.button("🚀 Extract Data")

if extract_btn and uploaded_file:
    with st.spinner("📄 Reading and analyzing your statement..."):
        pdf_bytes = uploaded_file.read()
        pdf_text = extract_text_from_pdf(pdf_bytes)

        # --- PDF Preview (extra feature)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            st.caption("🖼️ Preview of Page 1:")
            st.image(pdf.pages[0].to_image(resolution=200).original, use_container_width=True)

        prompt = f"""
You are an expert financial document parser.
Extract the following fields from this credit card statement:
{', '.join(selected_fields)}.

If 'transaction information' is selected, extract it as a list of objects with keys:
["date", "description", "amount", "type (credit/debit)"].

Format output strictly as valid JSON only. No text outside the JSON.

Statement text:
{pdf_text[:7000]}
"""
        try:
            response_text = query_groq(prompt)
        except Exception as e:
            st.error(f"❌ Groq API Error: {e}")
            st.stop()

        try:
            json_part = response_text.split("{", 1)[1].rsplit("}", 1)[0]
            result = json.loads("{" + json_part + "}")
        except Exception:
            result = {"raw_output": response_text}

        # ---------------------------------------------------------
        # DISPLAY RESULTS
        # ---------------------------------------------------------
        st.markdown("### ✅ Extracted Summary")

        if "raw_output" in result:
            st.warning("⚠️ Model returned unstructured data:")
            st.text(result["raw_output"])
        else:
            # Transactions
            if "transaction information" in result and isinstance(result["transaction information"], list):
                st.markdown("### 🧾 Transaction Details")
                tx_df = pd.DataFrame(result["transaction information"])
                st.dataframe(tx_df, use_container_width=True)
                result.pop("transaction information", None)

                # --- Optional analytics ---
                try:
                    tx_df['amount'] = tx_df['amount'].astype(float)
                    st.markdown("#### 📊 Transaction Summary")
                    st.write(f"**Total Transactions:** {len(tx_df)}")
                    st.write(f"**Total Spend:** ₹{tx_df[tx_df['type (credit/debit)']=='debit']['amount'].sum():,.2f}")
                    st.write(f"**Total Credits:** ₹{tx_df[tx_df['type (credit/debit)']=='credit']['amount'].sum():,.2f}")
                except:
                    pass

            # Summary info
            html = "<table class='result-table'><tr>"
            for key in result.keys():
                html += f"<th>{key}</th>"
            html += "</tr><tr>"
            for value in result.values():
                html += f"<td>{value}</td>"
            html += "</tr></table>"
            st.markdown(html, unsafe_allow_html=True)

        # ---------------------------------------------------------
        # DOWNLOAD BUTTONS
        # ---------------------------------------------------------
        df = pd.DataFrame([result])
        st.download_button(
            "💾 Download Summary (CSV)",
            df.to_csv(index=False).encode("utf-8"),
            file_name=f"{uploaded_file.name}_summary.csv",
            mime="text/csv"
        )

        if "transaction information" in locals():
            st.download_button(
                "📥 Download Transactions (CSV)",
                tx_df.to_csv(index=False).encode("utf-8"),
                file_name=f"{uploaded_file.name}_transactions.csv",
                mime="text/csv"
            )

        st.success("✅ Extraction complete!")

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------
st.markdown("""
<div class="footer">
🚀 Developed with ❤️ by <b>Om Maurya</b> | Powered by <b>Groq Llama-3.1-8B</b> | Built on Streamlit ✨
</div>
""", unsafe_allow_html=True)
