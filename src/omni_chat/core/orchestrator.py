from typing import Dict, Any, Optional, List, Callable, Type
import re
import json
import importlib
from datetime import datetime

def build_prompt(messages: List[Dict[str, str]], tools: List[Dict[str, Any]], 
                system: str = None, examples: List[Dict[str, str]] = None) -> dict:
    """Build a prompt for the language model.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        tools: List of available tools
        system: Optional system message
        examples: Optional examples for few-shot learning
        
    Returns:
        Formatted prompt dictionary
    """
    formatted_messages = [
        {"role": msg["role"].lower(), "text": str(msg["content"])}
        for msg in messages
    ]
    
    if system is None:
        system = """You are a helpful assistant with access to tools. 
        Always respond with valid JSON in one of these formats:
        
        For a normal response:
        {"type": "reply", "text": "Your response here"}
        
        For a tool call:
        {
            "type": "tool_call",
            "tool": "adapter.tool_name",
            "params": {"param1": value1, "param2": value2},
            "confirm": false
        }
        """
    
    # Format tools for the prompt
    formatted_tools = []
    for tool in tools:
        formatted_tool = {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "example": tool.get("example", {})
        }
        if "side_effects" in tool:
            formatted_tool["side_effects"] = tool["side_effects"]
        formatted_tools.append(formatted_tool)
    
    prompt = {
        "system": system,
        "tools": formatted_tools,
        "messages": formatted_messages,
        "current_time": datetime.now().isoformat()
    }
    
    if examples:
        prompt["examples"] = examples
    
    return prompt

class Orchestrator:
    """Orchestrates between the language model and various tools."""
    
    def __init__(self, LLM_client, memory_db):
        """Initialize the orchestrator with required services.
        
        Args:
            LLM_client: Instance of LLM client
            memory_db: Instance of MemoryDB for tool registration
        """
        self.LLM_client = LLM_client
        self.memory_db = memory_db
        self._load_tools()
        self._tool_cache = {}  # Cache for instantiated adapters
    
    def _load_tools(self):
        """Load tools from the database and prepare them for use."""
        self.tools = self.memory_db.get_tools()
        self._tool_mapping = {
            tool["name"]: tool for tool in self.tools
        }
    
    def process_message(self, context: List[Dict[str, str]]) -> str:
        """Process user input using the language model and available tools.
        
        Args:
            context: List of message dicts with 'role' and 'content' keys
            
        Returns:
            The final response to show to the user
        """
        if not context:
            return "Error: No context provided"
            
        # Get the model's initial response
        prompt = build_prompt(context, self.tools)
        response = self.LLM_client.generate_response(json.dumps(prompt))
        
        try:
            response = self._handle_model_response(response)
            
            # Process tool calls if any
            count = 0
            while response["action"] == "tool_call" and count < 3:
                tool_name = response["tool"]
                params = response.get("params", {})
                confirm = response.get("confirm", False)
                
                # Execute the tool
                tool_result = self._execute_tool(tool_name, params)
                
                # Add tool call and result to context
                tool_call_msg = f"Called {tool_name} with params: {params}"
                context.append({"role": "assistant", "content": tool_call_msg})
                context.append({"role": "system", "content": str(tool_result)})
                
                # Get new response with updated context
                prompt = build_prompt(context, self.tools)
                response = self.LLM_client.generate_response(json.dumps(prompt))
                response = self._handle_model_response(response)
                count += 1
                
            return response["text"]
            
        except Exception as e:
            return f"Error processing request: {str(e)}"
    
    def _handle_model_response(self, response: str) -> Dict[str, Any]:
        """Parse and validate the model's response."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            return {
                "action": "reply",
                "text": f"Invalid JSON response from model: {str(e)}. Please try again."
            }
        
        rtype = data.get("type", "").lower()
        
        if rtype == "reply":
            return {
                "action": "reply",
                "text": data.get("text", "")
            }
        
        elif rtype == "tool_call":
            tool_name = data.get("tool", "")
            if not tool_name:
                return {
                    "action": "reply",
                    "text": "Error: No tool specified in tool call"
                }
                
            # Validate tool exists
            if tool_name not in self._tool_mapping:
                return {
                    "action": "reply",
                    "text": f"Error: Unknown tool '{tool_name}'. Available tools: {', '.join(self._tool_mapping.keys())}"
                }
                
            return {
                "action": "tool_call",
                "tool": tool_name,
                "params": data.get("params", {}),
                "confirm": data.get("confirm", False)
            }
        
        return {
            "action": "reply",
            "text": f"Error: Invalid response type '{rtype}'. Expected 'reply' or 'tool_call'."
        }
    
    def _execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Execute a tool with the given parameters."""
        if tool_name not in self._tool_mapping:
            return {"error": f"Unknown tool: {tool_name}"}
            
        tool_info = self._tool_mapping[tool_name]
        adapter_name = tool_info.get("adapter")
        try:
            # Get or create the adapter instance
            if adapter_name not in self._tool_cache:
                adapter_class = self._load_adapter_class(adapter_name)
                
                if not adapter_class:
                    print(f"Could not load adapter: {adapter_name}")
                    return {"error": f"Could not load adapter: {adapter_name}"}
                self._tool_cache[adapter_name] = adapter_class()
                
            adapter = self._tool_cache[adapter_name]
            method_name = tool_name.split('.')[-1]  # Get just the method name
            
            if not hasattr(adapter, method_name):
                print(f"Adapter '{adapter_name}' has no method '{method_name}'")
                return {"error": f"Adapter '{adapter_name}' has no method '{method_name}'"}
                
            method = getattr(adapter, method_name)
            
            # Validate parameters
            import inspect
            sig = inspect.signature(method)
            valid_params = {}
            
            for param_name, param in sig.parameters.items():
                if param_name in params:
                    valid_params[param_name] = params[param_name]
                elif param.default != inspect.Parameter.empty:
                    valid_params[param_name] = param.default
                elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                    continue  # Skip *args
                elif param.kind == inspect.Parameter.VAR_KEYWORD:
                    valid_params.update(params)  # Include all remaining params
                    break
                else:
                    return {"error": f"Missing required parameter: {param_name}"}
            
            # Execute the method
            result = method(**valid_params)
            return result
            
        except Exception as e:
            return {
                "error": str(e),
                "exception_type": e.__class__.__name__,
                "tool": tool_name,
                "params": params
            }
    
    def _load_adapter_class(self, adapter_name: str) -> Optional[Type]:
        """Dynamically load an adapter class by name.
        
        Args:
            adapter_name: The name of the adapter to load
            
        Returns:
            The adapter class if found, None otherwise
        """
        # First, get the adapter info from the database
        with self.memory_db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT class_name FROM adapters WHERE name = ?", 
                (adapter_name,)
            )
            result = cursor.fetchone()
            
            if not result:
                print(f"No adapter found in database with name: {adapter_name}")
                return None
                
            class_name = result[0]
        
        # Try different possible module paths
        path = f"omni_chat.adapters.{adapter_name}_adapter"              
        
        try:
            module = importlib.import_module(path)
            
            # Get the class using the name from the database
            adapter_class = getattr(module, class_name, None)
            
            if adapter_class:
                return adapter_class
            else:
                print(f"Class {class_name} not found in module {path}")
                
        except ImportError as e:
            print(f"Failed to import {path}: {str(e)}")
            
        print(f"Could not find adapter class {class_name} for adapter: {adapter_name}")
        return None
