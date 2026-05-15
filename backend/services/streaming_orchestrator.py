"""
Streaming Bob orchestrator service for PHRAXIS.
Provides real-time progress updates via Server-Sent Events during Bob execution.
"""
import logging
import asyncio
import json
from typing import Dict, Any, AsyncGenerator
from datetime import datetime

from backend.services.bob_orchestrator import BobOrchestrator, BobOrchestratorError

logger = logging.getLogger(__name__)


class StreamingOrchestrator:
    """
    Streaming wrapper for BobOrchestrator.
    Yields progress events as Server-Sent Events during execution.
    """
    
    def __init__(self):
        """Initialize the streaming orchestrator."""
        self.orchestrator = BobOrchestrator()
        logger.info("Streaming orchestrator initialized successfully")
    
    async def orchestrate_stream(
        self,
        intent: Dict[str, Any],
        repo_path: str
    ) -> AsyncGenerator[str, None]:
        """
        Run Bob orchestration with streaming progress updates.
        
        Args:
            intent: Structured intent dictionary
            repo_path: Path to the repository to modify
        
        Yields:
            Server-Sent Event formatted strings with progress updates
        
        Event types:
            - started: Orchestration started
            - architect_started: Architect mode started
            - architect_complete: Architect mode completed
            - plan_started: Plan mode started
            - plan_complete: Plan mode completed
            - code_started: Code generation started
            - code_step: Individual code generation step
            - code_complete: Code generation completed
            - complete: Orchestration completed successfully
            - error: Error occurred
        """
        session_id = None
        
        try:
            # Send started event
            yield self._format_sse({
                "event": "started",
                "timestamp": datetime.utcnow().isoformat(),
                "intent": intent,
                "repo_path": repo_path
            })
            
            # Run orchestration in executor to avoid blocking
            loop = asyncio.get_event_loop()
            
            # Step 1: Architect mode
            yield self._format_sse({
                "event": "architect_started",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Analyzing repository structure..."
            })
            
            # Run architect in thread pool
            architect_output = await loop.run_in_executor(
                None,
                self.orchestrator._run_architect,
                intent,
                repo_path,
                self._generate_session_id()
            )
            
            session_id = architect_output.get('session_id', 'unknown')
            
            yield self._format_sse({
                "event": "architect_complete",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Repository analysis complete",
                "data": {
                    "files_to_modify": len(architect_output.get('files_to_modify', [])),
                    "new_files": len(architect_output.get('new_files_to_create', [])),
                    "functions_to_change": len(architect_output.get('functions_to_change', []))
                }
            })
            
            # Step 2: Plan mode
            yield self._format_sse({
                "event": "plan_started",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Creating implementation plan..."
            })
            
            plan = await loop.run_in_executor(
                None,
                self.orchestrator._run_plan,
                intent,
                architect_output,
                session_id
            )
            
            yield self._format_sse({
                "event": "plan_complete",
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Plan created with {len(plan)} steps",
                "data": {
                    "steps": len(plan),
                    "plan_summary": [
                        {
                            "step": s.get('step'),
                            "file": s.get('file_path'),
                            "operation": s.get('operation')
                        }
                        for s in plan
                    ]
                }
            })
            
            # Step 3: Code generation
            yield self._format_sse({
                "event": "code_started",
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Generating code for {len(plan)} steps..."
            })
            
            # Generate code step by step with progress updates
            code_changes = {}
            for i, step in enumerate(plan, 1):
                step_num = step.get('step', i)
                file_path = step.get('file_path', '')
                operation = step.get('operation', 'modify')
                
                yield self._format_sse({
                    "event": "code_step",
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": f"Generating code for step {i}/{len(plan)}: {operation} {file_path}",
                    "data": {
                        "step": step_num,
                        "current": i,
                        "total": len(plan),
                        "file_path": file_path,
                        "operation": operation
                    }
                })
                
                # Generate code for this step
                try:
                    description = step.get('description', '')
                    prompt = (
                        f"Switch to Code mode. Implement this specific change in {repo_path}: "
                        f"{description}. "
                        f"File: {file_path}. Operation: {operation}. "
                        f"Follow the existing code patterns exactly. "
                        f"Write the complete file content."
                    )
                    
                    output = await loop.run_in_executor(
                        None,
                        self.orchestrator._run_bob_command,
                        prompt,
                        session_id,
                        f"code_step_{step_num}"
                    )
                    
                    code_content = self.orchestrator._extract_code_from_output(output)
                    code_changes[file_path] = code_content
                    
                except Exception as e:
                    logger.error(f"Code generation failed for step {step_num}: {e}")
                    code_changes[file_path] = f"# ERROR: Code generation failed: {e}"
                    
                    yield self._format_sse({
                        "event": "code_step_error",
                        "timestamp": datetime.utcnow().isoformat(),
                        "message": f"Error generating code for step {i}: {str(e)}",
                        "data": {
                            "step": step_num,
                            "file_path": file_path,
                            "error": str(e)
                        }
                    })
            
            yield self._format_sse({
                "event": "code_complete",
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Code generation complete: {len(code_changes)} files",
                "data": {
                    "files_generated": list(code_changes.keys())
                }
            })
            
            # Prepare final result
            result = {
                "plan": plan,
                "files_generated": list(code_changes.keys()),
                "code_changes": code_changes,
                "bob_session_id": session_id,
                "architect_output": architect_output,
                "status": "success"
            }
            
            # Save session
            self.orchestrator._save_session(session_id, intent, result)
            
            # Send completion event
            yield self._format_sse({
                "event": "complete",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Orchestration completed successfully",
                "data": result
            })
            
        except BobOrchestratorError as e:
            logger.error(f"Bob orchestration error: {e}")
            yield self._format_sse({
                "event": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "message": str(e),
                "data": {
                    "error_type": "BobOrchestratorError",
                    "session_id": session_id
                }
            })
        
        except Exception as e:
            logger.error(f"Unexpected error during streaming orchestration: {e}")
            yield self._format_sse({
                "event": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Unexpected error: {str(e)}",
                "data": {
                    "error_type": type(e).__name__,
                    "session_id": session_id
                }
            })
    
    def _format_sse(self, data: Dict[str, Any]) -> str:
        """
        Format data as Server-Sent Event.
        
        Args:
            data: Event data dictionary
        
        Returns:
            SSE formatted string
        """
        event_type = data.get('event', 'message')
        json_data = json.dumps(data)
        
        # SSE format: event: type\ndata: json\n\n
        return f"event: {event_type}\ndata: {json_data}\n\n"
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        import uuid
        return str(uuid.uuid4())


# Made with Bob