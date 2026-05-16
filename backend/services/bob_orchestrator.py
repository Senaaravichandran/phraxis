"""
IBM Bob orchestrator service for PHRAXIS.
Coordinates code generation using WatsonX Granite API.

Originally designed around Bob Shell CLI subprocess calls, now refactored
to use WatsonX Granite model directly via API for Architect→Plan→Code pipeline.
"""
import logging
import json
import uuid
import os
import shutil
import tempfile
import zipfile
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from env_loader import get_config
from services.watsonx_code_service import WatsonxCodeService, WatsonxCodeServiceError

logger = logging.getLogger(__name__)


class BobOrchestratorError(Exception):
    """Raised when Bob orchestration encounters an error."""
    pass


class BobOrchestrator:
    """
    Code generation orchestrator for PHRAXIS.
    Runs full Architect→Plan→Code sequence using WatsonX Granite API.
    """

    def __init__(self):
        """Initialize the orchestrator."""
        config = get_config()
        self.config = config
        self.project_root = Path(__file__).resolve().parents[2]
        self.session_dir = self.project_root / "bob_sessions"
        self.repo_cache_dir = self.project_root / ".phraxis_repo_cache"
        self.session_dir.mkdir(exist_ok=True)
        self.repo_cache_dir.mkdir(exist_ok=True)

        # Initialize WatsonX code service (replaces Bob Shell CLI)
        try:
            self.code_service = WatsonxCodeService()
            logger.info("Bob orchestrator initialized with WatsonX code service")
        except WatsonxCodeServiceError as e:
            logger.error(f"Failed to initialize WatsonX code service: {e}")
            raise BobOrchestratorError(f"Code service initialization failed: {e}")

    def _build_default_repo_url(self) -> str:
        """Build the default GitHub repository URL from configuration."""
        return (
            os.getenv("DEMO_REPO_URL", "").strip()
            or f"https://github.com/{self.config.GITHUB_REPO_OWNER}/{self.config.GITHUB_REPO_NAME}"
        )

    def _is_remote_repo_reference(self, repo_path: str) -> bool:
        """Return True when the repo path should be resolved from GitHub."""
        candidate = repo_path.strip() if repo_path else self.config.GITHUB_REPO_NAME
        if candidate in {"demo_repo", self.config.GITHUB_REPO_NAME}:
            return True

        return candidate.startswith("https://github.com/") or candidate.startswith("http://github.com/")

    def _parse_repo_reference(self, repo_reference: str) -> tuple[str, str]:
        """Parse a GitHub repository reference into owner and repository name."""
        reference = repo_reference.strip() if repo_reference else self._build_default_repo_url()

        if reference in {"demo_repo", self.config.GITHUB_REPO_NAME}:
            return self.config.GITHUB_REPO_OWNER, self.config.GITHUB_REPO_NAME

        if reference.startswith("https://github.com/") or reference.startswith("http://github.com/"):
            parsed = urlparse(reference)
            path_parts = [part for part in parsed.path.strip("/").split("/") if part]
            if len(path_parts) < 2:
                raise BobOrchestratorError(f"Invalid GitHub repository URL: {reference}")

            owner = path_parts[0]
            repo_name = path_parts[1].removesuffix(".git")
            return owner, repo_name

        raise BobOrchestratorError(f"Unsupported repository reference: {reference}")

    def _get_archive_download_url(self, owner: str, repo_name: str) -> str:
        """Build the GitHub archive URL for the configured repository."""
        return f"https://api.github.com/repos/{owner}/{repo_name}/zipball"

    def _sync_remote_repo(self, repo_reference: str) -> Path:
        """
        Download the latest GitHub repository archive into a managed cache folder.
        """
        owner, repo_name = self._parse_repo_reference(repo_reference)
        target_dir = self.repo_cache_dir / f"{owner}_{repo_name}"
        archive_url = self._get_archive_download_url(owner, repo_name)

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "PHRAXIS",
        }
        if self.config.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {self.config.GITHUB_TOKEN}"

        logger.info(f"Syncing remote repository from GitHub: {owner}/{repo_name}")

        try:
            response = requests.get(archive_url, headers=headers, timeout=60)
            response.raise_for_status()
        except requests.RequestException as e:
            raise BobOrchestratorError(f"Failed to download GitHub repository archive: {e}")

        temp_extract_dir = Path(tempfile.mkdtemp(prefix="phraxis_repo_", dir=str(self.repo_cache_dir)))
        archive_path = temp_extract_dir / f"{repo_name}.zip"

        try:
            archive_path.write_bytes(response.content)

            with zipfile.ZipFile(archive_path, "r") as archive:
                archive.extractall(temp_extract_dir)

            extracted_dirs = [path for path in temp_extract_dir.iterdir() if path.is_dir()]
            if not extracted_dirs:
                raise BobOrchestratorError("Downloaded repository archive did not contain any files")

            extracted_root = extracted_dirs[0]

            if target_dir.exists():
                shutil.rmtree(target_dir)

            shutil.move(str(extracted_root), str(target_dir))
            logger.info(f"Remote repository synced to cache: {target_dir}")
            return target_dir
        except zipfile.BadZipFile as e:
            raise BobOrchestratorError(f"Invalid GitHub repository archive: {e}")
        finally:
            if archive_path.exists():
                archive_path.unlink(missing_ok=True)
            shutil.rmtree(temp_extract_dir, ignore_errors=True)

    def resolve_repo_path(self, repo_path: str) -> Path:
        """
        Resolve the repository path used for operations.

        Supports overriding the default demo repo path via `DEMO_REPO_PATH`.
        Relative paths are resolved from the project root so backend launch
        location does not affect behavior.
        """
        candidate = repo_path.strip() if repo_path else self.config.GITHUB_REPO_NAME

        if self._is_remote_repo_reference(candidate):
            return self._sync_remote_repo(candidate)

        configured_demo_repo = os.getenv("DEMO_REPO_PATH", "").strip()
        if candidate == "demo_repo" and configured_demo_repo:
            candidate = configured_demo_repo

        path = Path(candidate)
        if not path.is_absolute():
            path = (self.project_root / path).resolve()

        return path

    def validate_runtime(self, repo_path: str) -> Path:
        """
        Validate runtime prerequisites before starting generation.
        """
        # Verify WatsonX code service is healthy
        if not self.code_service.health_check():
            raise BobOrchestratorError(
                "WatsonX code service health check failed. "
                "Verify WATSONX_API_KEY and WATSONX_URL in .env"
            )

        resolved_repo_path = self.resolve_repo_path(repo_path)
        if not resolved_repo_path.exists() or not resolved_repo_path.is_dir():
            raise BobOrchestratorError(
                f"Repository path not found: {resolved_repo_path}. "
                "Update `DEMO_REPO_PATH` or pass a valid repo_path."
            )

        return resolved_repo_path

    def _scan_repo_context(self, repo_path: Path) -> str:
        """
        Scan repository files to build context string for WatsonX.

        Args:
            repo_path: Path to the repository

        Returns:
            String representation of repository structure and key files
        """
        context_lines = [f"Repository: {repo_path.name}", ""]

        # Walk the repo and list files
        context_lines.append("File Structure:")
        file_count = 0
        for root, dirs, files in os.walk(str(repo_path)):
            # Skip hidden dirs and common non-essential dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                       {'node_modules', '__pycache__', 'venv', 'env', '.git', 'dist', 'build'}]

            rel_root = Path(root).relative_to(repo_path)
            for f in files:
                if file_count > 50:
                    break
                rel_path = rel_root / f
                context_lines.append(f"  {rel_path}")
                file_count += 1

        context_lines.append("")

        # Read key files (up to a limit)
        key_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.yaml', '.yml', '.json', '.md'}
        total_chars = 0
        max_chars = 4000

        for root, dirs, files in os.walk(str(repo_path)):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                       {'node_modules', '__pycache__', 'venv', 'env', '.git', 'dist', 'build'}]

            for f in files:
                if total_chars > max_chars:
                    break
                file_path = Path(root) / f
                if file_path.suffix in key_extensions and file_path.stat().st_size < 5000:
                    try:
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                        rel_path = file_path.relative_to(repo_path)
                        context_lines.append(f"--- {rel_path} ---")
                        context_lines.append(content[:1000])
                        context_lines.append("")
                        total_chars += len(content[:1000])
                    except Exception:
                        pass

        return "\n".join(context_lines)

    def orchestrate(self, intent: Dict[str, Any], repo_path: str) -> Dict[str, Any]:
        """
        Run full orchestration: Architect→Plan→Code sequence using WatsonX.

        Args:
            intent: Structured intent dictionary with action, parameters, constraints
            repo_path: Path to the repository to modify

        Returns:
            Dictionary containing:
                - plan (list): Step-by-step implementation plan
                - files_generated (list): List of files created/modified
                - code_changes (dict): Map of file paths to their changes
                - bob_session_id (str): Unique session identifier
                - architect_output (dict): Repository analysis
                - execution_time (float): Total execution time in seconds

        Raises:
            BobOrchestratorError: If any step fails
        """
        session_id = str(uuid.uuid4())
        session_start = datetime.utcnow()

        resolved_repo_path = self.validate_runtime(repo_path)

        logger.info(f"Starting orchestration session: {session_id}")
        logger.info(f"Intent: {intent.get('action')} on {resolved_repo_path}")

        try:
            # Step 1: ARCHITECT - Analyze repository
            logger.info("Step 1: Running Architect mode")
            architect_output = self._run_architect(intent, str(resolved_repo_path), session_id)

            # Step 2: PLAN - Create implementation plan
            logger.info("Step 2: Running Plan mode")
            plan = self._run_plan(intent, architect_output, session_id)

            # Step 3: CODE - Generate code for each step
            logger.info("Step 3: Running Code mode")
            code_changes = self._run_code(plan, str(resolved_repo_path), session_id)

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

            logger.info(f"Orchestration completed successfully: {session_id}")
            logger.info(f"Generated {len(code_changes)} files in {execution_time:.2f}s")

            return result

        except Exception as e:
            error_msg = f"Orchestration failed: {str(e)}"
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
        Run Architect mode to analyze repository using WatsonX.

        Args:
            intent: Structured intent
            repo_path: Repository path
            session_id: Session identifier

        Returns:
            Repository analysis as dictionary
        """
        action = intent.get('action', 'unknown')
        parameters = intent.get('parameters', {})
        raw_text = intent.get('raw_text', '')

        # Build repo context
        repo_context = self._scan_repo_context(Path(repo_path))

        # Use the user's actual voice transcript as the task description
        # Fall back to structured action only if raw_text is missing
        if raw_text:
            task_description = raw_text
        else:
            task_description = f"{action} with parameters {json.dumps(parameters)}"

        try:
            architect_data = self.code_service.run_architect(repo_context, task_description)

            # Log output
            self._log_output(session_id, "architect", task_description, json.dumps(architect_data, indent=2))

            logger.info(f"Architect analysis complete: {len(architect_data.get('files_to_modify', []))} files to modify")
            return architect_data

        except WatsonxCodeServiceError as e:
            logger.error(f"Architect mode failed: {e}")
            raise BobOrchestratorError(f"Architect mode failed: {e}")

    def _run_plan(
        self,
        intent: Dict[str, Any],
        architect_output: Dict[str, Any],
        session_id: str
    ) -> List[Dict[str, Any]]:
        """
        Run Plan mode to create implementation plan using WatsonX.

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
        raw_text = intent.get('raw_text', '')

        # Use the user's actual voice transcript as the task description
        if raw_text:
            task_description = raw_text
        else:
            task_description = f"{action} with parameters {json.dumps(parameters)}"

        try:
            plan = self.code_service.run_plan(architect_output, task_description, constraints)

            # Log output
            self._log_output(session_id, "plan", task_description, json.dumps(plan, indent=2))

            logger.info(f"Plan created with {len(plan)} steps")
            return plan

        except WatsonxCodeServiceError as e:
            logger.error(f"Plan mode failed: {e}")
            raise BobOrchestratorError(f"Plan mode failed: {e}")

    def _run_code(
        self,
        plan: List[Dict[str, Any]],
        repo_path: str,
        session_id: str
    ) -> Dict[str, str]:
        """
        Run Code mode to generate code for each planned step using WatsonX.

        Args:
            plan: Implementation plan from Plan mode
            repo_path: Repository path
            session_id: Session identifier

        Returns:
            Dictionary mapping file paths to their generated content
        """
        code_changes = {}
        repo_context = self._scan_repo_context(Path(repo_path))

        for step in plan:
            step_num = step.get('step', 0)
            file_path = step.get('file_path', '')
            operation = step.get('operation', 'modify')
            description = step.get('description', '')

            logger.info(f"Generating code for step {step_num}: {operation} {file_path}")

            # Read existing file content for modify operations
            existing_code = ""
            if operation == "modify":
                full_path = Path(repo_path) / file_path
                if full_path.exists():
                    try:
                        existing_code = full_path.read_text(encoding='utf-8', errors='ignore')
                    except Exception:
                        pass

            try:
                code_content = self.code_service.run_code(
                    file_path=file_path,
                    operation=operation,
                    description=description,
                    repo_context=repo_context[:1500],
                    existing_code=existing_code
                )

                code_changes[file_path] = code_content

                # Log output
                self._log_output(
                    session_id, f"code_step_{step_num}",
                    f"{operation} {file_path}: {description}",
                    code_content
                )

                logger.info(f"Code generated for {file_path}: {len(code_content)} characters")

            except WatsonxCodeServiceError as e:
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
        Execute a code generation command using WatsonX API.

        This method maintains the same interface as the original Bob Shell
        subprocess version for backward compatibility with StreamingOrchestrator.

        Args:
            prompt: Command prompt
            session_id: Session identifier
            mode: Mode being used (for logging)
            max_retries: Maximum number of retry attempts

        Returns:
            Generated output as string
        """
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Running WatsonX command (attempt {attempt + 1}/{max_retries + 1}): {mode}")

                output = self.code_service._call_watsonx_api(
                    prompt=prompt,
                    max_new_tokens=2000,
                    temperature=0.2
                )

                # Log output to session file
                self._log_output(session_id, mode, prompt, output)

                return output

            except WatsonxCodeServiceError as e:
                logger.warning(f"WatsonX command failed (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    raise BobOrchestratorError(f"WatsonX command failed: {e}")

            except Exception as e:
                logger.warning(f"Unexpected error (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    raise BobOrchestratorError(f"Command failed: {e}")

        raise BobOrchestratorError("Command failed after all retries")

    def _extract_code_from_output(self, output: str) -> str:
        """
        Extract code content from output, handling markdown code blocks.
        Maintained for backward compatibility with StreamingOrchestrator.

        Args:
            output: Raw output

        Returns:
            Extracted code content
        """
        return self.code_service._extract_code_from_text(output)

    def _log_output(
        self,
        session_id: str,
        mode: str,
        prompt: str,
        output: str
    ):
        """
        Log command output to session file.

        Args:
            session_id: Session identifier
            mode: Mode
            prompt: Command prompt
            output: Command output
        """
        log_file = self.session_dir / f"{session_id}_{mode}.log"

        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== WatsonX {mode.upper()} Mode ===\n")
                f.write(f"Session ID: {session_id}\n")
                f.write(f"Timestamp: {datetime.utcnow().isoformat()}\n\n")
                f.write(f"=== PROMPT ===\n{prompt}\n\n")
                f.write(f"=== OUTPUT ===\n{output}\n")

            logger.debug(f"Logged output to {log_file}")
        except Exception as e:
            logger.warning(f"Failed to log output: {e}")

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
            "engine": "watsonx_granite",
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
