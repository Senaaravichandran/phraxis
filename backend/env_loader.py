"""
Environment variable loader and validator for PHRAXIS backend.
Loads all required IBM service credentials and validates them on startup.
"""
import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


class EnvironmentError(Exception):
    """Raised when required environment variables are missing or invalid."""
    pass


class EnvConfig:
    """Environment configuration with validation."""
    
    # IBM Watson Speech-to-Text
    IBM_STT_API_KEY: str
    IBM_STT_URL: str
    
    # IBM Watson Natural Language Understanding
    IBM_NLU_API_KEY: str
    IBM_NLU_URL: str
    
    # IBM Cloudant Database
    IBM_CLOUDANT_URL: str
    IBM_CLOUDANT_API_KEY: str
    IBM_CLOUDANT_DB_NAME: str
    
    # IBM WatsonX AI
    WATSONX_API_KEY: str
    WATSONX_PROJECT_ID: str
    WATSONX_MODEL_ID: str
    WATSONX_URL: str
    
    # GitHub Integration
    GITHUB_TOKEN: str
    GITHUB_REPO_OWNER: str
    GITHUB_REPO_NAME: str
    
    def __init__(self):
        """Load and validate all environment variables."""
        self._load_and_validate()
    
    def _load_and_validate(self):
        """Load environment variables and validate they exist."""
        required_vars = {
            # IBM Watson STT
            'IBM_STT_API_KEY': 'IBM Watson Speech-to-Text API key',
            'IBM_STT_URL': 'IBM Watson Speech-to-Text service URL',
            
            # IBM Watson NLU
            'IBM_NLU_API_KEY': 'IBM Watson Natural Language Understanding API key',
            'IBM_NLU_URL': 'IBM Watson Natural Language Understanding service URL',
            
            # IBM Cloudant
            'IBM_CLOUDANT_URL': 'IBM Cloudant database URL',
            'IBM_CLOUDANT_API_KEY': 'IBM Cloudant API key',
            'IBM_CLOUDANT_DB_NAME': 'IBM Cloudant database name',
            
            # IBM WatsonX
            'WATSONX_API_KEY': 'IBM WatsonX API key',
            'WATSONX_PROJECT_ID': 'IBM WatsonX project ID',
            'WATSONX_MODEL_ID': 'IBM WatsonX model ID',
            'WATSONX_URL': 'IBM WatsonX service URL',
            
            # GitHub
            'GITHUB_TOKEN': 'GitHub personal access token',
            'GITHUB_REPO_OWNER': 'GitHub repository owner',
            'GITHUB_REPO_NAME': 'GitHub repository name',
        }
        
        missing_vars = []
        
        for var_name, description in required_vars.items():
            value = os.getenv(var_name)
            if not value or value.strip() == '':
                missing_vars.append(f"  - {var_name}: {description}")
            else:
                setattr(self, var_name, value.strip())
        
        if missing_vars:
            error_msg = (
                "Missing required environment variables:\n" +
                "\n".join(missing_vars) +
                "\n\nPlease set these variables in your .env file or environment."
            )
            raise EnvironmentError(error_msg)
    
    def get_all(self) -> Dict[str, Any]:
        """Return all configuration as a dictionary."""
        return {
            key: getattr(self, key)
            for key in dir(self)
            if not key.startswith('_') and key.isupper()
        }
    
    def __repr__(self) -> str:
        """String representation with masked sensitive values."""
        config_items = []
        for key in dir(self):
            if not key.startswith('_') and key.isupper():
                value = getattr(self, key)
                # Mask API keys and tokens
                if 'KEY' in key or 'TOKEN' in key:
                    masked_value = value[:8] + '...' if len(value) > 8 else '***'
                    config_items.append(f"{key}={masked_value}")
                else:
                    config_items.append(f"{key}={value}")
        return f"EnvConfig({', '.join(config_items)})"


# Global configuration instance
_config: EnvConfig | None = None


def get_config() -> EnvConfig:
    """
    Get the global configuration instance.
    Initializes on first call and validates all required environment variables.
    
    Returns:
        EnvConfig: The validated configuration instance
        
    Raises:
        EnvironmentError: If any required environment variables are missing
    """
    global _config
    if _config is None:
        _config = EnvConfig()
    return _config


def validate_environment():
    """
    Validate environment variables on application startup.
    Call this in main.py before starting the FastAPI server.
    
    Raises:
        EnvironmentError: If any required environment variables are missing
    """
    try:
        config = get_config()
        print("✓ Environment variables validated successfully")
        print(f"✓ Loaded configuration: {config}")
        return config
    except EnvironmentError as e:
        print(f"✗ Environment validation failed:\n{e}")
        raise

# Made with Bob
