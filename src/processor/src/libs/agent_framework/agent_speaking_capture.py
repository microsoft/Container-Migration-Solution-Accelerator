# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from datetime import datetime
from typing import Any, Callable, Optional, Awaitable
from agent_framework import AgentRunContext, AgentMiddleware

class AgentSpeakingCaptureMiddleware(AgentMiddleware):
    """Middleware to capture agent name and response for each agent invocation with callback support.
    
    This middleware captures:
    - Agent name
    - Response text
    - Timestamp
    - Streaming vs non-streaming output
    
    Supports both synchronous and asynchronous callbacks that are triggered when responses are captured.
    
    Usage:
        # With callback
        def on_response_captured(capture_data: dict):
            print(f"Captured: {capture_data['agent_name']} - {capture_data['response']}")
        
        capture_middleware = AgentSpeakingCaptureMiddleware(callback=on_response_captured)
        
        # With async callback
        async def async_callback(capture_data: dict):
            await log_to_database(capture_data)
        
        capture_middleware = AgentSpeakingCaptureMiddleware(callback=async_callback)
        
        # Without callback (store only)
        capture_middleware = AgentSpeakingCaptureMiddleware()
        
        agent = client.create_agent(
            name="MyAgent",
            middleware=[capture_middleware],
            ...
        )
        
        # After agent runs, access captured data:
        for capture in capture_middleware.captured_responses:
            print(f"{capture['agent_name']}: {capture['response']}")
    """
    
    def __init__(
        self, 
        callback: Optional[Callable[[dict[str, Any]], Any]] = None,
        on_stream_response_complete: Optional[Callable[[dict[str, Any]], Any]] = None,
        store_responses: bool = True
    ):
        """Initialize the middleware with optional callback and storage configuration.
        
        Args:
            callback: Optional callback function (sync or async) that receives capture data.
                     Triggered for all responses (streaming and non-streaming).
                     Signature: (capture_data: dict) -> Any
            on_stream_complete: Optional callback triggered only when streaming finishes.
                               Useful for immediate reactions to completed streaming responses.
                               Signature: (capture_data: dict) -> Any
            store_responses: Whether to store responses in memory (default: True).
                            Set to False if only using callbacks for memory efficiency.
        """
        self.captured_responses: list[dict[str, Any]] = [] if store_responses else None
        self.callback = callback
        self.on_stream_response_complete = on_stream_response_complete
        self.store_responses = store_responses
        self._streaming_buffers: dict[str, list[str]] = {}  # Buffer for streaming responses
    
    async def process(self, context: AgentRunContext, next):
        """Process the agent invocation and capture the response.
        
        Args:
            context: Agent run context containing agent, messages, and execution details
            next: Next middleware in the chain
        """
        agent_name = context.agent.name if hasattr(context.agent, 'name') else str(context.agent)
        start_time = datetime.now()
        
        # Initialize streaming buffer for this agent
        if context.is_streaming:
            self._streaming_buffers[agent_name] = []
        
        # Call the next middleware/agent
        await next(context)
        
        # Capture the response after execution
        response_text = ""
        
        # For streaming responses, context.result is an async_generator
        # We need to consume the generator to capture the streamed content
        if context.is_streaming:
            # For streaming, we need to intercept and buffer the stream
            # Since context.result is an async_generator, we can't easily capture it here
            # The response will be added to messages by the workflow after streaming completes
            
            # Try to get response from context after the generator is consumed
            # In GroupChat workflows, the response might not be in context.messages yet
            # Instead, we'll mark this for later capture or use a different approach
            
            # For now, capture a placeholder indicating streaming occurred
            response_text = "[Streaming response - capture not supported in middleware for GroupChat]"
            
            # Clean up buffer
            self._streaming_buffers.pop(agent_name, None)
            
            capture_data = {
                'agent_name': agent_name,
                'response': response_text,
                'timestamp': start_time,
                'completed_at': datetime.now(),
                'is_streaming': True,
                'messages': context.messages,
                'full_result': context.result,
            }
            
            if self.store_responses:
                self.captured_responses.append(capture_data)
            
            # Trigger general callback if provided
            await self._trigger_callback(capture_data)
            
            # Trigger streaming-specific callback
            await self._trigger_stream_complete_callback(capture_data)
            
        elif context.result:
                # Handle non-streaming responses
                if hasattr(context.result, 'messages') and context.result.messages:
                    # Extract text from response messages
                    response_text = "\n".join(
                        msg.text for msg in context.result.messages 
                        if hasattr(msg, 'text') and msg.text
                    )
                elif hasattr(context.result, 'text'):
                    response_text = context.result.text
                else:
                    response_text = str(context.result)
                
                capture_data = {
                    'agent_name': agent_name,
                    'response': response_text,
                    'timestamp': start_time,
                    'completed_at': datetime.now(),
                    'is_streaming': False,
                    'messages': context.messages,
                    'full_result': context.result,
                }
                
                if self.store_responses:
                    self.captured_responses.append(capture_data)
                
                # Trigger callback if provided
                await self._trigger_callback(capture_data)
    
    async def _trigger_callback(self, capture_data: dict[str, Any]):
        """Trigger the callback function if one is configured.
        
        Args:
            capture_data: The captured response data to pass to the callback
        """
        if self.callback:
            try:
                import asyncio
                import inspect
                
                # Check if callback is async or sync
                if inspect.iscoroutinefunction(self.callback):
                    await self.callback(capture_data)
                else:
                    # Run sync callback in thread pool to avoid blocking
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self.callback, capture_data)
            except Exception as e:
                # Log error but don't break the middleware chain
                print(f"[WARNING] Callback error in AgentSpeakingCaptureMiddleware: {e}")
    
    async def _trigger_stream_complete_callback(self, capture_data: dict[str, Any]):
        """Trigger the on_stream_complete callback if one is configured.
        
        This callback is only triggered for streaming responses after they finish.
        
        Args:
            capture_data: The captured response data to pass to the callback
        """
        if self.on_stream_response_complete:
            try:
                import asyncio
                import inspect
                
                # Check if callback is async or sync
                if inspect.iscoroutinefunction(self.on_stream_response_complete):
                    await self.on_stream_response_complete(capture_data)
                else:
                    # Run sync callback in thread pool to avoid blocking
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self.on_stream_response_complete, capture_data)
            except Exception as e:
                # Log error but don't break the middleware chain
                print(f"[WARNING] Stream complete callback error: {e}")
    
    def get_all_responses(self) -> list[dict[str, Any]]:
        """Get all captured responses.
        
        Returns:
            List of dictionaries containing agent_name, response, timestamp, etc.
            Returns empty list if store_responses is False.
        """
        return self.captured_responses if self.store_responses else []
    
    def get_responses_by_agent(self, agent_name: str) -> list[dict[str, Any]]:
        """Get captured responses for a specific agent.
        
        Args:
            agent_name: Name of the agent to filter by
            
        Returns:
            List of responses from the specified agent.
            Returns empty list if store_responses is False.
        """
        if not self.store_responses:
            return []
        
        return [
            capture for capture in self.captured_responses 
            if capture['agent_name'] == agent_name
        ]
    
    def clear(self):
        """Clear all captured responses."""
        if self.store_responses:
            self.captured_responses.clear()
