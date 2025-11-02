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

st.set_page_config(page_title="💳 Credit Card Parser", page_icon="💳", layout="wide")

# ---------------------------------------------------------
# CUSTOM STYLES
# ---------------------------------------------------------
st.markdown("""
<style>
    .main {background-color: #0e1117;}
    h1, h2, h3, h4 {color: #e6e6e6;}
    .stButton>button {
        background-color: #007bff;
        color: white;
        border-radius: 10px;
        padding: 0.6em 1.5em;
        font-weight: 600;
        transition: 0.2s;
    }
    .stButton>button:hover {
        background-color: #0056b3;
    }
    .stDownloadButton>button {
        background-color: #28a745;
        color: white;
        border-radius: 10px;
        font-weight: 600;
    }
    .stDownloadButton>button:hover {
        background-color: #218838;
    }
    .result-table {
        border-collapse: collapse;
        width: 100%;
        background-color: #1e222a;
        color: #f8f8f8;
        border-radius: 10px;
        overflow: hidden;
        margin-top: 15px;
    }
    .result-table th {
        background-color: #007bff;
        color: white;
        padding: 10px;
        text-align: center;
    }
    .result-table td {
        padding: 8px 15px;
        text-align: center;
        border: 1px solid #333;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# TITLE
# ---------------------------------------------------------
st.title("💳 Credit Card Statement Parser")
st.caption("Extract key details from your credit-card statement — powered by **Groq’s Llama-3.1-8B-Instant**")

if not groq_key:
    st.error("⚠️ GROQ_API_KEY missing in `.env`. Please add it.")
    st.stop()

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)

# ---------------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------------
uploaded_file = st.file_uploader("📄 Upload Credit Card Statement (PDF)", type=["pdf"])

# ---------------------------------------------------------
# FIELD SELECTION (HORIZONTAL CHECKBOXES)
# ---------------------------------------------------------
st.markdown("#### Select Fields to Extract:")

cols = st.columns(3)
with cols[0]:
    issuer = st.checkbox("Issuer (Bank Name)", value=True, key="issuer")
    customer = st.checkbox("Customer Name", value=True, key="customer")
with cols[1]:
    card_last = st.checkbox("Card Last 4 Digits", key="card")
    bill_from = st.checkbox("Billing Cycle From", key="from")
with cols[2]:
    bill_to = st.checkbox("Billing Cycle To", key="to")
    due_date = st.checkbox("Payment Due Date", key="due")
total_due = st.checkbox("Total Amount Due", value=True, key="total")

selected_fields = [
    f for f, v in {
        "issuer (bank name)": issuer,
        "customer name": customer,
        "card last 4 digits": card_last,
        "billing cycle from": bill_from,
        "billing cycle to": bill_to,
        "payment due date": due_date,
        "total amount due": total_due
    }.items() if v
]

if not selected_fields:
    st.warning("❗ Please select at least one field to extract.")
    st.stop()

# ---------------------------------------------------------
# FUNCTION HELPERS
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
        max_tokens=512
    )
    return completion.choices[0].message.content

# ---------------------------------------------------------
# MAIN WORKFLOW
# ---------------------------------------------------------
extract_btn = st.button("🚀 Extract Data")

if extract_btn and uploaded_file:
    with st.spinner("📄 Reading and analyzing your statement..."):
        pdf_text = extract_text_from_pdf(uploaded_file.read())

        prompt = f"""
You are an expert financial document parser.
Extract the following fields from this credit card statement:
{', '.join(selected_fields)}.

Return only one valid JSON object with these exact keys.

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
        # VISUALIZATION
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
        # DOWNLOAD
        # ---------------------------------------------------------
        df = pd.DataFrame([result])
        st.download_button(
            "💾 Download Extracted Data (CSV)",
            df.to_csv(index=False).encode("utf-8"),
            file_name=f"{uploaded_file.name}_summary.csv",
            mime="text/csv"
        )

st.markdown("---")
st.caption("✨ Built with ❤️ using Streamlit + Groq’s Llama-3.1-8B-Instant")
