💳 Credit Card Data Extraction App — Usage Guide live: https://creditcarddataextraction.streamlit.app/
 📘 Overview
The Credit Card Data Extraction App is a Streamlit web application that automatically extracts key information such as Issuer Bank Name, Customer Name, Billing Cycle, Payment Due Date, and Total Amount Due from PDF statements. It uses Groq’s Llama-3.1-8B-Instant model (OpenAI-compatible) to interpret complex statement formats intelligently.
⚙️ 1. Installation 🧩 Prerequisites
Python 3.9 or higher
pip (Python package manager)
A Groq API key (free — create at https://console.groq.com/keys )
🧰 Clone or Download git clone https://github.com/om0401/CreditCardDataExtraction.git cd CreditCardDataExtraction
📦 Install dependencies pip install -r requirements.txt
🔐 Add API Key (locally)
Create a .env file in the project root:
GROQ_API_KEY = gsk_your_actual_key_here
🌐 2. Running the App Locally
Run this command:
streamlit run app.py
Then open your browser at 👉 http://localhost:8501
🧠 3. How to Use the App Step-by-Step
1️⃣ Launch the App Run the command above or open your Streamlit Cloud link.
2️⃣ Upload your Credit Card PDF
Click Browse files or drag-and-drop your statement (PDF).
The file is processed locally for text extraction using pdfplumber (and OCR via pytesseract for scanned PDFs).
3️⃣ Select Fields to Extract
Choose the fields you want using the horizontal checkboxes:
Issuer (Bank Name)
Customer Name
Card Last 4 Digits
Billing Cycle From / To
Payment Due Date
Total Amount Due
You must select at least one field (the app validates this).
4️⃣ Click “🚀 Extract Data”
The app sends a secure text query to Groq’s API (using your GROQ_API_KEY).
The AI reads and interprets the PDF contents.
5️⃣ View Results
Extracted information appears in a horizontal table.
All values are neatly formatted for easy reading.
6️⃣ Download Results
Choose from:
CSV → For Excel or further analysis
TXT → For plain text storage
JSON → For structured data integration
☁️ 4. Deploying on Streamlit Cloud Steps
Push this folder to your GitHub (already done ✅).
Go to https://share.streamlit.io
Click New App → Connect GitHub
Choose:
Repository: om0401/CreditCardDataExtraction
Branch: main
File path: app.py
In Settings → Secrets, add:
GROQ_API_KEY = "gsk_your_actual_key_here"
Click Deploy
Your live app will be accessible at:
https://om0401-creditcarddataextraction.streamlit.app/
🎨 5. App UI Overview Section Description Header Title and description Upload Area Upload one PDF at a time Field Selection Horizontal checkboxes to choose what to extract Extract Button Triggers Groq LLM processing Results Section Displays extracted data in horizontal table 
 

🧠 7. Technologies Used
Component	Purpose
Streamlit	Web UI framework
pdfplumber	Extracts text from PDFs
pytesseract	OCR for scanned PDFs
Groq API	AI text understanding
pandas	Output formatting
dotenv	Secure key loadin

🧾 8. Example Output
issuer (bank name)	customer name	total amount due
HDFC Bank	Mr. Rupal Patel	₹13,429.57

 
🏁 10. Credits
Developed by Om Built with ❤️ using Python, Streamlit, and Groq’s AI API
Pdf 

