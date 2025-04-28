# src/unit_test_generator/infrastructure/adapters/llm/mcp_client_adapter.py
"""
Adapter for Model Context Protocol (MCP) servers.
"""
import os
import json
import logging
import requests
from typing import Dict, Any, List, Optional

from unit_test_generator.domain.ports.llm_service import LLMServicePort

logger = logging.getLogger(__name__)


class MCPTool:
    """
    Representation of a tool for MCP.
    """
    
    def __init__(self, name: str, description: str, parameters_schema: Dict[str, Any]):
        """
        Initialize the MCP tool.
        
        Args:
            name: The name of the tool
            description: A description of what the tool does
            parameters_schema: JSON schema for the tool parameters
        """
        self.name = name
        self.description = description
        self.parameters_schema = parameters_schema
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to MCP tool format.
        
        Returns:
            Dictionary representation of the tool
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema
        }


class MCPRequestBuilder:
    """
    Builder for MCP requests.
    """
    
    def __init__(self, model: str, tools: Optional[List[MCPTool]] = None):
        """
        Initialize the MCP request builder.
        
        Args:
            model: The model to use
            tools: Optional list of tools
        """
        self.model = model
        self.tools = tools or []
        self.messages = []
    
    def add_system_message(self, content: str) -> 'MCPRequestBuilder':
        """
        Add a system message.
        
        Args:
            content: The message content
            
        Returns:
            Self for chaining
        """
        self.messages.append({
            "role": "system",
            "content": content
        })
        return self
    
    def add_user_message(self, content: str) -> 'MCPRequestBuilder':
        """
        Add a user message.
        
        Args:
            content: The message content
            
        Returns:
            Self for chaining
        """
        self.messages.append({
            "role": "user",
            "content": content
        })
        return self
    
    def add_assistant_message(self, content: str) -> 'MCPRequestBuilder':
        """
        Add an assistant message.
        
        Args:
            content: The message content
            
        Returns:
            Self for chaining
        """
        self.messages.append({
            "role": "assistant",
            "content": content
        })
        return self
    
    def build(self) -> Dict[str, Any]:
        """
        Build the MCP request.
        
        Returns:
            The MCP request dictionary
        """
        request = {
            "model": self.model,
            "messages": self.messages
        }
        
        if self.tools:
            request["tools"] = [tool.to_dict() for tool in self.tools]
        
        return request


class MCPClientAdapter(LLMServicePort):
    """
    Adapter for MCP servers implementing the LLMServicePort interface.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the MCP client adapter.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.server_url = config.get("mcp", {}).get("server_url")
        self.api_key = config.get("mcp", {}).get("api_key") or os.environ.get("MCP_API_KEY")
        self.model = config.get("mcp", {}).get("model", "default")
        self.timeout = config.get("mcp", {}).get("timeout", 60)
        
        if not self.server_url:
            raise ValueError("MCP server URL not configured")
        
        logger.info(f"Initialized MCP client adapter with server URL: {self.server_url}")
    
    def generate_tests(self, context_payload: Dict[str, Any]) -> str:
        """
        Generate tests using the MCP server.
        
        Args:
            context_payload: Context for test generation
            
        Returns:
            Generated test code
        """
        logger.info("Generating tests using MCP server")
        
        # Convert context payload to MCP format
        mcp_request = self._convert_to_mcp_request(context_payload, "generate_test")
        
        # Send request to MCP server
        response = self._send_request(mcp_request)
        
        # Extract test code from response
        test_code = self._extract_code_from_response(response)
        
        return test_code
    
    def generate_fix(self, context_payload: Dict[str, Any]) -> str:
        """
        Generate a fix using the MCP server.
        
        Args:
            context_payload: Context for fix generation
            
        Returns:
            Generated fix code
        """
        logger.info("Generating fix using MCP server")
        
        # Convert context payload to MCP format
        mcp_request = self._convert_to_mcp_request(context_payload, "generate_fix")
        
        # Send request to MCP server
        response = self._send_request(mcp_request)
        
        # Extract fixed code from response
        fixed_code = self._extract_code_from_response(response)
        
        return fixed_code
    
    def _convert_to_mcp_request(self, context_payload: Dict[str, Any], task_type: str) -> Dict[str, Any]:
        """
        Convert a context payload to an MCP request.
        
        Args:
            context_payload: The context payload
            task_type: The type of task ("generate_test" or "generate_fix")
            
        Returns:
            MCP request dictionary
        """
        builder = MCPRequestBuilder(self.model)
        
        if task_type == "generate_test":
            # Add system message with instructions
            builder.add_system_message(self._get_test_generation_system_prompt())
            
            # Add user message with context
            user_message = self._format_test_generation_user_message(context_payload)
            builder.add_user_message(user_message)
        elif task_type == "generate_fix":
            # Add system message with instructions
            builder.add_system_message(self._get_fix_generation_system_prompt())
            
            # Add user message with context
            user_message = self._format_fix_generation_user_message(context_payload)
            builder.add_user_message(user_message)
        
        return builder.build()
    
    def _get_test_generation_system_prompt(self) -> str:
        """
        Get the system prompt for test generation.
        
        Returns:
            System prompt
        """
        target_language = self.config.get("generation", {}).get("target_language", "Kotlin")
        target_framework = self.config.get("generation", {}).get("target_framework", "JUnit5 with MockK")
        
        return f"""
        You are an expert test writer for {target_language} using {target_framework}.
        Your task is to generate high-quality unit tests for the provided source code.
        
        Follow these guidelines:
        1. Write comprehensive tests that cover all important functionality
        2. Follow best practices for {target_framework}
        3. Use appropriate mocking and assertions
        4. Structure the tests clearly and logically
        5. Include helpful comments explaining the test strategy
        
        Return ONLY the test code without any additional explanation.
        """
    
    def _get_fix_generation_system_prompt(self) -> str:
        """
        Get the system prompt for fix generation.
        
        Returns:
            System prompt
        """
        return """
        You are an expert at fixing compilation errors in unit tests.
        Your task is to fix the provided test code based on the error messages.
        
        Follow these guidelines:
        1. Analyze the error messages carefully
        2. Make minimal changes to fix the issues
        3. Preserve the original test intent
        4. Fix import statements if needed
        5. Ensure the test will compile and run correctly
        
        Return ONLY the fixed test code without any additional explanation.
        """
    
    def _format_test_generation_user_message(self, context_payload: Dict[str, Any]) -> str:
        """
        Format the user message for test generation.
        
        Args:
            context_payload: The context payload
            
        Returns:
            Formatted user message
        """
        source_content = context_payload.get("source_content", "")
        similar_examples = context_payload.get("similar_examples", [])
        
        message = f"# Source Code\n\n```kotlin\n{source_content}\n```\n\n"
        
        if similar_examples:
            message += "# Similar Examples\n\n"
            for i, example in enumerate(similar_examples):
                example_content = example.get("content", "")
                message += f"## Example {i+1}\n\n```kotlin\n{example_content}\n```\n\n"
        
        message += "Please generate a comprehensive unit test for this source code."
        
        return message
    
    def _format_fix_generation_user_message(self, context_payload: Dict[str, Any]) -> str:
        """
        Format the user message for fix generation.
        
        Args:
            context_payload: The context payload
            
        Returns:
            Formatted user message
        """
        test_code = context_payload.get("test_code", "")
        error_output = context_payload.get("error_output", "")
        source_content = context_payload.get("source_content", "")
        
        message = f"# Test Code with Errors\n\n```kotlin\n{test_code}\n```\n\n"
        message += f"# Error Output\n\n```\n{error_output}\n```\n\n"
        
        if source_content:
            message += f"# Source Code\n\n```kotlin\n{source_content}\n```\n\n"
        
        message += "Please fix the test code to resolve the compilation errors."
        
        return message
    
    def _send_request(self, mcp_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a request to the MCP server.
        
        Args:
            mcp_request: The MCP request
            
        Returns:
            MCP response
            
        Raises:
            RuntimeError: If the request fails
        """
        headers = {
            "Content-Type": "application/json"
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            response = requests.post(
                f"{self.server_url}/v1/chat/completions",
                headers=headers,
                json=mcp_request,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error sending request to MCP server: {e}")
            raise RuntimeError(f"Failed to communicate with MCP server: {e}")
    
    def _extract_code_from_response(self, response: Dict[str, Any]) -> str:
        """
        Extract code from an MCP response.
        
        Args:
            response: The MCP response
            
        Returns:
            Extracted code
        """
        try:
            # Extract the assistant's message
            choices = response.get("choices", [])
            if not choices:
                logger.warning("No choices in MCP response")
                return ""
            
            message = choices[0].get("message", {})
            content = message.get("content", "")
            
            # Extract code blocks
            import re
            code_blocks = re.findall(r"```(?:kotlin)?\n(.*?)```", content, re.DOTALL)
            
            if code_blocks:
                # Return the first code block
                return code_blocks[0].strip()
            else:
                # If no code blocks, return the entire content
                return content.strip()
        except Exception as e:
            logger.error(f"Error extracting code from MCP response: {e}")
            return ""
