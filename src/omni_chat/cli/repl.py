from ..core.gemini_client import GeminiClient
from ..core.memory_db import MemoryDB
from ..core.orchestrator import Orchestrator

class ChatREPL:
    """A simple REPL for interacting with the chatbot."""
    def __init__(self, memory_db: MemoryDB, LLM_client: GeminiClient, memory_limit: int = 5):
        """Initialize the REPL with memory and client.
        Args:
            memory_db: Instance of MemoryDB for conversation history
            gemini_client: Instance of GeminiClient for generating responses
            memory_limit: Number of recent messages to include in context
        """
        self.memory_db = memory_db
        self.LLM_client = LLM_client
        self.memory_limit = memory_limit
        self.orchestrator = Orchestrator(LLM_client, memory_db)
    
    def get_chat_context(self) -> str:
        """Get the conversation context from memory."""
        recent_messages = self.memory_db.get_recent_messages(self.memory_limit * 2)  # Get extra to ensure we have enough
        return recent_messages
    
    def run(self):
        """Run the REPL loop."""
        self.memory_db.clear_messages()
        print("OmniChat REPL - Type 'exit' to quit")
        print("Enter your message below:")
        
        try:
            while True:
                try:
                    # Get user input
                    
                    user_input = input("\nYou: ").strip()
                    
                    # Check for exit command
                    if user_input.lower() in ('exit', 'quit'):
                        print("Goodbye!")
                        break
                    
                    if not user_input:
                        continue
                    
                    # Store the user message 
                    self.memory_db.add_message("user", user_input)

                    # Get the conversation context
                    context = self.get_chat_context()

                    # Process the input using the orchestrator
                    response = self.orchestrator.process_message(context)
                    
                    # Store and display the assistant's response
                    self.memory_db.add_message("assistant", response)
                    print(f"\nAssistant: {response}")
                    
                except KeyboardInterrupt:
                    print("\nUse 'exit' to quit")
                    continue
                except EOFError:
                    print("\nGoodbye!")
                    break
                except Exception as e:
                    print(f"\nError: {str(e)}")
                    continue
                    
        except Exception as e:
            print(f"Fatal error: {str(e)}")
            raise

def main():
    """Main entry point for the REPL."""
    try:
        # Initialize components
        memory_db = MemoryDB()
        LLM_client = GeminiClient()
        # Start the REPL
        repl = ChatREPL(memory_db, LLM_client)
        repl.run()
        
    except Exception as e:
        print(f"Failed to start OmniChat: {str(e)}")

if __name__ == "__main__":
    main()
