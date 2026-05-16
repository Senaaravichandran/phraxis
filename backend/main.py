"""
PHRAXIS FastAPI application.
Voice-to-code system powered by IBM Watson and IBM Bob.
"""
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List
from contextlib import asynccontextmanager

# Add backend directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from env_loader import validate_environment, get_config
from services.stt_service import STTService, STTServiceError
from services.nlu_service import NLUService, NLUServiceError
from services.cloudant_service import CloudantService, CloudantServiceError
from services.watsonx_service import WatsonxService, WatsonxServiceError
from services.bob_orchestrator import BobOrchestrator, BobOrchestratorError
from services.streaming_orchestrator import StreamingOrchestrator
from services.github_service import GitHubService, GitHubServiceError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Pydantic models for request/response validation
class TranscribeResponse(BaseModel):
    """Response model for transcription endpoint."""
    transcript: str
    confidence: float
    words: List[Dict[str, Any]]


class IntentRequest(BaseModel):
    """Request model for intent extraction."""
    transcript: str


class IntentResponse(BaseModel):
    """Response model for intent extraction."""
    intent_doc_id: str
    action: str
    target_module: str
    parameters: Dict[str, Any]
    constraints: List[str]
    confidence: float


class GenerateCodeRequest(BaseModel):
    """Request model for code generation."""
    intent_doc_id: str
    repo_path: str = Field(
        default="",
        description="GitHub repository URL or local repository path (resolved from .env if empty)"
    )


class OpenPRRequest(BaseModel):
    """Request model for opening PR."""
    intent_doc_id: str
    files_changed: Dict[str, str]
    branch_name: str | None = Field(default=None, description="Branch name (auto-generated if not provided)")


class PRResponse(BaseModel):
    """Response model for PR creation."""
    pr_url: str
    pr_number: int
    branch_name: str
    files_committed: List[str]
    commit_sha: str


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    services: Dict[str, bool]
    timestamp: str


# Global service instances
stt_service: STTService | None = None
nlu_service: NLUService | None = None
cloudant_service: CloudantService | None = None
watsonx_service: WatsonxService | None = None
bob_orchestrator: BobOrchestrator | None = None
streaming_orchestrator: StreamingOrchestrator | None = None
github_service: GitHubService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Initializes services on startup and cleans up on shutdown.
    """
    global stt_service, nlu_service, cloudant_service, watsonx_service
    global bob_orchestrator, streaming_orchestrator, github_service
    
    logger.info("Starting PHRAXIS application...")
    
    try:
        # Validate environment variables
        config = validate_environment()
        
        # Initialize services
        logger.info("Initializing services...")
        stt_service = STTService()
        nlu_service = NLUService()
        cloudant_service = CloudantService()
        watsonx_service = WatsonxService()
        bob_orchestrator = BobOrchestrator()
        streaming_orchestrator = StreamingOrchestrator()
        github_service = GitHubService()
        
        logger.info("✓ All services initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    
    finally:
        logger.info("Shutting down PHRAXIS application...")


# Create FastAPI app
app = FastAPI(
    title="PHRAXIS API",
    description="Voice-to-code system powered by IBM Watson and IBM Bob",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "PHRAXIS API - Voice-to-Code System",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.post("/api/voice/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file (WebM, FLAC, WAV)")
):
    """
    Transcribe audio to text using IBM Watson Speech-to-Text.
    
    Args:
        audio: Audio file from browser recording
    
    Returns:
        Transcript with confidence scores and word-level timing
    """
    if stt_service is None:
        raise HTTPException(status_code=503, detail="STT service not initialized")
    
    try:
        logger.info(f"Received audio file: {audio.filename} ({audio.content_type})")
        
        # Read audio bytes
        audio_bytes = await audio.read()
        
        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")

        # Support the frontend text fallback without sending it through STT.
        if (audio.content_type or "").split(";")[0].strip().lower() == "text/plain":
            transcript = audio_bytes.decode("utf-8", errors="ignore").strip()
            if not transcript:
                raise HTTPException(status_code=400, detail="Empty text input")

            return TranscribeResponse(
                transcript=transcript,
                confidence=1.0,
                words=[]
            )
        
        # Transcribe using STT service
        result = stt_service.transcribe_audio(
            audio_bytes=audio_bytes,
            content_type=audio.content_type or "audio/webm"
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return TranscribeResponse(**result)
        
    except STTServiceError as e:
        logger.error(f"STT service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error in transcribe endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@app.post("/api/intent/extract", response_model=IntentResponse)
async def extract_intent(request: IntentRequest):
    """
    Extract structured intent from transcript using IBM Watson NLU.
    
    Args:
        request: Request containing transcript text
    
    Returns:
        Structured intent with action, parameters, and constraints
    """
    if nlu_service is None or cloudant_service is None:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    try:
        logger.info(f"Extracting intent from transcript: '{request.transcript[:100]}...'")
        
        if not request.transcript or request.transcript.strip() == "":
            raise HTTPException(status_code=400, detail="Empty transcript")
        
        # Extract intent using NLU service
        intent = nlu_service.extract_intent(request.transcript)
        
        if "error" in intent:
            raise HTTPException(status_code=400, detail=intent["error"])
        
        # Save intent to Cloudant
        doc_id = cloudant_service.save_intent(intent)
        
        return IntentResponse(
            intent_doc_id=doc_id,
            action=intent["action"],
            target_module=intent["target_module"],
            parameters=intent["parameters"],
            constraints=intent["constraints"],
            confidence=intent["confidence"]
        )
        
    except NLUServiceError as e:
        logger.error(f"NLU service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    except CloudantServiceError as e:
        logger.error(f"Cloudant service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error in extract_intent endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Intent extraction failed: {str(e)}")


@app.get("/api/generate/code")
async def generate_code(
    intent_doc_id: str,
    repo_path: str = ""
):
    """
    Generate code using Bob orchestration with streaming progress updates.
    Returns Server-Sent Events stream.
    
    Args:
        intent_doc_id: Intent document ID from Cloudant
        repo_path: GitHub repository URL or local path for Bob analysis
    
    Returns:
        SSE stream of progress events
    """
    if cloudant_service is None or streaming_orchestrator is None:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    if not intent_doc_id or intent_doc_id == "undefined":
        raise HTTPException(status_code=400, detail="Invalid intent_doc_id")
    
    try:
        logger.info(f"Starting code generation for intent: {intent_doc_id}")
        
        # Get intent from Cloudant
        intent = cloudant_service.get_intent(intent_doc_id)
        
        # Update status to processing
        cloudant_service.update_intent_status(intent_doc_id, "processing")
        
        # Stream Bob orchestration progress
        async def event_generator():
            if cloudant_service is None or streaming_orchestrator is None:
                return
            try:
                async for event in streaming_orchestrator.orchestrate_stream(
                    intent=intent,
                    repo_path=repo_path
                ):
                    yield event
                
                # Update status to complete
                cloudant_service.update_intent_status(intent_doc_id, "complete")
                
            except Exception as e:
                logger.error(f"Error during code generation: {e}")
                # Update status to error
                cloudant_service.update_intent_status(
                    intent_doc_id,
                    "error",
                    {"error": str(e)}
                )
                # Send error event
                import json
                error_event = f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                yield error_event
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except CloudantServiceError as e:
        logger.error(f"Cloudant service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error in generate_code endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Code generation failed: {str(e)}")


@app.post("/api/pr/open", response_model=PRResponse)
async def open_pr(request: OpenPRRequest):
    """
    Open a GitHub pull request with generated code changes.
    
    Args:
        request: Request containing intent ID, files changed, and optional branch name
    
    Returns:
        PR details including URL and number
    """
    if cloudant_service is None or github_service is None:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    try:
        logger.info(f"Opening PR for intent: {request.intent_doc_id}")
        
        # Get intent from Cloudant
        intent = cloudant_service.get_intent(request.intent_doc_id)
        
        # Generate branch name if not provided
        if not request.branch_name:
            from datetime import datetime
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            action = intent.get('action', 'feature').replace('_', '-')
            request.branch_name = f"phraxis/{action}-{timestamp}"
        
        # Get transcript from intent
        transcript = intent.get('raw_text', 'Voice command')
        
        # Create PR using GitHub service
        config = get_config()
        pr_result = github_service.create_pr(
            repo_owner=config.GITHUB_REPO_OWNER,
            repo_name=config.GITHUB_REPO_NAME,
            branch_name=request.branch_name,
            files_changed=request.files_changed,
            intent=intent,
            transcript=transcript
        )
        
        # Update intent with PR information
        cloudant_service.update_intent_status(
            request.intent_doc_id,
            "complete",
            {
                "pr_url": pr_result["pr_url"],
                "pr_number": pr_result["pr_number"],
                "branch_name": pr_result["branch_name"]
            }
        )
        
        return PRResponse(**pr_result)
        
    except CloudantServiceError as e:
        logger.error(f"Cloudant service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    except GitHubServiceError as e:
        logger.error(f"GitHub service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error in open_pr endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"PR creation failed: {str(e)}")


@app.get("/api/intents")
async def list_intents(limit: int = 20):
    """
    List recent intents from Cloudant.
    
    Args:
        limit: Maximum number of intents to return (default: 20)
    
    Returns:
        List of intent documents
    """
    if cloudant_service is None:
        raise HTTPException(status_code=503, detail="Cloudant service not initialized")
    
    try:
        logger.info(f"Listing intents (limit: {limit})")
        
        intents = cloudant_service.list_intents(limit=limit)
        
        return {
            "intents": intents,
            "count": len(intents)
        }
        
    except CloudantServiceError as e:
        logger.error(f"Cloudant service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error in list_intents endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list intents: {str(e)}")


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """
    Check health status of all services.
    
    Returns:
        Health status for each service
    """
    from datetime import datetime
    
    try:
        logger.info("Running health checks...")
        
        services_status = {
            "stt": stt_service.health_check() if stt_service else False,
            "nlu": nlu_service.health_check() if nlu_service else False,
            "cloudant": cloudant_service.health_check() if cloudant_service else False,
            "watsonx": watsonx_service.health_check() if watsonx_service else False,
            "github": github_service.health_check() if github_service else False,
        }
        
        # Overall status is healthy if all services are healthy
        overall_status = "healthy" if all(services_status.values()) else "degraded"
        
        return HealthResponse(
            status=overall_status,
            services=services_status,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="error",
            services={},
            timestamp=datetime.utcnow().isoformat()
        )


# ============================================================================
# ADDITIONAL ENDPOINTS
# ============================================================================

@app.get("/api/intents/{intent_id}")
async def get_intent(intent_id: str):
    """
    Get a specific intent by ID.
    
    Args:
        intent_id: Intent document ID
    
    Returns:
        Intent document
    """
    if cloudant_service is None:
        raise HTTPException(status_code=503, detail="Cloudant service not initialized")
    
    try:
        intent = cloudant_service.get_intent(intent_id)
        return intent
        
    except CloudantServiceError as e:
        logger.error(f"Cloudant service error: {e}")
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/pr/{pr_number}")
async def get_pr(pr_number: int):
    """
    Get pull request details.
    
    Args:
        pr_number: Pull request number
    
    Returns:
        PR details
    """
    if github_service is None:
        raise HTTPException(status_code=503, detail="GitHub service not initialized")
    
    try:
        pr = github_service.get_pr(pr_number)
        return pr
        
    except GitHubServiceError as e:
        logger.error(f"GitHub service error: {e}")
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/prs")
async def list_prs(state: str = "open", limit: int = 20):
    """
    List pull requests.
    
    Args:
        state: PR state ("open", "closed", "all")
        limit: Maximum number of PRs to return
    
    Returns:
        List of PRs
    """
    if github_service is None:
        raise HTTPException(status_code=503, detail="GitHub service not initialized")
    
    try:
        prs = github_service.list_prs(state=state, limit=limit)
        return {
            "prs": prs,
            "count": len(prs)
        }
        
    except GitHubServiceError as e:
        logger.error(f"GitHub service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise


# Made with Bob
