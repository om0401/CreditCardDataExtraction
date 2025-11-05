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

st.set_page_config(page_title="💳 Credit Card Statement Parser", page_icon="💳", layout="wide")

if not groq_key:
    st.error("⚠️ GROQ_API_KEY missing in `.env`. Please add it.")
    st.stop()

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)

# ---------------------------------------------------------
# HELPERS
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

def clean_transaction_data(df: pd.DataFrame) -> pd.DataFrame:
    """Fix missing CR/DR, negative signs, or malformed transactions."""
    if df.empty:
        return df

    df.columns = [c.lower().strip() for c in df.columns]

    # Normalize 'type' or infer from amount
    if "type" in df.columns:
        df["type"] = df["type"].fillna("").str.lower()
        df["type"] = df["type"].apply(lambda x: "credit" if "cr" in x else ("debit" if "dr" in x else "debit"))
    else:
        df["type"] = df["amount"].apply(lambda x: "credit" if str(x).startswith("-") else "debit")

    # Clean amount
    df["amount"] = (
        df["amount"].astype(str)
        .str.replace(",", "")
        .str.replace("₹", "")
        .str.extract(r"([\d\.]+)")[0]
        .astype(float)
    )

    # Fix multi-line merges
    df["description"] = df["description"].str.replace("\n", " ").str.strip()
    df = df.drop_duplicates()
    return df

def query_groq(prompt: str) -> dict:
    """Query Groq model with enhanced prompt."""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1500
    )
    text = response.choices[0].message.content
    try:
        json_part = text.split("{", 1)[1].rsplit("}", 1)[0]
        return json.loads("{" + json_part + "}")
    except Exception:
        return {"raw_output": text}

# ---------------------------------------------------------
# SIDEBAR
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
# MAIN EXTRACTION LOGIC
# ---------------------------------------------------------
if uploaded_file and st.button("🚀 Extract Data"):
    with st.spinner("Analyzing statement with AI..."):
        pdf_text = extract_text_from_pdf(uploaded_file.read())

        # Enhanced LLM prompt
        prompt = f"""
You are a financial statement parser.
Extract the following fields as JSON:
{', '.join(selected_fields)}.

If there are transactions, output as:
"transaction_information": [
  {{
    "date": "DD/MM/YYYY",
    "description": "text",
    "amount": "numeric",
    "type": "credit/debit"
  }}
]

If CR/DR not mentioned, infer type based on description keywords
like 'payment received', 'refund' = credit, otherwise debit.

Return only valid JSON, no markdown.

Statement:
{pdf_text[:7000]}
"""
        result = query_groq(prompt)

        # ---------------------------------------------------------
        # DISPLAY SUMMARY
        # ---------------------------------------------------------
        st.markdown("### ✅ Extracted Summary")
        if "raw_output" in result:
            st.warning("⚠️ Model returned unstructured data:")
            st.text(result["raw_output"])
        else:
            summary_data = {k: v for k, v in result.items() if k != "transaction_information"}
            html = "<table class='result-table'><tr>"
            for k in summary_data.keys():
                html += f"<th>{k}</th>"
            html += "</tr><tr>"
            for v in summary_data.values():
                html += f"<td>{v}</td>"
            html += "</tr></table>"
            st.markdown(html, unsafe_allow_html=True)

            # ---------------------------------------------------------
            # DISPLAY TRANSACTIONS
            # ---------------------------------------------------------
            if "transaction_information" in result and isinstance(result["transaction_information"], list):
                st.markdown("### 🧾 Transaction Details (AI Extracted)")
                tx_df = pd.DataFrame(result["transaction_information"])
                tx_df = clean_transaction_data(tx_df)
                st.dataframe(tx_df, use_container_width=True)

                st.download_button(
                    "💾 Download Transactions (CSV)",
                    tx_df.to_csv(index=False).encode("utf-8"),
                    file_name=f"{uploaded_file.name}_transactions.csv",
                    mime="text/csv"
                )

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------
st.markdown("""
<div class="footer">
🚀 Developed with ❤️ by <b>Om</b> | Groq + Smart Post-Processing | Streamlit ✨
</div>
""", unsafe_allow_html=True)
