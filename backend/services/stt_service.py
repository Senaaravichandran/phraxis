"""
IBM Watson Speech-to-Text service for PHRAXIS.
Transcribes audio input from voice capture into text.
"""
import logging
from typing import Dict, Any, List
from ibm_watson import SpeechToTextV1
from ibm_watson.websocket import RecognizeCallback, AudioSource
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_cloud_sdk_core import ApiException

from backend.env_loader import get_config

logger = logging.getLogger(__name__)


class STTServiceError(Exception):
    """Raised when Speech-to-Text service encounters an error."""
    pass


class STTService:
    """
    IBM Watson Speech-to-Text service wrapper.
    Handles audio transcription with confidence scores and word-level timing.
    """
    
    def __init__(self):
        """Initialize the Speech-to-Text service with IBM credentials."""
        config = get_config()
        
        try:
            authenticator = IAMAuthenticator(config.IBM_STT_API_KEY)
            self.stt = SpeechToTextV1(authenticator=authenticator)
            self.stt.set_service_url(config.IBM_STT_URL)
            logger.info("STT service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize STT service: {e}")
            raise STTServiceError(f"STT initialization failed: {e}")
    
    def transcribe_audio(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/webm"
    ) -> Dict[str, Any]:
        """
        Transcribe audio bytes to text with confidence scores.
        
        Args:
            audio_bytes: Raw audio data as bytes
            content_type: MIME type of audio (e.g., 'audio/webm', 'audio/flac', 'audio/wav')
        
        Returns:
            Dictionary containing:
                - transcript (str): Full transcribed text
                - confidence (float): Overall confidence score (0.0-1.0)
                - words (list): List of word-level results with timing and confidence
                
        Raises:
            STTServiceError: If transcription fails or audio is invalid
        """
        # Handle empty audio
        if not audio_bytes or len(audio_bytes) == 0:
            logger.warning("Empty audio bytes received, returning empty transcript")
            return {
                "transcript": "",
                "confidence": 0.0,
                "words": [],
                "error": "No audio data provided"
            }
        
        try:
            logger.info(f"Transcribing audio: {len(audio_bytes)} bytes, type: {content_type}")
            
            # Call IBM Watson STT API
            response = self.stt.recognize(
                audio=audio_bytes,
                content_type=content_type,
                model='en-US_BroadbandModel',
                timestamps=True,
                word_confidence=True,
                smart_formatting=True,
                speaker_labels=False
            ).get_result()
            
            # Parse response
            if not response.get('results'):
                logger.warning("No transcription results returned")
                return {
                    "transcript": "",
                    "confidence": 0.0,
                    "words": [],
                    "error": "No speech detected in audio"
                }
            
            # Extract best alternative from results
            results = response['results']
            alternatives = results[0].get('alternatives', [])
            
            if not alternatives:
                logger.warning("No alternatives in transcription results")
                return {
                    "transcript": "",
                    "confidence": 0.0,
                    "words": [],
                    "error": "No transcription alternatives available"
                }
            
            best_alternative = alternatives[0]
            transcript = best_alternative.get('transcript', '').strip()
            confidence = best_alternative.get('confidence', 0.0)
            
            # Extract word-level details
            words = []
            if 'timestamps' in best_alternative:
                timestamps = best_alternative['timestamps']
                word_confidences = best_alternative.get('word_confidence', [])
                
                # Create word confidence lookup
                confidence_map = {word: conf for word, conf in word_confidences}
                
                for word_data in timestamps:
                    word_text = word_data[0]
                    start_time = word_data[1]
                    end_time = word_data[2]
                    
                    words.append({
                        'word': word_text,
                        'start_time': start_time,
                        'end_time': end_time,
                        'confidence': confidence_map.get(word_text, 0.0)
                    })
            
            result = {
                "transcript": transcript,
                "confidence": confidence,
                "words": words
            }
            
            logger.info(f"Transcription successful: '{transcript}' (confidence: {confidence:.2f})")
            return result
            
        except ApiException as e:
            error_msg = f"IBM Watson STT API error: {e.code} - {e.message}"
            logger.error(error_msg)
            raise STTServiceError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error during transcription: {str(e)}"
            logger.error(error_msg)
            raise STTServiceError(error_msg)
    
    def get_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available speech recognition models.
        Useful for debugging and model selection.
        
        Returns:
            List of available models with their details
        """
        try:
            models = self.stt.list_models().get_result()
            return models.get('models', [])
        except ApiException as e:
            logger.error(f"Failed to list STT models: {e}")
            return []
    
    def health_check(self) -> bool:
        """
        Check if the STT service is accessible and working.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Try to list models as a health check
            self.get_models()
            logger.info("STT service health check passed")
            return True
        except Exception as e:
            logger.error(f"STT service health check failed: {e}")
            return False

# Made with Bob
