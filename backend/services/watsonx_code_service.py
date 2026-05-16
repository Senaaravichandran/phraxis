"""
IBM WatsonX Code Generation service for PHRAXIS.
Replaces Bob Shell CLI with WatsonX Granite API for code generation.
Handles Architect→Plan→Code pipeline using IBM Granite model.
"""
import json
import logging
import re
import requests
from typing import Dict, Any, List, Optional
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from env_loader import get_config

logger = logging.getLogger(__name__)


class WatsonxCodeServiceError(Exception):
    """Raised when WatsonX code generation encounters an error."""
    pass


class WatsonxCodeService:
    """
    IBM WatsonX-powered code generation service.
    Uses IBM Granite model to perform Architect→Plan→Code pipeline
    that previously relied on Bob Shell CLI.
    """

    def __init__(self):
        """Initialize WatsonX code service with IBM credentials."""
        config = get_config()

        try:
            self.authenticator = IAMAuthenticator(config.WATSONX_API_KEY)
            self.project_id = config.WATSONX_PROJECT_ID
            self.model_id = config.WATSONX_MODEL_ID
            self.url = f"{config.WATSONX_URL}/ml/v1/text/generation?version=2023-05-29"

            logger.info(f"WatsonX code service initialized (model: {self.model_id})")
        except Exception as e:
            logger.error(f"Failed to initialize WatsonX code service: {e}")
            raise WatsonxCodeServiceError(f"WatsonX code service initialization failed: {e}")

    def _get_access_token(self) -> str:
        """Get IAM access token for WatsonX API."""
        try:
            token = self.authenticator.token_manager.get_token()
            return token
        except Exception as e:
            logger.error(f"Failed to get access token: {e}")
            raise WatsonxCodeServiceError(f"Failed to authenticate: {e}")

    def _call_watsonx_api(
        self,
        prompt: str,
        max_new_tokens: int = 2000,
        temperature: float = 0.2,
        min_new_tokens: int = 50
    ) -> str:
        """
        Call WatsonX API with the given prompt and return generated text.

        Args:
            prompt: Prompt text for IBM Granite
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature (lower = more deterministic)
            min_new_tokens: Minimum tokens to generate

        Returns:
            Generated text from IBM Granite
        """
        try:
            access_token = self._get_access_token()

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            payload = {
                "model_id": self.model_id,
                "input": prompt,
                "parameters": {
                    "decoding_method": "greedy",
                    "max_new_tokens": max_new_tokens,
                    "min_new_tokens": min_new_tokens,
                    "temperature": temperature,
                    "top_k": 50,
                    "top_p": 1,
                    "repetition_penalty": 1.05
                },
                "project_id": self.project_id
            }

            logger.info(f"Calling WatsonX API (max_tokens={max_new_tokens})")

            response = requests.post(
                self.url,
                headers=headers,
                json=payload,
                timeout=120
            )

            response.raise_for_status()
            result = response.json()

            results = result.get("results", [])
            if not results:
                raise WatsonxCodeServiceError("No results returned from WatsonX API")

            generated_text = results[0].get("generated_text", "")
            logger.info(f"WatsonX generated {len(generated_text)} characters")
            return generated_text

        except requests.exceptions.RequestException as e:
            logger.error(f"WatsonX API request failed: {e}")
            raise WatsonxCodeServiceError(f"API request failed: {e}")

    def _parse_json_from_text(self, text: str) -> Any:
        """
        Parse JSON from generated text, handling markdown code blocks.

        Args:
            text: Raw generated text

        Returns:
            Parsed JSON data
        """
        cleaned = text.strip()

        # Try direct JSON parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try extracting from ```json ... ``` blocks
        json_match = re.search(r'```json\s*\n(.*?)\n```', cleaned, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try extracting from any ``` ... ``` blocks
        code_match = re.search(r'```\s*\n(.*?)\n```', cleaned, re.DOTALL)
        if code_match:
            try:
                return json.loads(code_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try to find JSON object or array in the text
        for pattern in [r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', r'(\[.*?\])']: 
            match = re.search(pattern, cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

        logger.warning("Could not parse JSON from WatsonX output")
        return {"raw_output": cleaned}

    def _extract_code_from_text(self, text: str) -> str:
        """
        Extract code content from generated text, handling markdown code blocks.

        Args:
            text: Raw generated text

        Returns:
            Extracted code content
        """
        cleaned = text.strip()

        # Look for code blocks with language specifier
        code_match = re.search(r'```(?:\w+)?\s*\n(.*?)\n```', cleaned, re.DOTALL)
        if code_match:
            return code_match.group(1)

        # If no code block found, return the entire output
        return cleaned

    # =========================================================================
    # ARCHITECT MODE
    # =========================================================================

    def run_architect(
        self,
        repo_context: str,
        task_description: str
    ) -> Dict[str, Any]:
        """
        Run Architect mode: analyze repository and identify change locations.

        Args:
            repo_context: Repository file structure and key code snippets
            task_description: Description of the task/feature to implement

        Returns:
            Dictionary with files_to_modify, new_files_to_create,
            functions_to_change, patterns_used
        """
        logger.info(f"Running WatsonX Architect mode for: {task_description}")

        prompt = f"""You are an expert software architect. Analyze the repository and identify what needs to change.

Repository Structure:
{repo_context[:3000]}

Task: {task_description}

CRITICAL RULES:
1. DO NOT suggest modifying unrelated files (e.g. app.py, config.py, payment services) unless explicitly required by the Task.
2. If the task asks to create a new file (like an HTML file), ONLY create that file. Do NOT modify backend config or routing unless requested.
3. Be minimal and precise.

Respond ONLY with a JSON object in this exact format (no additional text):
{{
  "files_to_modify": ["list of existing file paths that need changes"],
  "new_files_to_create": ["list of new file paths to create"],
  "functions_to_change": ["list of function names that need modification"],
  "patterns_used": ["list of code patterns identified in the repository"]
}}"""

        try:
            output = self._call_watsonx_api(prompt, max_new_tokens=1000, temperature=0.1)
            result = self._parse_json_from_text(output)

            # Ensure expected keys exist
            for key in ["files_to_modify", "new_files_to_create", "functions_to_change", "patterns_used"]:
                if key not in result:
                    result[key] = []

            logger.info(f"Architect analysis: {len(result.get('files_to_modify', []))} files to modify")
            return result

        except Exception as e:
            logger.error(f"Architect mode failed: {e}")
            raise WatsonxCodeServiceError(f"Architect mode failed: {e}")

    # =========================================================================
    # PLAN MODE
    # =========================================================================

    def run_plan(
        self,
        architect_output: Dict[str, Any],
        task_description: str,
        constraints: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Run Plan mode: create step-by-step implementation plan.

        Args:
            architect_output: Output from Architect mode
            task_description: Description of the task/feature
            constraints: Additional constraints

        Returns:
            List of implementation steps
        """
        logger.info(f"Running WatsonX Plan mode for: {task_description}")

        constraints_str = ", ".join(constraints) if constraints else "none"

        prompt = f"""You are an expert software architect creating an implementation plan.

Repository Analysis:
{json.dumps(architect_output, indent=2)[:2000]}

Task: {task_description}
Constraints: {constraints_str}

CRITICAL RULES:
1. ONLY plan steps that are directly relevant to the Task.
2. DO NOT plan modifications to unrelated files like config.py, app.py, or other services unless the Task explicitly requires wiring them up.
3. Keep the plan as minimal as possible to achieve the exact Task.

Create a step-by-step implementation plan. Respond ONLY with a JSON array (no additional text):
[
  {{
    "step": 1,
    "file_path": "path/to/file.py",
    "function_name": "function_to_modify_or_create",
    "operation": "modify",
    "description": "Detailed description of what to change"
  }}
]

Operations must be either "modify" or "create". Include all necessary steps."""

        try:
            output = self._call_watsonx_api(prompt, max_new_tokens=1500, temperature=0.1)
            result = self._parse_json_from_text(output)

            # Normalize to list
            if isinstance(result, dict):
                if "steps" in result:
                    plan = result["steps"]
                elif "plan" in result:
                    plan = result["plan"]
                else:
                    plan = [result]
            elif isinstance(result, list):
                plan = result
            else:
                plan = []

            logger.info(f"Plan created with {len(plan)} steps")
            return plan

        except Exception as e:
            logger.error(f"Plan mode failed: {e}")
            raise WatsonxCodeServiceError(f"Plan mode failed: {e}")

    # =========================================================================
    # CODE MODE
    # =========================================================================

    def run_code(
        self,
        file_path: str,
        operation: str,
        description: str,
        repo_context: str = "",
        existing_code: str = ""
    ) -> str:
        """
        Run Code mode: generate code for a specific file.

        Args:
            file_path: Path to the file to create/modify
            operation: "create" or "modify"
            description: What to implement
            repo_context: Repository context for pattern matching
            existing_code: Existing file content (for modify operations)

        Returns:
            Generated code content
        """
        logger.info(f"Running WatsonX Code mode: {operation} {file_path}")

        if operation == "modify" and existing_code:
            prompt = f"""You are an expert programmer. Modify the existing file to implement the requested change.

File: {file_path}
Operation: modify

Existing Code:
```
{existing_code[:2000]}
```

Change Required: {description}

Repository Context:
{repo_context[:1000]}

Write the COMPLETE modified file content. Follow existing code patterns exactly.
Output ONLY the code, wrapped in a code block with the appropriate language tag."""
        else:
            prompt = f"""You are an expert programmer. Create a new file to implement the requested functionality.

File: {file_path}
Operation: create

Requirement: {description}

Repository Context:
{repo_context[:1000]}

Write the COMPLETE file content. Follow existing code patterns from the repository.
Output ONLY the code, wrapped in a code block with the appropriate language tag."""

        try:
            output = self._call_watsonx_api(prompt, max_new_tokens=2000, temperature=0.2)
            code = self._extract_code_from_text(output)
            logger.info(f"Code generated for {file_path}: {len(code)} characters")
            return code

        except Exception as e:
            logger.error(f"Code generation failed for {file_path}: {e}")
            raise WatsonxCodeServiceError(f"Code generation failed: {e}")

    def health_check(self) -> bool:
        """Check if WatsonX code service is accessible."""
        try:
            self._get_access_token()
            logger.info("WatsonX code service health check passed")
            return True
        except Exception as e:
            logger.error(f"WatsonX code service health check failed: {e}")
            return False
