# EngageAI — Final Planning Aligned MVP

This folder is aligned to the final EngageAI planning document. The old Representative and Lead tables are removed. The locked visitor lifecycle is `Visitor -> Needs Follow-Up -> Meeting Scheduled`, and meeting escalation uses three n8n-backed tools.

## Run
1. Copy `.env.example` to `.env` and fill PostgreSQL, Azure, Gemini embedding, Azure AI Search, and n8n values.
2. Install `requirements.txt`.
3. From `backend/`, run `uvicorn main:app --reload`.
4. Open `portal/signup.html` for the business owner portal.
5. Replace `REPLACE_WITH_ORGANIZATION_UUID` in `dummy_website/index.html` after onboarding, then open the dummy site.

## Important existing-database note
`Base.metadata.create_all()` does not convert the old integer/Representative/Lead schema. Use a fresh MVP database or migrate/drop the old development tables before running this final schema.

## n8n follow-up workflow
The scheduled follow-up workflow is external to this codebase by design. Configure n8n to run on the desired regular interval, query visitors where `status = 'Needs Follow-Up'` and `visitor_email IS NOT NULL`, and send the follow-up email using visitor name/email and interested service.

## RAG grounding update

This build uses source-aware chunking and source-prioritized hybrid retrieval:

- Structured Services are authoritative for service names, prices, descriptions, and requirements.
- Structured Policies are authoritative for refund/cancellation/restriction/guarantee rules.
- FAQ uploads are split into individual Q/A chunks to reduce cross-answer hallucination.
- Uploaded `document_type` is preserved in the search source type (`uploaded_service`, `uploaded_policy`, `uploaded_general`).
- Broad catalogue queries such as "all services" or "compare services" include the complete structured service set before reranking.

If the organization already had documents indexed before this update, rebuild its search data once after starting the backend:

`POST /knowledge-documents/{organization_id}/reindex`

Example organization:

`POST /knowledge-documents/086a0696-35e2-4bcb-934e-35ffc097d8ab/reindex`

The reindex operation rebuilds both structured Services/Policies and uploaded knowledge using the current chunking rules. It does not delete the PostgreSQL business records or uploaded files.
