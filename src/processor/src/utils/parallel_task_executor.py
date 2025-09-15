import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class TaskResult:
    name: str
    status: TaskStatus
    result: Any = None
    error: Exception | None = None
    attempts: int = 0
    execution_time: float = 0.0


@dataclass
class TaskConfig:
    name: str
    coro_func: Callable[..., Awaitable[Any]]  # The async function to call
    kwargs: dict  # All parameters for the function
    max_retries: int = 2
    retry_delay_base: float = 1.0
    timeout: float | None = None


class ParallelTaskExecutor:
    def __init__(
        self,
        default_max_retries: int = 2,
        default_retry_delay: float = 1.0,
        max_concurrent_tasks: int | None = None,
    ):
        self.tasks: dict[str, TaskConfig] = {}
        self.default_max_retries = default_max_retries
        self.default_retry_delay = default_retry_delay
        self.max_concurrent_tasks = max_concurrent_tasks
        self.results: dict[str, TaskResult] = {}

    def add_task(
        self,
        name: str,
        coro_func: Callable[..., Awaitable[Any]],
        max_retries: int | None = None,
        retry_delay: float | None = None,
        timeout: float | None = None,
        **kwargs,
    ) -> "ParallelTaskExecutor":
        """Add a task to be executed in parallel

        Args:
            name: Unique name for the task
            coro_func: The async function to call (e.g., agent.execute_thread)
            max_retries: Override default retry count for this task
            retry_delay: Override default retry delay for this task
            timeout: Optional timeout for this task
            **kwargs: All parameters to pass to the coro_func
        """
        task_config = TaskConfig(
            name=name,
            coro_func=coro_func,
            kwargs=kwargs,
            max_retries=max_retries or self.default_max_retries,
            retry_delay_base=retry_delay or self.default_retry_delay,
            timeout=timeout,
        )
        self.tasks[name] = task_config
        return self  # For method chaining

    async def execute_all(
        self,
        stop_on_first_failure: bool = False,
        progress_callback: Callable | None = None,
    ) -> dict[str, TaskResult]:
        """Execute all tasks in parallel with retry logic"""
        if not self.tasks:
            return {}

        print(f"[START] Starting parallel execution of {len(self.tasks)} tasks...")

        # Initialize results
        self.results = {
            name: TaskResult(name=name, status=TaskStatus.PENDING)
            for name in self.tasks
        }

        # Create semaphore for concurrency control if specified
        semaphore = (
            asyncio.Semaphore(self.max_concurrent_tasks)
            if self.max_concurrent_tasks
            else None
        )

        # Create tasks for parallel execution
        async_tasks = []
        for task_name, task_config in self.tasks.items():
            async_task = asyncio.create_task(
                self._execute_single_task_with_retry(
                    task_config, semaphore, progress_callback
                ),
                name=task_name,
            )
            async_tasks.append(async_task)

        # Execute all tasks
        if stop_on_first_failure:
            done, pending = await asyncio.wait(
                async_tasks, return_when=asyncio.FIRST_EXCEPTION
            )
            for task in pending:
                task.cancel()
        else:
            await asyncio.gather(*async_tasks, return_exceptions=True)

        # Report final status
        successful_tasks = [
            name
            for name, result in self.results.items()
            if result.status == TaskStatus.SUCCESS
        ]
        failed_tasks = [
            name
            for name, result in self.results.items()
            if result.status == TaskStatus.FAILED
        ]

        print("[SUCCESS] Parallel execution completed:")
        print(f"   Success: {len(successful_tasks)}/{len(self.tasks)} tasks")
        if failed_tasks:
            print(f"   Failed: {failed_tasks}")

        return self.results

    async def _execute_single_task_with_retry(
        self,
        task_config: TaskConfig,
        semaphore: asyncio.Semaphore | None,
        progress_callback: Callable | None,
    ) -> TaskResult:
        """Execute a single task with retry logic"""
        result = self.results[task_config.name]

        for attempt in range(task_config.max_retries + 1):
            try:
                result.attempts = attempt + 1
                result.status = (
                    TaskStatus.RETRYING if attempt > 0 else TaskStatus.RUNNING
                )

                if progress_callback:
                    await progress_callback(task_config.name, result.status, attempt)

                print(
                    f"[PROCESSING] Executing {task_config.name} (attempt {attempt + 1}/{task_config.max_retries + 1})"
                )

                # Use semaphore for concurrency control if provided
                if semaphore:
                    async with semaphore:
                        task_result = await self._run_task_with_timeout(task_config)
                else:
                    task_result = await self._run_task_with_timeout(task_config)

                result.result = task_result
                result.status = TaskStatus.SUCCESS
                result.error = None

                print(f"[SUCCESS] {task_config.name} completed successfully")
                return result

            except TimeoutError:
                error = Exception(f"Task {task_config.name} timed out")
                print(f"[TIMEOUT] {task_config.name} timed out on attempt {attempt + 1}")
                result.error = error

            except Exception as e:
                print(f"[FAILED] {task_config.name} failed on attempt {attempt + 1}: {e}")
                result.error = e

                # If this isn't the last attempt, wait before retrying
                if attempt < task_config.max_retries:
                    delay = task_config.retry_delay_base * (2**attempt)
                    print(f"⏳ Waiting {delay}s before retry...")
                    await asyncio.sleep(delay)

        # All retries exhausted
        result.status = TaskStatus.FAILED
        print(
            f"[EXPLOSION] {task_config.name} failed after {task_config.max_retries + 1} attempts"
        )
        return result

    async def _run_task_with_timeout(self, task_config: TaskConfig) -> Any:
        """Run a task with optional timeout"""
        if task_config.timeout:
            return await asyncio.wait_for(
                task_config.coro_func(**task_config.kwargs), timeout=task_config.timeout
            )
        else:
            return await task_config.coro_func(**task_config.kwargs)

    def get_successful_results(self) -> dict[str, Any]:
        """Get only successful results"""
        return {
            name: result.result
            for name, result in self.results.items()
            if result.status == TaskStatus.SUCCESS
        }

    def get_failed_tasks(self) -> dict[str, Exception]:
        """Get failed tasks and their errors"""
        return {
            name: result.error
            for name, result in self.results.items()
            if result.status == TaskStatus.FAILED
        }

    def clear_tasks(self):
        """Clear all tasks and results"""
        self.tasks.clear()
        self.results.clear()
