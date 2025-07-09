"""
Retry utilities for Automoy.

This module provides functions for retrying operations with exponential backoff.
"""

import logging
import random
import time
from functools import wraps
from typing import Callable, Any, Optional, Type, Tuple, List, Dict, Union

# Get a logger for this module
logger = logging.getLogger(__name__)

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions_to_retry: Tuple[Type[Exception], ...] = (Exception,),
    retry_logger: Optional[logging.Logger] = None,
    on_retry_callback: Optional[Callable[[Exception, int, float], None]] = None
):
    """
    Retry a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retries
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Factor to multiply delay by after each retry
        jitter: Whether to add random jitter to delay
        exceptions_to_retry: Tuple of exceptions to retry on
        retry_logger: Logger to use for retry messages
        on_retry_callback: Callback to call on each retry with (exception, retry_count, delay)
    
    Returns:
        Decorator function
    """
    retry_logger = retry_logger or logger

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retry_count = 0
            delay = base_delay
            
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions_to_retry as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        retry_logger.error(f"Failed after {retry_count-1} retries: {e}")
                        raise
                    
                    # Calculate delay with optional jitter
                    if jitter:
                        delay_with_jitter = delay * (0.5 + random.random())
                    else:
                        delay_with_jitter = delay
                    
                    # Cap delay at max_delay
                    actual_delay = min(delay_with_jitter, max_delay)
                    
                    retry_logger.warning(f"Retry {retry_count}/{max_retries} after {actual_delay:.2f}s due to {e.__class__.__name__}: {e}")
                    
                    # Call callback if provided
                    if on_retry_callback:
                        on_retry_callback(e, retry_count, actual_delay)
                    
                    # Sleep before retry
                    time.sleep(actual_delay)
                    
                    # Increase delay for next retry
                    delay = min(delay * backoff_factor, max_delay)
        
        return wrapper
    
    return decorator
