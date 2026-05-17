"""
IBM Cloudant database service for PHRAXIS.
Stores and manages intent data and processing status.
"""
import logging
from typing import Dict, Any, List, Optional, cast
from datetime import datetime
from ibmcloudant.cloudant_v1 import CloudantV1, Document
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_cloud_sdk_core import ApiException

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from env_loader import get_config

logger = logging.getLogger(__name__)


class CloudantServiceError(Exception):
    """Raised when Cloudant service encounters an error."""
    pass


class CloudantService:
    """
    IBM Cloudant database service wrapper.
    Manages intent storage, retrieval, and status tracking.
    """
    
    def __init__(self, db_name: str = "phraxis_intents"):
        """Initialize the Cloudant service with IBM credentials."""
        config = get_config()
        
        try:
            authenticator = IAMAuthenticator(config.IBM_CLOUDANT_API_KEY)
            self.client = CloudantV1(authenticator=authenticator)
            self.client.set_service_url(config.IBM_CLOUDANT_URL)
            self.db_name = db_name
            
            # Ensure database exists
            self._ensure_database_exists()
            
            logger.info(f"Cloudant service initialized successfully for database: {self.db_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Cloudant service: {e}")
            raise CloudantServiceError(f"Cloudant initialization failed: {e}")
    
    def _ensure_database_exists(self):
        """Create database if it doesn't exist."""
        try:
            # Try to get database info
            self.client.get_database_information(db=self.db_name).get_result()
            logger.info(f"Database '{self.db_name}' exists")
        except ApiException as e:
            if e.code == 404:
                # Database doesn't exist, create it
                try:
                    self.client.put_database(db=self.db_name).get_result()
                    logger.info(f"Created database '{self.db_name}'")
                except ApiException as create_error:
                    logger.error(f"Failed to create database: {create_error}")
                    raise CloudantServiceError(f"Failed to create database: {create_error}")
            else:
                logger.error(f"Error checking database: {e}")
                raise CloudantServiceError(f"Error checking database: {e}")
    
    def save_intent(self, intent: Dict[str, Any]) -> str:
        """
        Save an intent document to Cloudant.
        
        Args:
            intent: Intent dictionary containing action, parameters, etc.
        
        Returns:
            Document ID of the saved intent
        
        Raises:
            CloudantServiceError: If save operation fails
        """
        try:
            # Add metadata
            document_dict = {
                **intent,
                "type": "intent",
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Saving intent: action={intent.get('action')}")
            
            # Save document - wrap dict in Document object
            result = self.client.post_document(
                db=self.db_name,
                document=Document(**document_dict)
            ).get_result()
            
            doc_id = result.get('id') if isinstance(result, dict) else None
            if not doc_id:
                raise CloudantServiceError("Failed to get document ID from Cloudant response")
            logger.info(f"Intent saved successfully with ID: {doc_id}")
            return doc_id
            
        except ApiException as e:
            error_msg = f"Cloudant API error while saving intent: {e.code} - {e.message}"
            logger.error(error_msg)
            raise CloudantServiceError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error while saving intent: {str(e)}"
            logger.error(error_msg)
            raise CloudantServiceError(error_msg)
    
    def get_intent(self, doc_id: str) -> Dict[str, Any]:
        """
        Retrieve an intent document by ID.
        
        Args:
            doc_id: Document ID to retrieve
        
        Returns:
            Intent document as dictionary
        
        Raises:
            CloudantServiceError: If retrieval fails or document not found
        """
        try:
            logger.info(f"Retrieving intent with ID: {doc_id}")
            
            response = self.client.get_document(
                db=self.db_name,
                doc_id=doc_id
            ).get_result()
            
            logger.info(f"Intent retrieved successfully: {doc_id}")
            # Type cast for proper type checking
            return cast(Dict[str, Any], response)
            
        except ApiException as e:
            if e.code == 404:
                error_msg = f"Intent not found: {doc_id}"
                logger.warning(error_msg)
                raise CloudantServiceError(error_msg)
            else:
                error_msg = f"Cloudant API error while retrieving intent: {e.code} - {e.message}"
                logger.error(error_msg)
                raise CloudantServiceError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error while retrieving intent: {str(e)}"
            logger.error(error_msg)
            raise CloudantServiceError(error_msg)
    
    def list_intents(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List recent intents from the database.
        
        Args:
            limit: Maximum number of intents to return (default: 20)
        
        Returns:
            List of intent documents
        
        Raises:
            CloudantServiceError: If listing fails
        """
        try:
            logger.info(f"Listing intents (limit: {limit})")
            
            # Query all documents of type "intent"
            response = self.client.post_find(
                db=self.db_name,
                selector={
                    "type": {"$eq": "intent"}
                },
                sort=[{"created_at": "desc"}],
                limit=limit
            ).get_result()
            
            # Type cast for proper type checking
            result = cast(Dict[str, Any], response)
            docs: List[Dict[str, Any]] = result.get('docs', [])
            logger.info(f"Retrieved {len(docs)} intents")
            return docs
            
        except ApiException as e:
            error_msg = f"Cloudant API error while listing intents: {e.code} - {e.message}"
            logger.error(error_msg)
            raise CloudantServiceError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error while listing intents: {str(e)}"
            logger.error(error_msg)
            raise CloudantServiceError(error_msg)
    
    def update_intent_status(
        self,
        doc_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update the status of an intent document.
        
        Args:
            doc_id: Document ID to update
            status: New status ("pending", "processing", "complete", "error")
            result: Optional result data to attach (e.g., generated code, PR URL, error details)
        
        Returns:
            True if update successful
        
        Raises:
            CloudantServiceError: If update fails
        """
        valid_statuses = ["pending", "processing", "quantum_optimized", "complete", "error"]
        if status not in valid_statuses:
            raise CloudantServiceError(f"Invalid status: {status}. Must be one of {valid_statuses}")
        
        try:
            logger.info(f"Updating intent {doc_id} status to: {status}")
            
            # Get current document
            doc = self.get_intent(doc_id)
            
            # Update fields
            doc['status'] = status
            doc['updated_at'] = datetime.utcnow().isoformat()
            
            if result:
                doc.update(result)
                doc['result'] = result
            
            # Save updated document - wrap dict in Document object
            response = self.client.post_document(
                db=self.db_name,
                document=Document(**doc)
            ).get_result()
            
            logger.info(f"Intent status updated successfully: {doc_id} -> {status}")
            return True
            
        except ApiException as e:
            error_msg = f"Cloudant API error while updating intent status: {e.code} - {e.message}"
            logger.error(error_msg)
            raise CloudantServiceError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error while updating intent status: {str(e)}"
            logger.error(error_msg)
            raise CloudantServiceError(error_msg)
    
    def delete_intent(self, doc_id: str) -> bool:
        """
        Delete an intent document.
        
        Args:
            doc_id: Document ID to delete
        
        Returns:
            True if deletion successful
        
        Raises:
            CloudantServiceError: If deletion fails
        """
        try:
            logger.info(f"Deleting intent: {doc_id}")
            
            # Get document to get its revision
            doc = self.get_intent(doc_id)
            rev = doc.get('_rev')
            
            # Delete document
            self.client.delete_document(
                db=self.db_name,
                doc_id=doc_id,
                rev=rev
            ).get_result()
            
            logger.info(f"Intent deleted successfully: {doc_id}")
            return True
            
        except ApiException as e:
            error_msg = f"Cloudant API error while deleting intent: {e.code} - {e.message}"
            logger.error(error_msg)
            raise CloudantServiceError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error while deleting intent: {str(e)}"
            logger.error(error_msg)
            raise CloudantServiceError(error_msg)
    
    def get_intents_by_status(self, status: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get intents filtered by status.
        
        Args:
            status: Status to filter by ("pending", "processing", "complete", "error")
            limit: Maximum number of intents to return
        
        Returns:
            List of intent documents with the specified status
        
        Raises:
            CloudantServiceError: If query fails
        """
        try:
            logger.info(f"Querying intents with status: {status} (limit: {limit})")
            
            result = self.client.post_find(
                db=self.db_name,
                selector={
                    "type": {"$eq": "intent"},
                    "status": {"$eq": status}
                },
                sort=[{"created_at": "desc"}],
                limit=limit
            ).get_result()
            
            if not isinstance(result, dict):
                raise CloudantServiceError(f"Unexpected response type from Cloudant: {type(result)}")
            
            docs: List[Dict[str, Any]] = result.get('docs', [])
            logger.info(f"Retrieved {len(docs)} intents with status: {status}")
            return docs
            
        except ApiException as e:
            error_msg = f"Cloudant API error while querying intents: {e.code} - {e.message}"
            logger.error(error_msg)
            raise CloudantServiceError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error while querying intents: {str(e)}"
            logger.error(error_msg)
            raise CloudantServiceError(error_msg)
    
    def health_check(self) -> bool:
        """
        Check if the Cloudant service is accessible and working.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Try to get database info as health check
            self.client.get_database_information(db=self.db_name).get_result()
            logger.info("Cloudant service health check passed")
            return True
        except Exception as e:
            logger.error(f"Cloudant service health check failed: {e}")
            return False

# Made with Bob
