import time
from typing import Dict, Optional
from dataclasses import dataclass

@dataclass
class RateLimit:
    limit: int
    window: int  # in seconds
    current: int = 0
    reset_time: float = 0

class RateLimiter:
    """Handles rate limiting for Twitter API calls."""
    
    def __init__(self):
        """Initialize rate limits for different operations."""
        # All windows are 15 minutes (900 seconds) according to twikit docs
        self.limits: Dict[str, RateLimit] = {
            'unfollow': RateLimit(limit=187, window=900),  # friendships/destroy
            'get_user_following': RateLimit(limit=500, window=900),  # Following endpoint
        }
        
    async def check_limit(self, operation: str) -> bool:
        """Check if operation is within rate limits."""
        if operation not in self.limits:
            return True
            
        limit = self.limits[operation]
        current_time = time.time()
        
        # Reset if window has passed
        if current_time >= limit.reset_time:
            limit.current = 0
            limit.reset_time = current_time + limit.window
            
        return limit.current < limit.limit
        
    async def increment(self, operation: str):
        """Increment the count for an operation."""
        if operation in self.limits:
            self.limits[operation].current += 1
            
    async def time_until_reset(self, operation: str) -> Optional[float]:
        """Get time until rate limit resets."""
        if operation not in self.limits:
            return None
            
        limit = self.limits[operation]
        current_time = time.time()
        
        if current_time >= limit.reset_time:
            return 0
            
        return limit.reset_time - current_time 