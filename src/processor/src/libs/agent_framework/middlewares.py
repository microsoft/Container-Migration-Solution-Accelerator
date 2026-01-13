import time
from collections.abc import Awaitable, Callable

from agent_framework import (
    AgentMiddleware,
    AgentRunContext,
    ChatContext,
    ChatMessage,
    ChatMiddleware,
    FunctionInvocationContext,
    FunctionMiddleware,
    Role,
)


class DebuggingMiddleware(AgentMiddleware):
    """Class-based middleware that adds debugging information to chat responses."""

    async def process(
        self,
        context: AgentRunContext,
        next: Callable[[AgentRunContext], Awaitable[None]],
    ) -> None:
        """Run-level debugging middleware for troubleshooting specific runs."""
        print("[Debug] Debug mode enabled for this run")
        print(f"[Debug] Messages count: {len(context.messages)}")
        print(f"[Debug] Is streaming: {context.is_streaming}")

        # Log existing metadata from agent middleware
        if context.metadata:
            print(f"[Debug] Existing metadata: {context.metadata}")

        context.metadata["debug_enabled"] = True

        await next(context)

        print("[Debug] Debug information collected")


class LoggingFunctionMiddleware(FunctionMiddleware):
    """Function middleware that logs function calls."""

    async def process(
        self,
        context: FunctionInvocationContext,
        next: Callable[[FunctionInvocationContext], Awaitable[None]],
    ) -> None:
        function_name = context.function.name

        # Collect arguments for display
        args_info = []
        if context.arguments:
            for key, value in context.arguments.model_dump().items():
                args_info.append(f"{key}: {value}")

        start_time = time.time()
        await next(context)
        end_time = time.time()
        duration = end_time - start_time

        # Build comprehensive log output
        print("\n" + "=" * 80)
        print("[LoggingFunctionMiddleware] Function Call")
        print("=" * 80)
        print(f"Function Name: {function_name}")
        print(f"Execution Time: {duration:.5f}s")

        # Display arguments
        if args_info:
            print("\nArguments:")
            for arg in args_info:
                print(f"  - {arg}")
        else:
            print("\nArguments: None")

        # Display output results
        if context.result:
            print("\nOutput Results:")

            # Ensure context.result is treated as a list
            results = (
                context.result if isinstance(context.result, list) else [context.result]
            )

            for idx, result in enumerate(results):
                print(f"  Result #{idx + 1}:")

                # Use raw_representation to get the actual output
                if hasattr(result, "raw_representation"):
                    raw_output = result.raw_representation
                    raw_type = type(raw_output).__name__
                    print(f"    Type: {raw_type}")

                    # Limit output length for very large content
                    output_str = str(raw_output)
                    if len(output_str) > 1000:
                        print(f"    Output (truncated): {output_str[:1000]}...")
                    else:
                        print(f"    Output: {output_str}")
                # result is just string or primitive
                else:
                    output_str = str(result)
                    if len(output_str) > 1000:
                        print(f"    Output (truncated): {output_str[:1000]}...")
                    else:
                        print(f"    Output: {output_str}")

                # Check if result has error flag
                if hasattr(result, "is_error"):
                    print(f"    Is Error: {result.is_error}")
        else:
            print("\nOutput Results: None")

        print("=" * 80 + "\n")


class InputObserverMiddleware(ChatMiddleware):
    """Class-based middleware that observes and modifies input messages."""

    def __init__(self, replacement: str | None = None):
        """Initialize with a replacement for user messages."""
        self.replacement = replacement

    async def process(
        self,
        context: ChatContext,
        next: Callable[[ChatContext], Awaitable[None]],
    ) -> None:
        """Observe and modify input messages before they are sent to AI."""
        print("[InputObserverMiddleware] Observing input messages:")

        for i, message in enumerate(context.messages):
            content = message.text if message.text else str(message.contents)
            print(f"  Message {i + 1} ({message.role.value}): {content}")

        print(f"[InputObserverMiddleware] Total messages: {len(context.messages)}")

        # Modify user messages by creating new messages with enhanced text
        modified_messages: list[ChatMessage] = []
        modified_count = 0

        for message in context.messages:
            if message.role == Role.USER and message.text:
                original_text = message.text
                updated_text = original_text

                if self.replacement:
                    updated_text = self.replacement
                    print(
                        f"[InputObserverMiddleware] Updated: '{original_text}' -> '{updated_text}'"
                    )

                modified_message = ChatMessage(role=message.role, text=updated_text)
                modified_messages.append(modified_message)
                modified_count += 1
            else:
                modified_messages.append(message)

        # Replace messages in context
        context.messages[:] = modified_messages

        # Continue to next middleware or AI execution
        await next(context)

        # Observe that processing is complete
        print("[InputObserverMiddleware] Processing completed")
