# OpsMate — Streamlit Leadership Demo

OpsMate is a region-aware AI operations knowledge assistant for NORAM, Europe and APAC.

## Demo capabilities
- Agent chat with one clear, evidence-backed answer
- Searches selected Region + Global knowledge only
- PDF, DOCX, XLSX, CSV and TXT upload
- SOP / FAQ / Quality Error / Global document categories
- Screenshot/image question support
- English plus Romanized Hindi/Kannada/Telugu queries
- Source references and confidence
- Helpful / Not Helpful feedback
- Safe fallback when evidence is insufficient
- Admin-only document upload
- Dashboard by region, feedback, topics, common questions and unresolved questions
- Excel export
- SQLite demo database

## Important
This repository is a **leadership-demo architecture**, not the final enterprise deployment.
Streamlit Community Cloud's local filesystem should not be treated as durable enterprise storage.
For production, replace SQLite/local uploads with your office-approved database, object storage and SSO.

## Local setup
1. Install Python 3.12.
2. Clone/download this repository.
3. Create `.streamlit/secrets.toml` from `.streamlit/secrets.toml.example`.
4. Add your OpenAI API key and change the admin password.
5. Run:
   ```
   pip install -r requirements.txt
   streamlit run streamlit_app.py
   ```

## Streamlit Community Cloud
1. Push all files to GitHub, except `secrets.toml`.
2. Create an app in Streamlit Community Cloud.
3. Select `streamlit_app.py` as the entrypoint.
4. In Advanced settings / Secrets, paste:
   ```
   OPENAI_API_KEY = "..."
   ADMIN_PASSWORD = "..."
   ```
5. Deploy.

## Knowledge authority
For the demo, evidence is ranked:
1. Regional SOP
2. Global SOP
3. Regional FAQ
4. Global FAQ
5. Regional Quality Error
6. Global Quality Error
7. Other approved documents

The model is instructed to produce one answer. If authoritative evidence conflicts or is insufficient, OpsMate escalates instead of guessing.

## Suggested production migration
- Microsoft Entra ID / corporate SSO
- PostgreSQL / SQL Server
- pgvector or Azure AI Search
- SharePoint / Blob / approved document store
- role-based access by employee and region
- document versioning + approval workflow
- audit logs and retention controls
- enterprise OpenAI/Azure OpenAI endpoint as approved
