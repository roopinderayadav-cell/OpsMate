# OpsMate — Gemini Free-Tier Streamlit Demo

This version uses Google's Gemini Developer API instead of OpenAI.

## Secrets
Do NOT commit your real key to GitHub.

In Streamlit Cloud > App settings > Secrets use:

```toml
GEMINI_API_KEY = "PASTE_YOUR_GEMINI_API_KEY_HERE"
ADMIN_PASSWORD = "Opsmate@2026"
```

## Get a Gemini API key
1. Open Google AI Studio.
2. Sign in with your Google account.
3. Open the API Keys page / click Get API key.
4. Create a new API key.
5. Copy it immediately.
6. Paste it into Streamlit Cloud Secrets, not into GitHub source code.

## Run
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Demo safety
Use synthetic/sample SOPs and screenshots for the free-tier leadership demo. Do not upload confidential company/customer information unless your company has explicitly approved that environment.
