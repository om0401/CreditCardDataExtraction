import io, os, json, re
import pdfplumber, pytesseract
from PIL import Image
import pandas as pd
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

# --- Setup ---
load_dotenv()
groq_key = os.getenv("GROQ_API_KEY")
st.set_page_config(page_title="💳 SureFinance Parser", page_icon="💳", layout="wide")

if not groq_key:
    st.error("⚠️ Add GROQ_API_KEY to .env"); st.stop()

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)

# --- Helpers ---
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Try text layer first, else OCR fallback."""
    texts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            # if unreadable (Axis Bank style), fallback to OCR
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
    """Extract JSON from model output even if wrapped in text."""
    try:
        json_part = re.search(r"\{.*\}", response_text, re.S).group(0)
        data = json.loads(json_part)
        return data
    except Exception:
        return {"raw_output": response_text}

def format_transactions(df: pd.DataFrame):
    if df.empty: return df
    df.columns = [c.lower() for c in df.columns]
    # remove type column entirely if exists
    if "type" in df.columns:
        df = df.drop(columns=["type"])
    # strip whitespace & newlines
    for c in df.columns:
        df[c] = df[c].astype(str).str.replace("\n", " ").str.strip()
    return df

# --- Sidebar ---
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

# --- File Upload ---
uploaded_file = st.file_uploader("📄 Upload Credit Card Statement", type=["pdf"])

# --- Main Logic ---
if uploaded_file and st.button("🚀 Extract Data"):
    with st.spinner("Extracting text and analyzing..."):
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

        st.markdown("### ✅ Extracted Summary")
        if "raw_output" in result:
            st.warning("⚠️ Model returned unstructured data:")
            st.text(result["raw_output"])
        else:
            summary = {k:v for k,v in result.items() if k!="transaction_information"}
            st.dataframe(pd.DataFrame([summary]))

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

# --- Footer ---
st.markdown("""
<div style='text-align:center;color:#00E6F6;margin-top:30px'>
🚀 Developed with ❤️ by <b>Om</b> | AI-based Credit Card Parser | Streamlit ✨
</div>
""", unsafe_allow_html=True)
