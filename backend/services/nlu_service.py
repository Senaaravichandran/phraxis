"""
IBM Watson Natural Language Understanding service for PHRAXIS.
Extracts structured intent from transcribed voice commands.
"""
import logging
import re
from typing import Dict, Any, List, Optional, cast
from io import BytesIO
from ibm_watson import NaturalLanguageUnderstandingV1
from ibm_watson.natural_language_understanding_v1 import (
    Features,
    EntitiesOptions,
    KeywordsOptions,
    SemanticRolesOptions,
    ConceptsOptions
)
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_cloud_sdk_core import ApiException

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from env_loader import get_config

logger = logging.getLogger(__name__)


class NLUServiceError(Exception):
    """Raised when Natural Language Understanding service encounters an error."""
    pass


class NLUService:
    """
    IBM Watson Natural Language Understanding service wrapper.
    Extracts structured intent from natural language developer commands.
    """
    
    def __init__(self):
        """Initialize the NLU service with IBM credentials."""
        config = get_config()
        
        try:
            authenticator = IAMAuthenticator(config.IBM_NLU_API_KEY)
            self.nlu = NaturalLanguageUnderstandingV1(
                version='2022-04-07',
                authenticator=authenticator
            )
            self.nlu.set_service_url(config.IBM_NLU_URL)
            logger.info("NLU service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize NLU service: {e}")
            raise NLUServiceError(f"NLU initialization failed: {e}")
    
    def extract_intent(self, text: str) -> Dict[str, Any]:
        """
        Extract structured intent from natural language text.
        
        Args:
            text: Natural language command from developer
        
        Returns:
            Dictionary containing:
                - action (str): The primary action to perform
                - target_module (str): Module/component to modify
                - parameters (dict): Extracted parameters for the action
                - constraints (list): Additional constraints or requirements
                - raw_text (str): Original input text
                - confidence (float): Overall confidence score
        
        Raises:
            NLUServiceError: If intent extraction fails
        """
        if not text or text.strip() == "":
            logger.warning("Empty text provided for intent extraction")
            return {
                "action": "unknown",
                "target_module": "unknown",
                "parameters": {},
                "constraints": [],
                "raw_text": "",
                "confidence": 0.0,
                "error": "No text provided"
            }
        
        try:
            logger.info(f"Extracting intent from: '{text}'")
            
            # Call IBM Watson NLU API
            response = self.nlu.analyze(
                text=text,
                features=Features(
                    entities=EntitiesOptions(sentiment=False, limit=10),
                    keywords=KeywordsOptions(sentiment=False, limit=10),
                    semantic_roles=SemanticRolesOptions(),
                    concepts=ConceptsOptions(limit=5)
                ),
                language='en'
            ).get_result()
            
            # Post-process NLU response into structured intent
            # Cast response to Dict since get_result() returns DetailedResponse which behaves like a dict
            response_dict = cast(Dict[str, Any], response)
            intent = self._parse_nlu_response(text, response_dict)
            
            logger.info(f"Intent extracted: action={intent['action']}, module={intent['target_module']}")
            return intent
            
        except ApiException as e:
            error_msg = f"IBM Watson NLU API error: {e.code} - {e.message}"
            logger.error(error_msg)
            raise NLUServiceError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error during intent extraction: {str(e)}"
            logger.error(error_msg)
            raise NLUServiceError(error_msg)
    
    def _parse_nlu_response(self, text: str, nlu_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse NLU response into structured intent format.
        Handles the demo scenario and general feature requests.
        
        Args:
            text: Original input text
            nlu_response: Raw response from IBM NLU
        
        Returns:
            Structured intent dictionary
        """
        # Extract entities, keywords, and semantic roles
        entities = nlu_response.get('entities', [])
        keywords = nlu_response.get('keywords', [])
        semantic_roles = nlu_response.get('semantic_roles', [])
        concepts = nlu_response.get('concepts', [])
        
        # Determine action from semantic roles and keywords
        action = self._extract_action(text, semantic_roles, keywords)
        
        # Determine target module
        target_module = self._extract_target_module(text, entities, keywords)
        
        # Extract parameters
        parameters = self._extract_parameters(text, entities, keywords)
        
        # Extract constraints
        constraints = self._extract_constraints(text, semantic_roles)
        
        # Calculate confidence score
        confidence = self._calculate_confidence(entities, keywords, semantic_roles)
        
        return {
            "action": action,
            "target_module": target_module,
            "parameters": parameters,
            "constraints": constraints,
            "raw_text": text,
            "confidence": confidence,
            "nlu_metadata": {
                "entities": entities,
                "keywords": [kw['text'] for kw in keywords],
                "concepts": [c['text'] for c in concepts]
            }
        }
    
    def _extract_action(
        self,
        text: str,
        semantic_roles: List[Dict],
        keywords: List[Dict]
    ) -> str:
        """Extract the primary action from text."""
        text_lower = text.lower()
        
        # Check for common actions
        action_patterns = {
            'add_rate_limiting': ['rate limit', 'rate-limit', 'rate limiting', 'throttle', 'limit requests'],
            'add_authentication': ['auth', 'authentication', 'login', 'sign in', 'jwt'],
            'add_validation': ['validate', 'validation', 'check', 'verify'],
            'add_logging': ['log', 'logging', 'track', 'monitor'],
            'add_caching': ['cache', 'caching', 'redis', 'memcache'],
            'add_endpoint': ['endpoint', 'route', 'api', 'rest'],
            'add_middleware': ['middleware', 'interceptor', 'filter'],
            'add_database': ['database', 'db', 'sql', 'postgres', 'mysql'],
            'add_feature': ['feature', 'functionality', 'capability'],
            'refactor': ['refactor', 'restructure', 'reorganize'],
            'optimize': ['optimize', 'improve', 'enhance', 'speed up'],
            'fix_bug': ['fix', 'bug', 'error', 'issue', 'problem']
        }
        
        # Match action patterns
        for action, patterns in action_patterns.items():
            if any(pattern in text_lower for pattern in patterns):
                return action
        
        # Extract verb from semantic roles
        for role in semantic_roles:
            if role.get('action', {}).get('verb', {}).get('text'):
                verb = role['action']['verb']['text'].lower()
                if verb in ['add', 'create', 'implement', 'build']:
                    return 'add_feature'
                elif verb in ['update', 'modify', 'change']:
                    return 'modify_feature'
                elif verb in ['remove', 'delete']:
                    return 'remove_feature'
        
        return 'add_feature'
    
    def _extract_target_module(
        self,
        text: str,
        entities: List[Dict],
        keywords: List[Dict]
    ) -> str:
        """Extract the target module/component."""
        text_lower = text.lower()
        
        # Module patterns
        module_patterns = {
            'middleware': ['middleware', 'interceptor', 'filter', 'rate limit'],
            'authentication': ['auth', 'login', 'jwt', 'token', 'session'],
            'database': ['database', 'db', 'model', 'schema', 'table'],
            'api': ['api', 'endpoint', 'route', 'controller'],
            'service': ['service', 'business logic', 'handler'],
            'utils': ['util', 'helper', 'common'],
            'config': ['config', 'settings', 'environment'],
            'tests': ['test', 'testing', 'spec']
        }
        
        for module, patterns in module_patterns.items():
            if any(pattern in text_lower for pattern in patterns):
                return module
        
        return 'service'
    
    def _extract_parameters(
        self,
        text: str,
        entities: List[Dict],
        keywords: List[Dict]
    ) -> Dict[str, Any]:
        """Extract parameters from text using pattern matching and NLU entities."""
        parameters = {}
        text_lower = text.lower()
        
        # Extract numeric values with context
        # Pattern: number + unit/context
        number_patterns = [
            (r'(\d+)\s*(?:requests?|req)?\s*per\s*minute', 'per_minute_limit'),
            (r'(\d+)\s*(?:requests?|req)?\s*per\s*hour', 'per_hour_limit'),
            (r'(\d+)\s*(?:requests?|req)?\s*per\s*second', 'per_second_limit'),
            (r'(\d+)\s*(?:requests?|req)?\s*per\s*day', 'per_day_limit'),
        ]
        
        for pattern, param_name in number_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                parameters[param_name] = int(matches[0])
        
        # Extract rate limiting specific parameters
        if 'rate limit' in text_lower or 'rate-limit' in text_lower:
            # Free tier limit
            free_match = re.search(r'(\d+)\s*(?:requests?)?\s*(?:per\s*minute)?\s*for\s*free', text_lower)
            if free_match:
                parameters['free_tier_limit'] = int(free_match.group(1))
                parameters['window'] = 'minute'
            
            # Premium tier limit
            premium_match = re.search(r'(\d+)\s*for\s*premium', text_lower)
            if premium_match:
                parameters['premium_limit'] = int(premium_match.group(1))
            
            # Error code
            error_code_match = re.search(r'(?:return\s*)?(\d{3})', text_lower)
            if error_code_match:
                parameters['error_code'] = int(error_code_match.group(1))
        
        # Extract tier information
        if 'free' in text_lower:
            parameters['has_free_tier'] = True
        if 'premium' in text_lower or 'paid' in text_lower:
            parameters['has_premium_tier'] = True
        
        # Extract entities as parameters
        for entity in entities:
            entity_type = entity.get('type', '')
            entity_text = entity.get('text', '')
            
            if entity_type == 'Number':
                # Try to determine what the number represents
                if 'limit' not in parameters:
                    parameters['limit'] = entity_text
        
        return parameters
    
    def _extract_constraints(
        self,
        text: str,
        semantic_roles: List[Dict]
    ) -> List[str]:
        """Extract constraints and requirements from text."""
        constraints = []
        text_lower = text.lower()
        
        # Common constraint patterns
        constraint_patterns = [
            ('retry-after', 'return retry-after header'),
            ('header', 'include appropriate headers'),
            ('error message', 'provide clear error messages'),
            ('log', 'add logging'),
            ('test', 'include tests'),
            ('documentation', 'update documentation'),
            ('backward compatible', 'maintain backward compatibility'),
            ('async', 'use async/await'),
            ('type hint', 'add type hints'),
        ]
        
        for pattern, constraint in constraint_patterns:
            if pattern in text_lower:
                constraints.append(constraint)
        
        # Extract constraints from semantic roles
        for role in semantic_roles:
            if role.get('action', {}).get('verb', {}).get('text'):
                verb = role['action']['verb']['text'].lower()
                if verb in ['return', 'include', 'add', 'provide']:
                    obj = role.get('object', {})
                    if obj:
                        obj_text = obj.get('text', '')
                        if obj_text and obj_text not in [c for c in constraints]:
                            constraints.append(f"include {obj_text}")
        
        return constraints
    
    def _calculate_confidence(
        self,
        entities: List[Dict],
        keywords: List[Dict],
        semantic_roles: List[Dict]
    ) -> float:
        """Calculate overall confidence score based on NLU results."""
        # Base confidence on number and relevance of extracted features
        confidence = 0.5  # Base confidence
        
        # Add confidence for entities
        if entities:
            entity_confidence = sum(e.get('confidence', 0) for e in entities) / len(entities)
            confidence += entity_confidence * 0.2
        
        # Add confidence for keywords
        if keywords:
            keyword_confidence = sum(k.get('relevance', 0) for k in keywords) / len(keywords)
            confidence += keyword_confidence * 0.2
        
        # Add confidence for semantic roles
        if semantic_roles:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def health_check(self) -> bool:
        """
        Check if the NLU service is accessible and working.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Try a simple analysis as health check
            test_text = "Add a new feature to the application"
            self.nlu.analyze(
                text=test_text,
                features=Features(keywords=KeywordsOptions(limit=1)),
                language='en'
            ).get_result()
            logger.info("NLU service health check passed")
            return True
        except Exception as e:
            logger.error(f"NLU service health check failed: {e}")
            return False

# Made with Bob
