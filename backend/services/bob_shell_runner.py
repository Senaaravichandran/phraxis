"""
Bob Shell runner utility for PHRAXIS.
Executes Bob commands via subprocess and parses structured output.
"""
import json
import logging
import subprocess
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class BobShellError(Exception):
    """Raised when Bob Shell execution fails."""
    pass


class BobShellRunner:
    """
    Utility class for running Bob Shell commands non-interactively.
    Handles subprocess execution, output parsing, and session logging.
    """
    
    def __init__(self, sessions_dir: str = "bob_sessions"):
        """
        Initialize Bob Shell runner.
        
        Args:
            sessions_dir: Directory to store Bob session outputs
        """
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(exist_ok=True)
        self.timeout = 120  # 2 minutes default timeout
    
    def _save_session(self, command: str, stdout: str, stderr: str, exit_code: int) -> str:
        """
        Save Bob Shell session output to file.
        
        Args:
            command: The Bob command that was executed
            stdout: Standard output from Bob
            stderr: Standard error from Bob
            exit_code: Process exit code
        
        Returns:
            Path to saved session file
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"bob_session_{timestamp}.json"
        filepath = self.sessions_dir / filename
        
        session_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "command": command,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr
        }
        
        with open(filepath, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        logger.info(f"Bob session saved to {filepath}")
        return str(filepath)
    
    def _execute_bob_command(self, command: str) -> Dict[str, Any]:
        """
        Execute a Bob Shell command via subprocess.
        
        Args:
            command: Full Bob command to execute
        
        Returns:
            Dictionary with stdout, stderr, exit_code, and session_file
        
        Raises:
            BobShellError: If command execution fails
        """
        logger.info(f"Executing Bob command: {command}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=os.getcwd()
            )
            
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            exit_code = result.returncode
            
            # Save session
            session_file = self._save_session(command, stdout, stderr, exit_code)
            
            if exit_code != 0:
                logger.error(f"Bob command failed with exit code {exit_code}")
                logger.error(f"stderr: {stderr}")
                raise BobShellError(f"Bob command failed: {stderr}")
            
            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "session_file": session_file
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"Bob command timed out after {self.timeout} seconds")
            raise BobShellError(f"Bob command timed out after {self.timeout} seconds")
        except Exception as e:
            logger.error(f"Error executing Bob command: {e}")
            raise BobShellError(f"Failed to execute Bob command: {str(e)}")
    
    def _parse_json_output(self, output: str) -> Any:
        """
        Parse JSON from Bob output, handling markdown code blocks.
        
        Args:
            output: Raw output from Bob
        
        Returns:
            Parsed JSON data
        """
        # Try direct JSON parse first
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        lines = output.split('\n')
        json_lines = []
        in_code_block = False
        
        for line in lines:
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                continue
            if in_code_block or (line.strip().startswith('{') or line.strip().startswith('[')):
                json_lines.append(line)
        
        if json_lines:
            try:
                json_str = '\n'.join(json_lines)
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # If all else fails, return as string
        logger.warning("Could not parse JSON from Bob output, returning raw text")
        return {"raw_output": output}
    
    def run_architect(self, repo_path: str, task_description: str) -> Dict[str, Any]:
        """
        Run Bob in Architect mode to analyze repository structure.
        
        Args:
            repo_path: Path to repository to analyze
            task_description: Description of the task/feature to implement
        
        Returns:
            Dictionary containing:
                - files_to_modify: List of files that need changes
                - new_files_to_create: List of new files to create
                - functions_to_change: List of functions to modify
                - patterns_used: List of code patterns identified
                - session_file: Path to saved session
        """
        command = (
            f'bob --non-interactive "Switch to Architect mode. '
            f'Read every file in {repo_path}. '
            f'Map all functions, classes, imports, and patterns. '
            f'Identify which files and functions need to change to implement: {task_description}. '
            f'Output as JSON: {{files_to_modify: [], new_files_to_create: [], '
            f'functions_to_change: [], patterns_used: []}}"'
        )
        
        result = self._execute_bob_command(command)
        parsed_output = self._parse_json_output(result["stdout"])
        
        return {
            **parsed_output,
            "session_file": result["session_file"]
        }
    
    def run_plan(self, context: Dict[str, Any], task_description: str) -> List[Dict[str, Any]]:
        """
        Run Bob in Plan mode to create implementation plan.
        
        Args:
            context: Context from Architect mode (repository map)
            task_description: Description of the task/feature to implement
        
        Returns:
            List of implementation steps, each containing:
                - file_path: Path to file to modify
                - function_name: Function to change (if applicable)
                - change_description: What to change
                - operation: 'modify' or 'create'
        """
        context_str = json.dumps(context, indent=2)
        
        command = (
            f'bob --non-interactive "Switch to Plan mode. '
            f'Given this repository map: {context_str}. '
            f'Create a step-by-step implementation plan for: {task_description}. '
            f'Each step must specify: file path, function name, exact change description, '
            f'and whether it is a modify or create operation. '
            f'Output as JSON array of steps."'
        )
        
        result = self._execute_bob_command(command)
        parsed_output = self._parse_json_output(result["stdout"])
        
        # Ensure we return a list
        if isinstance(parsed_output, dict):
            if "steps" in parsed_output:
                return parsed_output["steps"]
            elif "plan" in parsed_output:
                return parsed_output["plan"]
            else:
                return [parsed_output]
        elif isinstance(parsed_output, list):
            return parsed_output
        else:
            return []
    
    def run_code(self, file_path: str, instruction: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Run Bob in Code mode to generate code for a specific file.
        
        Args:
            file_path: Path to file to modify/create
            instruction: Specific instruction for what to implement
            context: Optional context from previous steps
        
        Returns:
            Generated code content
        """
        context_str = json.dumps(context, indent=2) if context else ""
        context_clause = f"With context: {context_str}. " if context else ""
        
        command = (
            f'bob --non-interactive "Switch to Code mode. '
            f'{context_clause}'
            f'Implement this specific change in {file_path}: {instruction}. '
            f'Follow the existing code patterns exactly. '
            f'Write the complete file content."'
        )
        
        result = self._execute_bob_command(command)
        
        # For code generation, return the raw output
        # Bob should output the complete file content
        return result["stdout"]
    
    def run_review(self, repo_path: str) -> Dict[str, Any]:
        """
        Run Bob review command on generated code.
        
        Args:
            repo_path: Path to repository to review
        
        Returns:
            Dictionary containing review findings:
                - issues: List of issues found
                - warnings: List of warnings
                - suggestions: List of suggestions
                - overall_status: 'pass' or 'fail'
        """
        command = f'bob --non-interactive "review {repo_path}"'
        
        try:
            result = self._execute_bob_command(command)
            parsed_output = self._parse_json_output(result["stdout"])
            
            # Structure the review output
            if isinstance(parsed_output, dict):
                return {
                    "issues": parsed_output.get("issues", []),
                    "warnings": parsed_output.get("warnings", []),
                    "suggestions": parsed_output.get("suggestions", []),
                    "overall_status": parsed_output.get("status", "unknown"),
                    "session_file": result["session_file"]
                }
            else:
                return {
                    "issues": [],
                    "warnings": [],
                    "suggestions": [],
                    "overall_status": "unknown",
                    "raw_output": str(parsed_output),
                    "session_file": result["session_file"]
                }
                
        except BobShellError as e:
            logger.warning(f"Bob review encountered issues: {e}")
            return {
                "issues": [str(e)],
                "warnings": [],
                "suggestions": [],
                "overall_status": "error",
                "session_file": None
            }
    
    def set_timeout(self, timeout: int):
        """
        Set timeout for Bob Shell commands.
        
        Args:
            timeout: Timeout in seconds
        """
        self.timeout = timeout
        logger.info(f"Bob Shell timeout set to {timeout} seconds")

# Made with Bob
