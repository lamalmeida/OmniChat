# OmniChat

A simple chatbot framework using Google's Gemini API with conversation history storage.

## Features

- Integration with Google's Gemini API
- SQLite-based conversation history
- Simple REPL interface
- Configurable memory limit

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install the dependencies:
   ```bash
   pip install -e .
   ```

3. Create a `.env` file with your Gemini API key:
   ```bash
   cp .env.example .env
   # Edit .env and add your API key
   ```

## Usage

Run the chatbot:
```bash
omni-chat
```

Or directly with Python:
```bash
python -m omni_chat
```

In the REPL:
- Type your message and press Enter to chat
- Type 'exit' or 'quit' to exit

## Project Structure

- `src/omni_chat/core/` - Core functionality
  - `gemini_client.py` - Wrapper for Gemini API
  - `memory_db.py` - SQLite-based conversation storage
- `src/omni_chat/cli/` - Command-line interface
  - `repl.py` - Read-Eval-Print Loop for interactive chat
