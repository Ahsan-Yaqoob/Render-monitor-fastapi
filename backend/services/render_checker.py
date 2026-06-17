import requests
from datetime import datetime
from backend.config.settings import settings
from backend.utils.logger import logger
from backend.database.models import IssueType


class RenderChecker:
    """Service for checking Render service status."""

    def __init__(self):
        self.api_key = settings.RENDER_API_KEY
        self.service_id = settings.RENDER_SERVICE_ID
        self.api_url = settings.RENDER_API_URL
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def _get_service_data(self):
        """Fetch service metadata from Render API. Returns raw dict or None."""
        try:
            endpoint = f'{self.api_url}/services/{self.service_id}'
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Render API returned HTTP {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching service data: {e}")
            return None

    def _get_service_url(self, data):
        """Extract the public URL from Render API service data."""
        service_details = data.get('serviceDetails', {})
        return service_details.get('url')

    def _check_url(self, url):
        """
        Perform an HTTP health check on the service URL.
        Returns (is_running, issue_type, error_msg).
        """
        try:
            response = requests.get(url, timeout=15, allow_redirects=True)
            if response.status_code < 500:
                return (True, 'NONE', None)
            else:
                return (False, IssueType.HTTP_ERROR.value, f'HTTP {response.status_code}')

        except requests.Timeout:
            logger.warning(f"Timeout checking URL: {url}")
            return (False, IssueType.TIMEOUT.value, 'Request timeout')

        except requests.ConnectionError as e:
            logger.warning(f"Connection error checking URL: {url} — {e}")
            return (False, IssueType.CONNECTION_ERROR.value, 'Connection error')

        except Exception as e:
            logger.error(f"Unexpected error checking URL: {url} — {e}")
            return (False, IssueType.UNKNOWN.value, str(e))

    def check_service_status(self):
        """
        Check the status of the Render service.
        Strategy:
          1. Fetch service metadata from Render API.
          2. If service is manually suspended → DOWN.
          3. Otherwise do an HTTP health check on the service URL.
        Returns tuple: (is_running, issue_type, error_message)
        """
        try:
            data = self._get_service_data()

            if data is None:
                return (False, IssueType.CONNECTION_ERROR.value, 'Could not reach Render API')

            # Log key fields for debugging
            logger.info(
                f"Render API - suspended: '{data.get('suspended')}' | "
                f"name: '{data.get('name')}' | type: '{data.get('type')}'"
            )

            # Check if service is manually suspended via Render dashboard
            if data.get('suspended') == 'suspended':
                logger.warning("Service is manually suspended on Render")
                return (False, IssueType.HTTP_ERROR.value, 'Service is suspended')

            # Get service URL for live health check
            service_url = self._get_service_url(data)

            if not service_url:
                logger.error("Could not find service URL in Render API response")
                return (False, IssueType.UNKNOWN.value, 'Service URL not found')

            logger.info(f"Running HTTP health check on: {service_url}")
            return self._check_url(service_url)

        except Exception as e:
            logger.error(f"Unexpected error in check_service_status: {e}")
            return (False, IssueType.UNKNOWN.value, str(e))

    def get_service_info(self):
        """Get detailed information about the service."""
        try:
            data = self._get_service_data()
            if not data:
                return None
            return {
                'id': data.get('id'),
                'name': data.get('name'),
                'type': data.get('type'),
                'suspended': data.get('suspended'),
                'created_at': data.get('createdAt'),
                'updated_at': data.get('updatedAt'),
                'url': self._get_service_url(data),
            }
        except Exception as e:
            logger.error(f"Error getting service info: {e}")
            return None

    def validate_credentials(self):
        """Validate API credentials."""
        try:
            endpoint = f'{self.api_url}/services/{self.service_id}'
            response = requests.get(endpoint, headers=self.headers, timeout=5)
            if response.status_code == 401:
                logger.error("Invalid API key")
                return False
            elif response.status_code == 404:
                logger.error("Invalid service ID")
                return False
            elif response.status_code == 200:
                logger.info("Credentials validated successfully")
                return True
            else:
                logger.warning(f"Unexpected response: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error validating credentials: {e}")
            return False
