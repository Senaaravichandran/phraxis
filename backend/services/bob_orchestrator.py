"""
IBM Bob orchestrator service for PHRAXIS.
Coordinates Bob Shell execution for repository intelligence and code generation.
"""
import logging
import subprocess
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from backend.env_loader import get_config

logger = logging.getLogger(__name__)


class BobOrchestratorError(Exception):
    """Raised when Bob orchestration encounters an error."""
    pass


class BobOrchestrator:
    """
    Bob Shell orchestrator for PHRAXIS.
    Runs full Architect→Plan→Code sequence using Bob Shell subprocess calls.
    """
    
    def __init__(self):
        """Initialize the Bob orchestrator."""
        config = get_config()
        self.session_dir = Path("bob_sessions")
        self.session_dir.mkdir(exist_ok=True)
        logger.info("Bob orchestrator initialized successfully")
    
    def orchestrate(self, intent: Dict[str, Any], repo_path: str) -> Dict[str, Any]:
        """
        Run full Bob orchestration: Architect→Plan→Code sequence.
        
        Args:
            intent: Structured intent dictionary with action, parameters, constraints
            repo_path: Path to the repository to modify
        
        Returns:
            Dictionary containing:
                - plan (list): Step-by-step implementation plan
                - files_generated (list): List of files created/modified
                - code_changes (dict): Map of file paths to their changes
                - bob_session_id (str): Unique session identifier
                - architect_output (dict): Repository analysis from Architect mode
                - execution_time (float): Total execution time in seconds
        
        Raises:
            BobOrchestratorError: If any step fails
        """
        session_id = str(uuid.uuid4())
        session_start = datetime.utcnow()
        
        logger.info(f"Starting Bob orchestration session: {session_id}")
        logger.info(f"Intent: {intent.get('action')} on {repo_path}")
        
        try:
            # Step 1: ARCHITECT - Analyze repository
            logger.info("Step 1: Running Architect mode")
            architect_output = self._run_architect(intent, repo_path, session_id)
            
            # Step 2: PLAN - Create implementation plan
            logger.info("Step 2: Running Plan mode")
            plan = self._run_plan(intent, architect_output, session_id)
            
            # Step 3: CODE - Generate code for each step
            logger.info("Step 3: Running Code mode")
            code_changes = self._run_code(plan, repo_path, session_id)
            
            # Calculate execution time
            execution_time = (datetime.utcnow() - session_start).total_seconds()
            
            # Prepare result
            result = {
                "plan": plan,
                "files_generated": list(code_changes.keys()),
                "code_changes": code_changes,
                "bob_session_id": session_id,
                "architect_output": architect_output,
                "execution_time": execution_time,
                "status": "success"
            }
            
            # Save session data
            self._save_session(session_id, intent, result)
            
            logger.info(f"Bob orchestration completed successfully: {session_id}")
            logger.info(f"Generated {len(code_changes)} files in {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            error_msg = f"Bob orchestration failed: {str(e)}"
            logger.error(error_msg)
            
            # Save error session
            error_result = {
                "status": "error",
                "error": str(e),
                "bob_session_id": session_id,
                "execution_time": (datetime.utcnow() - session_start).total_seconds()
            }
            self._save_session(session_id, intent, error_result)
            
            raise BobOrchestratorError(error_msg)
    
    def _run_architect(
        self,
        intent: Dict[str, Any],
        repo_path: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Run Bob in Architect mode to analyze repository.
        
        Args:
            intent: Structured intent
            repo_path: Repository path
            session_id: Session identifier
        
        Returns:
            Repository analysis as JSON
        """
        action = intent.get('action', 'unknown')
        parameters = intent.get('parameters', {})
        
        # Build Bob command for Architect mode
        prompt = (
            f"Switch to Architect mode. Read every file in {repo_path}. "
            f"Map all functions, classes, imports, and patterns. "
            f"Identify which files and functions need to change to implement: {action} "
            f"with parameters {json.dumps(parameters)}. "
            f"Output as JSON with this structure: "
            f"{{\"files_to_modify\": [], \"new_files_to_create\": [], "
            f"\"functions_to_change\": [], \"patterns_used\": []}}"
        )
        
        try:
            output = self._run_bob_command(prompt, session_id, "architect")
            
            # Parse JSON output
            architect_data = self._parse_bob_json_output(output)
            
            logger.info(f"Architect analysis complete: {len(architect_data.get('files_to_modify', []))} files to modify")
            return architect_data
            
        except Exception as e:
            logger.error(f"Architect mode failed: {e}")
            raise BobOrchestratorError(f"Architect mode failed: {e}")
    
    def _run_plan(
        self,
        intent: Dict[str, Any],
        architect_output: Dict[str, Any],
        session_id: str
    ) -> List[Dict[str, Any]]:
        """
        Run Bob in Plan mode to create implementation plan.
        
        Args:
            intent: Structured intent
            architect_output: Repository analysis from Architect mode
            session_id: Session identifier
        
        Returns:
            List of implementation steps
        """
        action = intent.get('action', 'unknown')
        parameters = intent.get('parameters', {})
        constraints = intent.get('constraints', [])
        
        intent_description = (
            f"{action} with parameters {json.dumps(parameters)}. "
            f"Constraints: {', '.join(constraints) if constraints else 'none'}"
        )
        
        # Build Bob command for Plan mode
        prompt = (
            f"Switch to Plan mode. Given this repository map: {json.dumps(architect_output)}. "
            f"Create a step-by-step implementation plan for: {intent_description}. "
            f"Each step must specify: file path, function name, exact change description, "
            f"and whether it's a modify or create operation. "
            f"Output as JSON array of steps with structure: "
            f"[{{\"step\": 1, \"file_path\": \"\", \"function_name\": \"\", "
            f"\"operation\": \"modify|create\", \"description\": \"\"}}]"
        )
        
        try:
            output = self._run_bob_command(prompt, session_id, "plan")
            
            # Parse JSON output
            plan_data = self._parse_bob_json_output(output)
            
            # Ensure it's a list
            if isinstance(plan_data, dict) and 'steps' in plan_data:
                plan = plan_data['steps']
            elif isinstance(plan_data, list):
                plan = plan_data
            else:
                raise ValueError("Plan output is not in expected format")
            
            logger.info(f"Plan created with {len(plan)} steps")
            return plan
            
        except Exception as e:
            logger.error(f"Plan mode failed: {e}")
            raise BobOrchestratorError(f"Plan mode failed: {e}")
    
    def _run_code(
        self,
        plan: List[Dict[str, Any]],
        repo_path: str,
        session_id: str
    ) -> Dict[str, str]:
        """
        Run Bob in Code mode to generate code for each planned step.
        
        Args:
            plan: Implementation plan from Plan mode
            repo_path: Repository path
            session_id: Session identifier
        
        Returns:
            Dictionary mapping file paths to their generated content
        """
        code_changes = {}
        
        for step in plan:
            step_num = step.get('step', 0)
            file_path = step.get('file_path', '')
            operation = step.get('operation', 'modify')
            description = step.get('description', '')
            
            logger.info(f"Generating code for step {step_num}: {operation} {file_path}")
            
            # Build Bob command for Code mode
            prompt = (
                f"Switch to Code mode. Implement this specific change in {repo_path}: "
                f"{description}. "
                f"File: {file_path}. Operation: {operation}. "
                f"Follow the existing code patterns exactly. "
                f"Write the complete file content."
            )
            
            try:
                output = self._run_bob_command(prompt, session_id, f"code_step_{step_num}")
                
                # Extract code from output
                # Bob may wrap code in markdown code blocks
                code_content = self._extract_code_from_output(output)
                
                code_changes[file_path] = code_content
                logger.info(f"Code generated for {file_path}: {len(code_content)} characters")
                
            except Exception as e:
                logger.error(f"Code generation failed for step {step_num}: {e}")
                # Continue with other steps even if one fails
                code_changes[file_path] = f"# ERROR: Code generation failed: {e}"
        
        return code_changes
    
    def _run_bob_command(
        self,
        prompt: str,
        session_id: str,
        mode: str,
        max_retries: int = 2
    ) -> str:
        """
        Execute a Bob Shell command with retry logic.
        
        Args:
            prompt: Command prompt for Bob
            session_id: Session identifier
            mode: Bob mode being used (for logging)
            max_retries: Maximum number of retry attempts
        
        Returns:
            Bob command output as string
        
        Raises:
            BobOrchestratorError: If command fails after retries
        """
        command = ["bob", "--non-interactive", prompt]
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Running Bob command (attempt {attempt + 1}/{max_retries + 1}): {mode}")
                
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                    check=True
                )
                
                output = result.stdout
                
                # Log output to session file
                self._log_bob_output(session_id, mode, prompt, output, attempt)
                
                return output
                
            except subprocess.TimeoutExpired:
                logger.warning(f"Bob command timed out (attempt {attempt + 1})")
                if attempt == max_retries:
                    raise BobOrchestratorError(f"Bob command timed out after {max_retries + 1} attempts")
            
            except subprocess.CalledProcessError as e:
                logger.warning(f"Bob command failed with exit code {e.returncode} (attempt {attempt + 1})")
                logger.warning(f"Error output: {e.stderr}")
                if attempt == max_retries:
                    raise BobOrchestratorError(f"Bob command failed: {e.stderr}")
            
            except Exception as e:
                logger.warning(f"Unexpected error running Bob command (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    raise BobOrchestratorError(f"Bob command failed: {e}")
        
        raise BobOrchestratorError("Bob command failed after all retries")
    
    def _parse_bob_json_output(self, output: str) -> Any:
        """
        Parse JSON from Bob output, handling markdown code blocks.
        
        Args:
            output: Raw Bob output
        
        Returns:
            Parsed JSON data
        """
        # Try to find JSON in markdown code blocks
        import re
        
        # Look for ```json ... ``` blocks
        json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Look for any code block
            code_match = re.search(r'```\s*\n(.*?)\n```', output, re.DOTALL)
            if code_match:
                json_str = code_match.group(1)
            else:
                # Try to parse the entire output
                json_str = output
        
        try:
            return json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Bob output: {e}")
            logger.error(f"Output was: {output[:500]}...")
            raise BobOrchestratorError(f"Failed to parse Bob JSON output: {e}")
    
    def _extract_code_from_output(self, output: str) -> str:
        """
        Extract code content from Bob output, handling markdown code blocks.
        
        Args:
            output: Raw Bob output
        
        Returns:
            Extracted code content
        """
        import re
        
        # Look for code blocks with language specifier
        code_match = re.search(r'```(?:\w+)?\s*\n(.*?)\n```', output, re.DOTALL)
        if code_match:
            return code_match.group(1)
        
        # If no code block found, return the entire output
        return output.strip()
    
    def _log_bob_output(
        self,
        session_id: str,
        mode: str,
        prompt: str,
        output: str,
        attempt: int
    ):
        """
        Log Bob command output to session file.
        
        Args:
            session_id: Session identifier
            mode: Bob mode
            prompt: Command prompt
            output: Command output
            attempt: Attempt number
        """
        log_file = self.session_dir / f"{session_id}_{mode}_attempt_{attempt}.log"
        
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== Bob {mode.upper()} Mode ===\n")
                f.write(f"Session ID: {session_id}\n")
                f.write(f"Attempt: {attempt + 1}\n")
                f.write(f"Timestamp: {datetime.utcnow().isoformat()}\n\n")
                f.write(f"=== PROMPT ===\n{prompt}\n\n")
                f.write(f"=== OUTPUT ===\n{output}\n")
            
            logger.debug(f"Logged Bob output to {log_file}")
        except Exception as e:
            logger.warning(f"Failed to log Bob output: {e}")
    
    def _save_session(
        self,
        session_id: str,
        intent: Dict[str, Any],
        result: Dict[str, Any]
    ):
        """
        Save complete session data to file.
        
        Args:
            session_id: Session identifier
            intent: Original intent
            result: Orchestration result
        """
        session_file = self.session_dir / f"{session_id}_session.json"
        
        session_data = {
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "intent": intent,
            "result": result
        }
        
        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
            
            logger.info(f"Session data saved to {session_file}")
        except Exception as e:
            logger.warning(f"Failed to save session data: {e}")
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve saved session data.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Session data or None if not found
        """
        session_file = self.session_dir / f"{session_id}_session.json"
        
        if not session_file.exists():
            logger.warning(f"Session file not found: {session_id}")
            return None
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load session data: {e}")
            return None


# Made with Bob