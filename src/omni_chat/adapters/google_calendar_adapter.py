import os
import pickle
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from .tool_adapter import ToolAdapter

# If modifying these scopes, delete the token.pickle file
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar.readonly'
]
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.pickle'

class CalendarAdapter(ToolAdapter):
    """Handles Google Calendar API interactions."""
    
    def __init__(self, credentials_file: str = None, token_file: str = None):
        """Initialize the CalendarAdapter with credentials.
        
        Args:
            credentials_file: Path to Google OAuth credentials JSON file
            token_file: Path to store the OAuth token
        """
        super().__init__(
            name="google_calendar",
            description="Google Calendar integration for managing events",
            tools=[
                {
                    'name': 'list_events',
                    'description': 'List upcoming events from Google Calendar',
                    'example': {'days': 7},
                    'side_effects': False
                }
            ]
        )
        
        self.credentials_file = credentials_file or os.path.join(
            os.path.dirname(__file__), '..', '..', '..', CREDENTIALS_FILE
        )
        self.token_file = token_file or os.path.join(
            os.path.dirname(__file__), '..', '..', '..', TOKEN_FILE
        )
        self.service = self._get_calendar_service()
    
    def _get_calendar_service(self):
        """Get an authorized Google Calendar API service instance."""
        creds = None
        
        # Load token if it exists
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, let the user log in
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
        
        return build('calendar', 'v3', credentials=creds)
    
    def list_events(self, days: str = "7") -> List[Dict[str, Any]]:
        """List upcoming events from the user's calendar.
        
        Args:
            days: Number of days to look ahead for events
            
        Returns:
            List of event dictionaries with 'summary', 'start', 'end', etc.
        """
        days = int(days)
        now = datetime.now(timezone.utc).isoformat()
        end_time = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        
        try:
            events_result = (self.service.events()
                           .list(calendarId='primary',
                                 timeMin=now,
                                 timeMax=end_time,
                                 singleEvents=True,
                                 orderBy='startTime')
                           .execute())
            
            events = events_result.get('items', [])
            
            # Format events for easier use
            formatted_events = []
            for event in events:
                if "dateTime" in event["start"]:
                    start = event['start']['dateTime']
                    end = event['end']['dateTime']
                else:
                    start = event['start']['date']
                    end = (datetime.fromisoformat(event['end']['date']) - timedelta(days=1)).date().isoformat()

                formatted_events.append({
                    'title': event.get('summary', '(No title)'),
                    'start': start,
                    'end': end,
                    'description': event.get('description', ''),
                    'location': event.get('location', '')
                })
            return formatted_events
            
        except Exception as e:
            print(f"Error accessing Google Calendar: {e}")
            return []

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    try:
        # Add project root to path to allow absolute imports
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
        from src.omni_chat.core.memory_db import MemoryDB
        
        # Initialize database and adapter
        db = MemoryDB()
        calendar = CalendarAdapter()
        
        # Register the adapter and its tools
        result = calendar.register(db)
        print(f"Calendar adapter registered with ID: {result['adapter_id']}")
        print("Registered tools:")
        for tool_name, tool_id in result['tool_ids'].items():
            print(f"- {tool_name}: {tool_id}")
        
        # Test the tool
        print("\nTesting calendar integration...")
        events = calendar.list_events("7")  # Get next 7 days of events
        
        if events:
            print("\nUpcoming events:")
            for i, event in enumerate(events, 1):
                print(f"{i}. {event['title']} - {event['start']} to {event['end']}")
        else:
            print("No upcoming events found.")
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)