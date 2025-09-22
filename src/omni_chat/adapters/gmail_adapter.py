import os
import base64
import pickle
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from .tool_adapter import ToolAdapter

# If modifying these scopes, delete the token.pickle file
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar.readonly'
]
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.pickle'

class GmailAdapter(ToolAdapter):
    """Handles Gmail API interactions."""
    
    def __init__(self, credentials_file: str = None, token_file: str = None):
        """Initialize the GmailAdapter with credentials.
        
        Args:
            credentials_file: Path to Google OAuth credentials JSON file
            token_file: Path to store the OAuth token
        """
        super().__init__(
            name="gmail",
            description="Gmail integration for reading and managing emails",
            tools=[
                {
                    'name': 'list_emails',
                    'description': 'List recent emails in your inbox',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'max_results': {
                                'type': 'integer',
                                'description': 'Maximum number of emails to return (default: 10)',
                                'default': 10
                            },
                            'label_ids': {
                                'type': 'array',
                                'items': {'type': 'string'},
                                'description': 'List of label IDs to filter emails',
                                'default': ['INBOX']
                            }
                        },
                        'required': []
                    }
                },
                {
                    'name': 'get_email',
                    'description': 'Get the full content of a specific email',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'email_id': {
                                'type': 'string',
                                'description': 'ID of the email to retrieve'
                            }
                        },
                        'required': ['email_id']
                    }
                }
            ]
        )
        
        self.credentials_file = credentials_file or CREDENTIALS_FILE
        self.token_file = token_file or TOKEN_FILE
        self.service = self._get_gmail_service()
    
    def _get_credentials(self):
        """Get valid user credentials from storage or prompt user to log in."""
        creds = None
        
        # Load token from file if it exists
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # If there are no valid credentials, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        return creds
    
    def _get_gmail_service(self):
        """Get an authorized Gmail API service instance."""
        creds = self._get_credentials()
        return build('gmail', 'v1', credentials=creds)
    
    def list_emails(self, max_results: int = 10, label_ids: List[str] = None) -> List[Dict[str, Any]]:
        """List recent emails from the user's inbox.
        
        Args:
            max_results: Maximum number of emails to return
            label_ids: List of label IDs to filter emails (default: INBOX)
            
        Returns:
            List of email summaries with id, subject, from, and date
        """
        label_ids = label_ids or ['INBOX']
        
        try:
            # Get list of messages
            results = self.service.users().messages().list(
                userId='me',
                labelIds=label_ids,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                return []
            
            # Get full message details for each message
            emails = []
            for message in messages:
                msg = self.service.users().messages().get(
                    userId='me',
                    id=message['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                # Extract headers
                headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}
                
                emails.append({
                    'id': msg['id'],
                    'threadId': msg['threadId'],
                    'snippet': msg.get('snippet', ''),
                    'subject': headers.get('subject', '(No subject)'),
                    'from': headers.get('from', 'Unknown'),
                    'date': headers.get('date', ''),
                    'labels': msg.get('labelIds', [])
                })
            
            return emails
            
        except Exception as e:
            print(f"Error listing emails: {e}")
            return []
    
    def get_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get the full content of a specific email.
        
        Args:
            email_id: ID of the email to retrieve
            
        Returns:
            Dictionary containing email details and content, or None if not found
        """
        try:
            # Get the full message
            message = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='full'
            ).execute()
            
            # Extract headers
            headers = {h['name'].lower(): h['value'] 
                      for h in message.get('payload', {}).get('headers', [])}
            
            # Get message body
            body = ""
            if 'parts' in message['payload']:
                for part in message['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        data = part['body'].get('data', '')
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
            
            return {
                'id': message['id'],
                'threadId': message['threadId'],
                'subject': headers.get('subject', '(No subject)'),
                'from': headers.get('from', 'Unknown'),
                'to': headers.get('to', ''),
                'date': headers.get('date', ''),
                'labels': message.get('labelIds', []),
                'body': body,
                'snippet': message.get('snippet', '')
            }
            
        except Exception as e:
            print(f"Error getting email: {e}")
            return None

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    try:
        # Add project root to path to allow absolute imports
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
        from src.omni_chat.core.memory_db import MemoryDB
        
        # Initialize database and adapter
        db = MemoryDB()
        gmail = GmailAdapter()
        
        # Register the adapter and its tools
        result = gmail.register(db)
        print(f"Gmail adapter registered with ID: {result['adapter_id']}")
        print("Registered tools:")
        for tool_id, tool_name in zip(result['tool_ids'], [tool['name'] for tool in gmail.tools]):
            print(f"- {tool_name} (ID: {tool_id})")
            
        # Test the adapter
        print("\nTesting Gmail adapter - Listing recent emails:")
        emails = gmail.list_emails(max_results=3)
        for email in emails:
            print(f"\nFrom: {email['from']}")
            print(f"Subject: {email['subject']}")
            print(f"Date: {email['date']}")
            print(f"Snippet: {email['snippet']}")
            print("-" * 50)
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)