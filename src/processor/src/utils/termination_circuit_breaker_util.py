"""
Termination Circuit Breaker Utility

This module provides circuit breaker functionality for agent termination strategies.
It helps prevent infinite loops, repetitive conversations, and stuck agent interactions
by monitoring conversation patterns and terminating when problematic patterns are detected.

Features:
- Repetitive message detection using similarity analysis
- Progress monitoring to detect stuck conversations
- Echo pattern detection for agent loops
- Configurable thresholds and parameters
- Comprehensive status reporting and logging

Usage:
    from utils.termination_circuit_breaker_util import CircuitBreakerManager

    # Create circuit breaker
    circuit_breaker = CircuitBreakerManager()

    # Configure parameters
    circuit_breaker.configure(
        enabled=True,
        max_similar_messages=3,
        max_no_progress_iterations=15,
        similarity_threshold=0.75
    )

    # Check if circuit should break
    should_break, reason = await circuit_breaker.should_break(history, current_content)
"""

from semantic_kernel.contents import ChatMessageContent

from utils.console_util import ConsoleColors


class CircuitBreakerConfig:
    """Configuration class for circuit breaker parameters."""

    def __init__(
        self,
        enabled: bool = True,
        max_similar_messages: int = 3,
        max_no_progress_iterations: int = 10,
        similarity_threshold: float = 0.8,
        progress_indicators: list[str] | None = None,
    ):
        self.enabled = enabled
        self.max_similar_messages = max_similar_messages
        self.max_no_progress_iterations = max_no_progress_iterations
        self.similarity_threshold = similarity_threshold
        self.progress_indicators = progress_indicators or [
            "PHASE",
            "COMPLETED",
            "APPROVED",
            "REJECTED",
            "ANALYSIS",
            "VALIDATED",
            "CHECKPOINT",
            "file_operation_service",
            "datetime_service",
            "creating",
            "saved",
            "generated",
            "workspace",
            "converted",
        ]


class CircuitBreakerState:
    """State management for circuit breaker."""

    def __init__(self):
        self.broken = False
        self.message_history: list[str] = []
        self.no_progress_count = 0
        self.last_meaningful_message_index = -1

    def reset(self):
        """Reset all state variables."""
        self.broken = False
        self.message_history = []
        self.no_progress_count = 0
        self.last_meaningful_message_index = -1


class CircuitBreakerManager:
    """
    Main circuit breaker manager that handles all circuit breaker logic.

    This class encapsulates all circuit breaker functionality including:
    - Configuration management
    - State tracking
    - Pattern detection algorithms
    - Status reporting
    """

    def __init__(self, config: CircuitBreakerConfig | None = None):
        """Initialize circuit breaker with optional configuration."""
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState()

    def configure(
        self,
        enabled: bool = True,
        max_similar_messages: int = 3,
        max_no_progress_iterations: int = 10,
        similarity_threshold: float = 0.8,
        progress_indicators: list[str] | None = None,
    ):
        """Configure circuit breaker parameters."""
        self.config = CircuitBreakerConfig(
            enabled=enabled,
            max_similar_messages=max_similar_messages,
            max_no_progress_iterations=max_no_progress_iterations,
            similarity_threshold=similarity_threshold,
            progress_indicators=progress_indicators,
        )

        print(f"{ConsoleColors.CYAN} Circuit breaker configured:{ConsoleColors.RESET}")
        print(f"   Enabled: {enabled}")
        print(f"   Max similar messages: {max_similar_messages}")
        print(f"   Max no-progress iterations: {max_no_progress_iterations}")
        print(f"   Similarity threshold: {similarity_threshold}")

    async def should_break(
        self, history: list[ChatMessageContent], current_content: str
    ) -> tuple[bool, str | None]:
        """
        Check if circuit breaker should be triggered.

        Args:
            history: The conversation history
            current_content: The current message content

        Returns:
            Tuple of (should_break: bool, reason: Optional[str])
        """
        if not self.config.enabled:
            return False, None

        if self.state.broken:
            return True, "Circuit breaker already activated"

        # Check 1: Too many similar consecutive messages
        similar_count = await self._count_similar_recent_messages(current_content)
        if similar_count >= self.config.max_similar_messages:
            reason = f"Too many similar messages detected ({similar_count} consecutive similar messages)"
            self.state.broken = True
            return True, reason

        # Check 2: No meaningful progress detection
        if await self._is_meaningful_progress(current_content, history):
            self.state.no_progress_count = 0
            self.state.last_meaningful_message_index = len(history) - 1
        else:
            self.state.no_progress_count += 1

        if self.state.no_progress_count >= self.config.max_no_progress_iterations:
            reason = (
                f"No meaningful progress for {self.state.no_progress_count} iterations"
            )
            self.state.broken = True
            return True, reason

        # Check 3: Detect infinite loops or echoing patterns
        if await self._detect_echo_pattern(history):
            reason = "Echo pattern or infinite loop detected"
            self.state.broken = True
            return True, reason

        return False, None

    async def _count_similar_recent_messages(self, current_content: str) -> int:
        """Count how many recent messages are similar to the current one."""
        if not self.state.message_history:
            self.state.message_history = [current_content]
            return 1

        similar_count = 1  # Current message
        current_words = set(current_content.lower().split())

        # Check last few messages for similarity
        for recent_msg in reversed(
            self.state.message_history[-self.config.max_similar_messages :]
        ):
            recent_words = set(recent_msg.lower().split())

            if not current_words or not recent_words:
                continue

            # Calculate Jaccard similarity
            intersection = len(current_words.intersection(recent_words))
            union = len(current_words.union(recent_words))
            similarity = intersection / union if union > 0 else 0

            if similarity >= self.config.similarity_threshold:
                similar_count += 1
            else:
                break  # Stop at first non-similar message

        # Update message history (keep only recent messages)
        self.state.message_history.append(current_content)
        if len(self.state.message_history) > self.config.max_similar_messages * 2:
            self.state.message_history = self.state.message_history[
                -self.config.max_similar_messages :
            ]

        return similar_count

    async def _is_meaningful_progress(
        self, current_content: str, history: list[ChatMessageContent]
    ) -> bool:
        """Determine if the current message represents meaningful progress."""
        content_upper = current_content.upper()

        # Check for progress indicators
        if any(
            indicator in content_upper for indicator in self.config.progress_indicators
        ):
            return True

        # Check for new file operations or tool usage
        if "tool" in current_content.lower() or "service" in current_content.lower():
            return True

        # Check for substantive content (not just acknowledgments)
        substantive_words = len(
            [word for word in current_content.split() if len(word) > 3]
        )
        if substantive_words < 5:  # Very short messages likely not meaningful
            return False

        return len(current_content) > 100  # Assume longer messages are more meaningful

    async def _detect_echo_pattern(self, history: list[ChatMessageContent]) -> bool:
        """Detect if agents are just echoing each other without progress."""
        if len(history) < 6:  # Need at least 6 messages to detect pattern
            return False

        # Check last 6 messages for A-B-A-B pattern
        recent_messages = history[-6:]

        # Group by agent
        agent_messages = {}
        for msg in recent_messages:
            agent_name = getattr(msg, "name", "unknown")
            if agent_name not in agent_messages:
                agent_messages[agent_name] = []
            agent_messages[agent_name].append(msg.content)

        # If only 2 agents are talking and repeating similar content
        if len(agent_messages) == 2:
            agents = list(agent_messages.keys())
            agent1_msgs = agent_messages[agents[0]]
            agent2_msgs = agent_messages[agents[1]]

            # Check if they're alternating with similar content
            if len(agent1_msgs) >= 2 and len(agent2_msgs) >= 2:
                # Simple similarity check for echo detection
                for i in range(min(2, len(agent1_msgs) - 1)):
                    msg1_words = set(agent1_msgs[i].lower().split())
                    msg2_words = set(agent1_msgs[i + 1].lower().split())

                    if msg1_words and msg2_words:
                        intersection = len(msg1_words.intersection(msg2_words))
                        union = len(msg1_words.union(msg2_words))
                        similarity = intersection / union if union > 0 else 0

                        if similarity >= 0.7:  # High similarity suggests echoing
                            return True

        return False

    def reset(self):
        """Reset the circuit breaker state."""
        self.state.reset()
        print(f"{ConsoleColors.GREEN}[PROCESSING] Circuit breaker reset{ConsoleColors.RESET}")

    def get_status(self) -> dict:
        """Get current circuit breaker status and statistics."""
        return {
            "enabled": self.config.enabled,
            "broken": self.state.broken,
            "no_progress_count": self.state.no_progress_count,
            "recent_message_count": len(self.state.message_history),
            "max_similar_messages": self.config.max_similar_messages,
            "max_no_progress_iterations": self.config.max_no_progress_iterations,
            "similarity_threshold": self.config.similarity_threshold,
        }

    def print_status(self):
        """Print a formatted status of the circuit breaker."""
        status = self.get_status()

        print(f"\n{ConsoleColors.CYAN} Circuit Breaker Status:{ConsoleColors.RESET}")
        print(
            f"   Status: {'[RED_CIRCLE] BROKEN' if status['broken'] else '🟢 ACTIVE' if status['enabled'] else '[WHITE_CIRCLE] DISABLED'}"
        )
        print(
            f"   No-progress count: {status['no_progress_count']}/{status['max_no_progress_iterations']}"
        )
        print(f"   Recent messages tracked: {status['recent_message_count']}")
        print(f"   Similarity threshold: {status['similarity_threshold'] * 100:.0f}%")
        print(f"   Max similar messages: {status['max_similar_messages']}")

    @property
    def is_broken(self) -> bool:
        """Check if circuit breaker is currently broken."""
        return self.state.broken

    @property
    def is_enabled(self) -> bool:
        """Check if circuit breaker is enabled."""
        return self.config.enabled


# Helper function for easy integration
async def check_circuit_breaker(
    history: list[ChatMessageContent],
    current_content: str,
    circuit_breaker: CircuitBreakerManager | None = None,
    **kwargs,
) -> tuple[bool, str | None]:
    """
    Convenient function to check circuit breaker without needing to manage instance.

    Args:
        history: Conversation history
        current_content: Current message content
        circuit_breaker: Optional existing circuit breaker instance
        **kwargs: Configuration parameters if creating new instance

    Returns:
        Tuple of (should_break: bool, reason: Optional[str])
    """
    if circuit_breaker is None:
        circuit_breaker = CircuitBreakerManager()
        if kwargs:
            circuit_breaker.configure(**kwargs)

    return await circuit_breaker.should_break(history, current_content)
