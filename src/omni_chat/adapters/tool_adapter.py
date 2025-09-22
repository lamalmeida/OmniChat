class ToolAdapter:
    """Base class for external tools (Calendar, Gmail, Drive, etc.)."""

    def __init__(self, name: str, description: str, tools: list = None, **kwargs):
        """Initialize the ToolAdapter.
        
        Args:
            name: Unique name for the adapter
            description: Description of what the adapter does
            tools: List of tools provided by this adapter
            **kwargs: Additional keyword arguments for backward compatibility
        """
        self.name = name
        self.description = description
        self.tools = tools or []
        
        # For backward compatibility
        if 'example' in kwargs:
            self.example = kwargs['example']
        if 'side_effects' in kwargs:
            self.side_effects = kwargs['side_effects']

    def register(self, db) -> dict:
        """Register the adapter and its tools in the database.
        
        Args:
            db: Database connection object
            
        Returns:
            dict: Dictionary containing adapter_id and tool_ids
        """
        # First register the adapter
        adapter_id = db.register_adapter(
            name=self.name,
            class_name=self.__class__.__name__,
            description=self.description
        )
        
        # Then register all tools provided by this adapter
        tool_ids = {}
        for tool in self.tools:
            tool_id = db.register_tool(
                adapter_id=adapter_id,
                name=tool['name'],
                full_name=f"{self.name}.{tool['name']}",
                short_desc=tool.get('description', ''),
                example=str(tool.get('example', '')),
                side_effects=tool.get('side_effects', False)
            )
            tool_ids[tool['name']] = tool_id
        
        return {
            'adapter_id': adapter_id,
            'tool_ids': tool_ids
        }