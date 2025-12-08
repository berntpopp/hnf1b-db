"""Exponential backoff retry utilities.

Implements retry logic with exponential backoff and jitter following best practices:
- Exponential backoff: wait_time = base * 2^attempt
- Full jitter: wait_time * random(0.5, 1.5) to prevent thundering herd
- Configurable max attempts and max wait time
- Exception filtering for retryable vs non-retryable errors

References:
- AWS Architecture Blog: Exponential Backoff And Jitter
- https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
"""

import asyncio
import functools
import logging
import random
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, Tuple, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay cap
    exponential_base: float = 2.0  # Exponential multiplier
    jitter: bool = True  # Add randomness to prevent thundering herd
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    non_retryable_exceptions: Tuple[Type[Exception], ...] = ()

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number (0-indexed).

        Uses exponential backoff with optional full jitter.

        Args:
            attempt: Current attempt number (0 for first retry)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: base * 2^attempt
        delay = self.base_delay * (self.exponential_base**attempt)

        # Cap at max delay
        delay = min(delay, self.max_delay)

        # Add jitter (full jitter: random between 0.5x and 1.5x)
        if self.jitter:
            jitter_factor = random.uniform(0.5, 1.5)
            delay *= jitter_factor

        return delay


def is_retryable(
    exception: Exception,
    retryable: Tuple[Type[Exception], ...],
    non_retryable: Tuple[Type[Exception], ...],
) -> bool:
    """Determine if an exception is retryable.

    Args:
        exception: The exception to check
        retryable: Tuple of retryable exception types
        non_retryable: Tuple of non-retryable exception types (takes precedence)

    Returns:
        True if exception should be retried
    """
    # Non-retryable takes precedence
    if isinstance(exception, non_retryable):
        return False

    return isinstance(exception, retryable)


async def retry_async(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
    **kwargs: Any,
) -> T:
    """Execute async function with retry logic.

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        config: Retry configuration (uses defaults if None)
        on_retry: Optional callback(exception, attempt, delay) called before retry
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        Last exception if all retries exhausted
    """
    config = config or RetryConfig()
    last_exception: Optional[Exception] = None

    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)

        except Exception as e:
            last_exception = e

            # Check if retryable
            if not is_retryable(
                e, config.retryable_exceptions, config.non_retryable_exceptions
            ):
                logger.debug(f"Non-retryable exception: {type(e).__name__}: {e}")
                raise

            # Check if more attempts available
            if attempt >= config.max_attempts - 1:
                logger.warning(
                    f"All {config.max_attempts} attempts exhausted: "
                    f"{type(e).__name__}: {e}"
                )
                raise

            # Calculate delay and wait
            delay = config.calculate_delay(attempt)

            if on_retry:
                on_retry(e, attempt, delay)
            else:
                logger.info(
                    f"Attempt {attempt + 1}/{config.max_attempts} failed: "
                    f"{type(e).__name__}. Retrying in {delay:.1f}s"
                )

            await asyncio.sleep(delay)

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic error: no result and no exception")


def async_retry(
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
) -> Callable[[F], F]:
    """Decorator for async functions with retry logic.

    Args:
        config: Retry configuration
        on_retry: Optional callback for retry events

    Returns:
        Decorator function

    Example:
        @async_retry(RetryConfig(max_attempts=3))
        async def fetch_data():
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await retry_async(
                func, *args, config=config, on_retry=on_retry, **kwargs
            )

        return wrapper  # type: ignore[return-value]

    return decorator


# Pre-configured retry configs for common use cases
HTTP_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
)

VEP_RETRY_CONFIG = RetryConfig(
    max_attempts=4,
    base_delay=2.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True,
)

AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=120.0,
    exponential_base=2.0,
    jitter=True,
)
