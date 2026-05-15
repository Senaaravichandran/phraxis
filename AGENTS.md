# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## What PHRAXIS Does

A developer speaks a feature idea (e.g., "add rate limiting — 100 requests per minute for free users"). IBM Watson STT transcribes it. IBM NLU extracts structured intent. IBM Bob reads the full demo_repo codebase using Architect mode, creates an implementation plan using Plan mode, generates the actual code files using Code mode, and opens a PR via GitHub API. Total time: under 4 minutes.

## Project Structure

```
phraxis/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── requirements.txt
│   ├── services/
│   │   ├── stt_service.py         # IBM Watson STT
│   │   ├── nlu_service.py         # IBM NLU intent extraction
│   │   ├── cloudant_service.py    # IBM Cloudant storage
│   │   ├── bob_orchestrator.py    # Calls Bob Shell, coordinates Bob modes
│   │   └── github_service.py      # Opens PRs via GitHub API
│   └── routes/
│       ├── voice.py               # POST /api/voice/transcribe
│       ├── intent.py              # POST /api/intent/extract
│       ├── generate.py            # POST /api/generate/code
│       └── pr.py                  # POST /api/pr/open
├── frontend/
│   ├── package.json
│   └── src/
│       ├── App.jsx
│       └── components/
│           ├── VoiceCapture.jsx   # Browser mic recording
│           ├── TranscriptPanel.jsx
│           ├── IntentPanel.jsx    # D3 structured intent display
│           ├── LiveCodePanel.jsx  # Real-time code generation view
│           └── PRStatus.jsx
├── demo_repo/                     # Sample payment service Bob will modify
│   ├── app.py
│   ├── models.py
│   ├── services/payment_service.py
│   └── tests/test_payment.py
├── bob_sessions/                  # Export all Bob task sessions here
├── .github/workflows/phraxis.yml
├── AGENTS.md
├── README.md
├── PROBLEM.md
├── SOLUTION.md
└── BOB_USAGE.md
```

## IBM Service Endpoints

- **STT_URL**: https://api.us-south.speech-to-text.watson.cloud.ibm.com
- **NLU_URL**: https://api.us-south.natural-language-understanding.watson.cloud.ibm.com
- **WATSONX_URL**: https://us-south.ml.cloud.ibm.com

## Required Environment Variables

```bash
IBM_STT_API_KEY=
IBM_STT_URL=https://api.us-south.speech-to-text.watson.cloud.ibm.com
IBM_NLU_API_KEY=
IBM_NLU_URL=https://api.us-south.natural-language-understanding.watson.cloud.ibm.com
IBM_CLOUDANT_URL=
IBM_CLOUDANT_API_KEY=
IBM_CLOUDANT_DB_NAME=phraxis_intents
WATSONX_API_KEY=
WATSONX_PROJECT_ID=
WATSONX_MODEL_ID=ibm/granite-3-8b-instruct
GITHUB_TOKEN=
GITHUB_REPO_OWNER=
GITHUB_REPO_NAME=demo_repo
```

## How Bob Is Used In This Project

- **Architect mode**: Bob reads demo_repo and maps every file, function, import, and pattern
- **Plan mode**: Bob generates step-by-step implementation plan for the spoken feature
- **Code mode**: Bob writes the actual code files across demo_repo
- **Orchestrate mode**: Bob coordinates the full Architect→Plan→Code sequence autonomously
- **Bob Shell**: Runs non-interactive Bob commands from Python subprocess calls
- **Ask mode**: Bob explains generated code in the PR description
- **Custom mode "phraxis-builder"**: Pre-loaded with demo_repo context to conserve Bobcoins

## The 5-Step Pipeline

1. **Voice captured** in browser → sent as audio blob to `POST /api/voice/transcribe`
2. **Transcript** → `POST /api/intent/extract` → structured JSON `{action, parameters, location, constraints}`
3. **Intent JSON** stored in Cloudant → `POST /api/generate/code` triggered
4. **bob_orchestrator.py** calls Bob Shell: Bob reads demo_repo, generates plan, writes code
5. **Generated files** committed → `POST /api/pr/open` → GitHub API creates PR with description referencing original transcript

## Demo Scenario

The demo_repo is a Python payment service. During the demo, the developer speaks: "Add rate limiting — 100 requests per minute for free tier users and 1000 for premium. Return 429 with a retry-after header." PHRAXIS generates the complete rate limiting middleware across all affected files and opens a real GitHub PR.

## Build & Run Commands

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Demo Repo (Target for Bob modifications)
```bash
cd demo_repo
pip install -r requirements.txt
pytest tests/
```

## Code Style Guidelines

### Backend (Python/FastAPI)
- Use async/await for all route handlers
- Type hints required for all function signatures
- Pydantic models for request/response validation
- Service layer pattern: routes call services, services call IBM APIs
- Error handling: raise HTTPException with appropriate status codes
- Logging: use Python logging module with structured JSON format

### Frontend (React/Vite)
- Functional components with hooks only
- PropTypes for component props
- CSS Modules for styling
- D3.js for intent visualization in IntentPanel
- MediaRecorder API for voice capture
- WebSocket for real-time code generation updates

### Bob Orchestrator
- All Bob commands run via subprocess with timeout
- Export Bob session data to bob_sessions/ directory
- Parse Bob output for structured data extraction
- Handle Bob mode switching: Architect → Plan → Code
- Retry logic for Bob API failures

## Testing

### Backend Tests
```bash
cd backend
pytest tests/ -v
pytest tests/test_specific.py::test_function_name  # Single test
```

### Frontend Tests
```bash
cd frontend
npm test
npm test -- VoiceCapture.test.jsx  # Single component
```

## Critical Integration Points

1. **Bob Shell Integration**: Use `subprocess.run()` with `capture_output=True` and `timeout=300`
2. **GitHub API**: Requires personal access token with `repo` scope
3. **IBM Watson Services**: All require IAM authentication with API keys
4. **Cloudant**: Use CouchDB-compatible client, database must exist before first write
5. **Audio Format**: Browser sends WebM/Opus, convert to FLAC for Watson STT

## Security Notes

- Never commit .env file with real credentials
- GitHub token should have minimal required scopes
- IBM API keys should be service-specific, not account-wide
- Validate all user input before passing to Bob or GitHub API
- Sanitize voice transcripts before storage in Cloudant

## Hackathon Demo Flow

1. Start backend: `cd backend && uvicorn main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open browser to http://localhost:5173
4. Click microphone, speak feature request
5. Watch real-time: transcript → intent → Bob working → PR created
6. Show GitHub PR with generated code and AI explanation
7. Total demo time: under 4 minutes from voice to PR