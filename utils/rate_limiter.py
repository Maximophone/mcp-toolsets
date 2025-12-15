"""
Rate Limiting Utilities for LinkedIn API

Provides two rate limiters:
1. RateLimiter - Proactive rate limiting with daily limits, jitter, and persistent storage
2. ReactiveRateLimiter - Reactive rate limiting with exponential backoff

LinkedIn (unofficial API) requires conservative rate limiting to avoid account restrictions.
"""

import json
import time
import logging
import random
from datetime import datetime, date, time as dt_time
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Default rate limit storage directory
DEFAULT_RATE_LIMIT_DIR = Path(__file__).parent.parent / "data" / "rate_limits"


class RateLimiter:
    """
    Proactive rate limiter with daily limits, jitter, night mode, and persistent storage.
    
    Designed for LinkedIn's unofficial API where we need to be conservative and
    appear human-like in our request patterns.
    """
    
    def __init__(
        self,
        name: str,
        min_delay_seconds: float = 10.0,
        max_delay_seconds: float = 30.0,
        max_per_day: int = 500,
        night_mode: bool = False,
        backoff_factor: float = 2.0,
        max_backoff_seconds: float = 300.0,
        storage_dir: Optional[Path] = None
    ):
        """
        Initialize rate limiter with configurable parameters.
        
        Args:
            name: Unique name for this rate limiter (used for persistent storage)
            min_delay_seconds: Minimum delay between operations
            max_delay_seconds: Maximum delay between operations (for jitter)
            max_per_day: Maximum number of operations per day
            night_mode: Whether to pause operations during night hours (00:30-07:30)
            backoff_factor: Multiplier for exponential backoff on failures
            max_backoff_seconds: Maximum backoff delay in seconds
            storage_dir: Directory for persistent storage (defaults to data/rate_limits)
        """
        self.name = name
        self.min_delay = min_delay_seconds
        self.max_delay = max_delay_seconds
        self.max_per_day = max_per_day
        self.night_mode = night_mode
        self.backoff_factor = backoff_factor
        self.max_backoff_seconds = max_backoff_seconds
        
        # Track consecutive failures for backoff
        self.consecutive_failures = 0
        self.current_backoff = min_delay_seconds
        
        # Night mode time settings (if enabled)
        self.night_start = dt_time(hour=0, minute=30)   # 00:30
        self.morning_start = dt_time(hour=7, minute=30)  # 07:30
        
        # Create rate limit directory
        self.rate_limit_dir = storage_dir or DEFAULT_RATE_LIMIT_DIR
        self.rate_limit_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize rate limiting from persistent storage
        self._init_rate_limiting()
    
    def _init_rate_limiting(self):
        """Initialize rate limiting data from persistent storage."""
        self.rate_limit_file = self.rate_limit_dir / f"{self.name}_rate_limit.json"
        
        # Default rate limit data
        self.rate_limit_data = {
            "date": str(date.today()),
            "operations_count": 0,
            "last_operation_time": None
        }
        
        # Load existing data if available
        if self.rate_limit_file.exists():
            try:
                with open(self.rate_limit_file, 'r') as f:
                    stored_data = json.load(f)
                
                # Reset counter if it's a new day
                if stored_data.get("date") == str(date.today()):
                    self.rate_limit_data = stored_data
                else:
                    # It's a new day, save default data
                    self._save_rate_limit_data()
            except Exception as e:
                logger.error(f"Error loading rate limit data: {e}")
                self._save_rate_limit_data()
        else:
            self._save_rate_limit_data()
    
    def _save_rate_limit_data(self):
        """Save rate limiting data to persistent storage."""
        try:
            with open(self.rate_limit_file, 'w') as f:
                json.dump(self.rate_limit_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving rate limit data: {e}")
    
    def _is_night_time(self) -> bool:
        """Check if current time is during night hours."""
        if not self.night_mode:
            return False
        current_time = datetime.now().time()
        return self.night_start <= current_time < self.morning_start
    
    def get_remaining_today(self) -> int:
        """Get the number of remaining operations for today."""
        # Refresh data in case date changed
        if self.rate_limit_data.get("date") != str(date.today()):
            self.rate_limit_data = {
                "date": str(date.today()),
                "operations_count": 0,
                "last_operation_time": None
            }
            self._save_rate_limit_data()
        
        return max(0, self.max_per_day - self.rate_limit_data["operations_count"])
    
    def get_operations_today(self) -> int:
        """Get the number of operations performed today."""
        if self.rate_limit_data.get("date") != str(date.today()):
            return 0
        return self.rate_limit_data["operations_count"]
    
    def wait(self) -> bool:
        """
        Implement rate limiting logic between operations.
        
        Returns:
            bool: True if the operation should proceed, False if daily limit reached
        """
        current_time = time.time()
        
        # Check if it's a new day - reset counters
        if self.rate_limit_data.get("date") != str(date.today()):
            self.rate_limit_data = {
                "date": str(date.today()),
                "operations_count": 0,
                "last_operation_time": None
            }
            self._save_rate_limit_data()
        
        # Check night mode restrictions
        if self._is_night_time():
            logger.warning(
                f"Night mode active for {self.name}. "
                f"Operations paused until 07:30."
            )
            return False
        
        # Check if we've hit the daily limit
        if self.rate_limit_data["operations_count"] >= self.max_per_day:
            logger.warning(
                f"Daily limit reached for {self.name}: "
                f"{self.rate_limit_data['operations_count']}/{self.max_per_day} operations"
            )
            return False
        
        # Calculate delay with backoff if there were failures
        base_delay = max(self.min_delay, self.current_backoff)
        
        if self.rate_limit_data["last_operation_time"] is not None:
            time_since_last = current_time - self.rate_limit_data["last_operation_time"]
            if time_since_last < base_delay:
                wait_time = base_delay - time_since_last
                # Add jitter
                if self.max_delay > base_delay:
                    jitter = random.uniform(0, self.max_delay - base_delay)
                    wait_time += jitter
                
                logger.info(
                    f"Rate limiting for {self.name}: waiting {wait_time:.1f}s. "
                    f"Operations today: {self.rate_limit_data['operations_count']}/{self.max_per_day}"
                )
                time.sleep(wait_time)
        
        return True
    
    def record_success(self):
        """Record a successful operation and reset backoff."""
        self.consecutive_failures = 0
        self.current_backoff = self.min_delay
        
        # Update rate limit data
        self.rate_limit_data["last_operation_time"] = time.time()
        self.rate_limit_data["operations_count"] += 1
        self._save_rate_limit_data()
        
        logger.debug(
            f"Operation recorded for {self.name}. "
            f"Total today: {self.rate_limit_data['operations_count']}/{self.max_per_day}"
        )
    
    def record_failure(self):
        """Record a failed operation and increase backoff."""
        self.consecutive_failures += 1
        
        # Exponential backoff with maximum limit
        self.current_backoff = min(
            self.current_backoff * self.backoff_factor,
            self.max_backoff_seconds
        )
        
        self.rate_limit_data["last_operation_time"] = time.time()
        self._save_rate_limit_data()
        
        logger.warning(
            f"Operation failed for {self.name}. "
            f"Consecutive failures: {self.consecutive_failures}. "
            f"Next backoff delay: {self.current_backoff:.1f}s"
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get current rate limiter status."""
        return {
            "name": self.name,
            "operations_today": self.get_operations_today(),
            "max_per_day": self.max_per_day,
            "remaining_today": self.get_remaining_today(),
            "current_backoff": self.current_backoff,
            "consecutive_failures": self.consecutive_failures,
            "night_mode": self.night_mode,
            "is_night_time": self._is_night_time(),
        }


class ReactiveRateLimiter:
    """
    A reactive rate limiter that only introduces delays after encountering rate limit errors.
    
    Unlike RateLimiter, this doesn't enforce delays proactively - it only backs off
    when errors occur, then gradually recovers.
    """
    
    def __init__(
        self,
        name: str,
        initial_backoff_seconds: float = 1.0,
        backoff_factor: float = 2.0,
        max_backoff_seconds: float = 600.0,
        max_retries: int = 10,
        recovery_factor: float = 2.0,
        min_backoff_threshold: float = 0.01
    ):
        """
        Initialize a reactive rate limiter.
        
        Args:
            name: Identifier for this rate limiter instance
            initial_backoff_seconds: Initial delay after first rate limit error
            backoff_factor: Multiplier for exponential backoff
            max_backoff_seconds: Maximum delay in seconds
            max_retries: Maximum retry attempts before giving up
            recovery_factor: Factor to decrease backoff after successful calls
            min_backoff_threshold: Values below this are treated as zero
        """
        self.name = name
        self.initial_backoff_seconds = initial_backoff_seconds
        self.backoff_factor = backoff_factor
        self.max_backoff_seconds = max_backoff_seconds
        self.max_retries = max_retries
        self.recovery_factor = recovery_factor
        self.min_backoff_threshold = min_backoff_threshold
        
        # Runtime state
        self.current_backoff = 0
        self._retry_count = 0
        self._has_had_failures = False
        self._consecutive_successes = 0
    
    def wait(self) -> bool:
        """
        Wait based on current backoff status.
        Returns immediately if no failures have occurred.
        
        Returns:
            bool: True if operation should proceed, False if max retries exceeded
        """
        if self.exceeded_max_retries():
            return False
        
        if not self._has_had_failures:
            return True
        
        if self.current_backoff > 0:
            logger.info(f"Rate limiting for {self.name}: waiting {self.current_backoff:.1f}s")
            time.sleep(self.current_backoff)
        
        return True
    
    def record_success(self):
        """Record a successful API call and gradually reduce backoff."""
        self._consecutive_successes += 1
        
        if self._has_had_failures and self.current_backoff > 0:
            self.current_backoff = max(0, self.current_backoff / self.recovery_factor)
            
            if self.current_backoff < self.min_backoff_threshold:
                self.current_backoff = 0
            
            if self.current_backoff > 0:
                logger.debug(
                    f"Reducing backoff for {self.name} to {self.current_backoff:.1f}s"
                )
            elif self._consecutive_successes >= 3:
                self._has_had_failures = False
                self._retry_count = 0
                logger.debug(f"Backoff fully recovered for {self.name}")
    
    def record_failure(self):
        """Record a rate limit failure and increase backoff."""
        self._has_had_failures = True
        self._retry_count += 1
        self._consecutive_successes = 0
        
        if self.current_backoff == 0:
            self.current_backoff = self.initial_backoff_seconds
        else:
            self.current_backoff = min(
                self.current_backoff * self.backoff_factor,
                self.max_backoff_seconds
            )
        
        logger.warning(
            f"Rate limit hit for {self.name}. "
            f"Retry {self._retry_count}/{self.max_retries}. "
            f"Backoff: {self.current_backoff:.1f}s"
        )
    
    def exceeded_max_retries(self) -> bool:
        """Check if maximum retry attempts have been exceeded."""
        return self._retry_count >= self.max_retries
    
    def reset(self):
        """Reset the rate limiter state."""
        self._retry_count = 0
        self._has_had_failures = False
        self.current_backoff = 0
        self._consecutive_successes = 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get current rate limiter status."""
        return {
            "name": self.name,
            "retry_count": self._retry_count,
            "max_retries": self.max_retries,
            "current_backoff": self.current_backoff,
            "has_had_failures": self._has_had_failures,
            "consecutive_successes": self._consecutive_successes,
        }

