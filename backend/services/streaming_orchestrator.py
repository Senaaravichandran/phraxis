"""
Streaming orchestrator service for PHRAXIS.
Provides real-time progress updates via Server-Sent Events during code generation.
"""
import logging
import asyncio
import json
from typing import Dict, Any, AsyncGenerator
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from services.bob_orchestrator import BobOrchestrator, BobOrchestratorError

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
        Run orchestration with streaming progress updates.

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
        session_id = self._generate_session_id()

        try:
            resolved_repo_path = self.orchestrator.validate_runtime(repo_path)

            # Send started event
            yield self._format_sse({
                "event": "started",
                "timestamp": datetime.utcnow().isoformat(),
                "intent": intent,
                "repo_path": str(resolved_repo_path),
                "session_id": session_id
            })

            # Run orchestration in executor to avoid blocking
            loop = asyncio.get_event_loop()

            # Step 1: Architect mode
            yield self._format_sse({
                "event": "architect_started",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Analyzing repository structure with WatsonX Granite..."
            })

            # Run architect in thread pool
            architect_output = await loop.run_in_executor(
                None,
                self.orchestrator._run_architect,
                intent,
                str(resolved_repo_path),
                session_id
            )

            yield self._format_sse({
                "event": "architect_complete",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Repository analysis complete",
                "result": architect_output,
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
                "message": "Creating implementation plan with WatsonX Granite..."
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
                "result": {
                    "steps": plan
                },
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
                "message": f"Generating code for {len(plan)} steps with WatsonX Granite..."
            })

            # Generate code step by step with progress updates
            code_changes = {}
            repo_context = self.orchestrator._scan_repo_context(resolved_repo_path)

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

                    # Read existing file if modifying
                    existing_code = ""
                    if operation == "modify":
                        full_path = resolved_repo_path / file_path
                        if full_path.exists():
                            try:
                                existing_code = full_path.read_text(encoding='utf-8', errors='ignore')
                            except Exception:
                                pass

                    code_content = await loop.run_in_executor(
                        None,
                        self.orchestrator.code_service.run_code,
                        file_path,
                        operation,
                        description,
                        repo_context[:1500],
                        existing_code
                    )

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
                "result": result,
                "data": result
            })

        except BobOrchestratorError as e:
            logger.error(f"Orchestration error: {e}")
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
