"""
IBM WatsonX service for PHRAXIS.
Uses IBM Granite model via watsonx.ai to enrich intent analysis.
"""
import json
import logging
import requests
from typing import Dict, Any
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_cloud_sdk_core import ApiException

from backend.env_loader import get_config

logger = logging.getLogger(__name__)


class WatsonxServiceError(Exception):
    """Raised when WatsonX service encounters an error."""
    pass


class WatsonxService:
    """
    IBM WatsonX service wrapper for intent enrichment.
    Uses IBM Granite model to analyze repository context and provide implementation hints.
    """
    
    def __init__(self):
        """Initialize WatsonX service with IBM credentials."""
        config = get_config()
        
        try:
            self.authenticator = IAMAuthenticator(config.WATSONX_API_KEY)
            self.project_id = config.WATSONX_PROJECT_ID
            self.model_id = config.WATSONX_MODEL_ID
            self.url = f"{config.WATSONX_URL}/ml/v1/text/generation?version=2023-05-29"
            
            logger.info("WatsonX service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WatsonX service: {e}")
            raise WatsonxServiceError(f"WatsonX initialization failed: {e}")
    
    def _get_access_token(self) -> str:
        """
        Get IAM access token for WatsonX API.
        
        Returns:
            Bearer token string
        """
        try:
            token = self.authenticator.token_manager.get_token()
            return token
        except Exception as e:
            logger.error(f"Failed to get access token: {e}")
            raise WatsonxServiceError(f"Failed to authenticate: {e}")
    
    def enrich_intent(self, intent: Dict[str, Any], repo_context: str) -> Dict[str, Any]:
        """
        Enrich intent with IBM Granite analysis.
        
        Analyzes the repository context and intent to provide:
        - Implementation hints (likely places to add code)
        - Risk level assessment
        - Estimated number of files to change
        
        Args:
            intent: Extracted intent dictionary from NLU
            repo_context: Repository structure and code context
        
        Returns:
            Enriched intent dictionary with additional fields:
                - implementation_hints: List of suggested implementation locations
                - risk_level: 'low', 'medium', or 'high'
                - estimated_files_changed: Number of files likely to change
                - granite_analysis: Full analysis from IBM Granite
        """
        logger.info(f"Enriching intent with IBM Granite: {intent.get('action')}")
        
        try:
            # Truncate repo context to avoid token limits
            truncated_context = repo_context[:2000] if len(repo_context) > 2000 else repo_context
            
            # Create prompt for IBM Granite
            prompt = self._create_analysis_prompt(intent, truncated_context)
            
            # Call WatsonX API
            response = self._call_watsonx_api(prompt)
            
            # Parse Granite's response
            analysis = self._parse_granite_response(response)
            
            # Enrich the original intent
            enriched_intent = {
                **intent,
                "implementation_hints": analysis.get("implementation_hints", []),
                "risk_level": analysis.get("risk_level", "medium"),
                "estimated_files_changed": analysis.get("estimated_files_changed", 3),
                "granite_analysis": analysis
            }
            
            logger.info(f"Intent enriched successfully. Risk level: {enriched_intent['risk_level']}")
            return enriched_intent
            
        except Exception as e:
            logger.error(f"Error enriching intent: {e}")
            # Return original intent with default enrichment on error
            return {
                **intent,
                "implementation_hints": ["Unable to generate hints"],
                "risk_level": "medium",
                "estimated_files_changed": 3,
                "granite_analysis": {"error": str(e)}
            }
    
    def _create_analysis_prompt(self, intent: Dict[str, Any], repo_context: str) -> str:
        """
        Create analysis prompt for IBM Granite.
        
        Args:
            intent: Intent dictionary
            repo_context: Repository context
        
        Returns:
            Formatted prompt string
        """
        action = intent.get('action', 'unknown')
        target_module = intent.get('target_module', 'unknown')
        parameters = intent.get('parameters', {})
        
        prompt = f"""You are an expert software architect analyzing a codebase for feature implementation.

Repository Context:
{repo_context}

Feature Request:
- Action: {action}
- Target Module: {target_module}
- Parameters: {parameters}

Task: Analyze where this feature should be implemented in the codebase.

Provide your analysis in the following JSON format:
{{
  "implementation_hints": [
    "Specific file or module where implementation should occur",
    "Another likely location",
    "Third possible location"
  ],
  "risk_level": "low|medium|high",
  "estimated_files_changed": <number>,
  "reasoning": "Brief explanation of your analysis"
}}

Risk levels:
- low: Simple change, isolated impact, well-defined scope
- medium: Moderate complexity, some cross-file dependencies
- high: Complex change, many dependencies, potential breaking changes

Respond with ONLY the JSON object, no additional text."""

        return prompt
    
    def _call_watsonx_api(self, prompt: str) -> Dict[str, Any]:
        """
        Call WatsonX API with the given prompt.
        
        Args:
            prompt: Prompt text for IBM Granite
        
        Returns:
            API response dictionary
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
                    "max_new_tokens": 500,
                    "min_new_tokens": 50,
                    "temperature": 0.7,
                    "top_k": 50,
                    "top_p": 1,
                    "repetition_penalty": 1.0
                },
                "project_id": self.project_id
            }
            
            logger.info(f"Calling WatsonX API: {self.url}")
            
            response = requests.post(
                self.url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"WatsonX API request failed: {e}")
            raise WatsonxServiceError(f"API request failed: {e}")
    
    def _parse_granite_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse IBM Granite's response.
        
        Args:
            response: Raw API response
        
        Returns:
            Parsed analysis dictionary
        """
        try:
            # Extract generated text from response
            results = response.get("results", [])
            if not results:
                logger.warning("No results in WatsonX response")
                return self._get_default_analysis()
            
            generated_text = results[0].get("generated_text", "")
            
            # Clean up the text (remove markdown code blocks if present)
            cleaned_text = generated_text.strip()
            if cleaned_text.startswith("```"):
                lines = cleaned_text.split("\n")
                cleaned_text = "\n".join(lines[1:-1])
            
            analysis = json.loads(cleaned_text)
            
            # Validate required fields
            if "implementation_hints" not in analysis:
                analysis["implementation_hints"] = []
            if "risk_level" not in analysis:
                analysis["risk_level"] = "medium"
            if "estimated_files_changed" not in analysis:
                analysis["estimated_files_changed"] = 3
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Granite response as JSON: {e}")
            logger.debug(f"Raw response: {response}")
            return self._get_default_analysis()
        except Exception as e:
            logger.error(f"Error parsing Granite response: {e}")
            return self._get_default_analysis()
    
    def _get_default_analysis(self) -> Dict[str, Any]:
        """
        Get default analysis when parsing fails.
        
        Returns:
            Default analysis dictionary
        """
        return {
            "implementation_hints": [
                "Review main application files",
                "Check service layer modules",
                "Examine middleware components"
            ],
            "risk_level": "medium",
            "estimated_files_changed": 3,
            "reasoning": "Default analysis due to parsing error"
        }
    
    def health_check(self) -> bool:
        """
        Check if WatsonX service is accessible.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Try to get access token as health check
            self._get_access_token()
            logger.info("WatsonX service health check passed")
            return True
        except Exception as e:
            logger.error(f"WatsonX service health check failed: {e}")
            return False

# Made with Bob
