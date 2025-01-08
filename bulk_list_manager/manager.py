from typing import Optional, Dict, List, Set
import asyncio
import time
from pathlib import Path
import json
from twikit import Client
from .rate_limiter import RateLimiter
from .utils import print_status, save_state, load_state, create_progress_bar

class TwitterListManager:
    """Manages bulk operations for Twitter lists and following status."""
    
    def __init__(self, auth_token: str):
        """Initialize the manager with authentication."""
        self.client = Client(auth_token)
        self.rate_limiter = RateLimiter()
        self.current_batch: List[Dict] = []
        self.processed_users: Set[str] = set()
        self._is_paused = False
        self._should_stop = False
        self.stats = {
            "total": 0,
            "processed": 0,
            "added_to_list": 0,
            "unfollowed": 0,
            "failed": 0,
            "time_to_next": 0
        }
        
    async def create_list(self, name: str, description: Optional[str] = None, 
                         is_private: bool = True) -> Dict:
        """Create a new Twitter list."""
        try:
            response = await self.client.create_list(
                name=name,
                description=description,
                private=is_private
            )
            
            if 'data' in response:
                return response['data']
            return response
        except Exception as e:
            print(f"Failed to create list: {str(e)}")
            raise
    
    async def process_following(self, list_id: str):
        """Process all following accounts in batches."""
        batch_size = 450  # Adjusted to be conservative with rate limits
        following = []
        cursor = None
        
        # Load any saved progress
        saved_state = self.load_progress()
        if saved_state:
            self.processed_users = set(saved_state.get("processed_users", []))
            self.stats = saved_state.get("stats", self.stats)
        
        try:
            # Fetch all following
            while True:
                if self._should_stop:
                    return
                    
                while not await self.rate_limiter.check_limit("get_following"):
                    self.stats["time_to_next"] = await self.rate_limiter.time_until_reset("get_following")
                    print_status(self.stats)
                    await asyncio.sleep(60)
                
                response = await self.client.get_following(cursor=cursor)
                if not response or 'errors' in response:
                    print(f"Error in response: {response.get('errors', 'Unknown error')}")
                    raise Exception("Failed to get following")

                # Handle twikit's response format
                users = response.get('data', [])
                next_token = response.get('meta', {}).get('next_token')
                
                new_users = [user for user in users 
                           if user['id'] not in self.processed_users]
                following.extend(new_users)
                
                await self.rate_limiter.increment("get_following")
                
                if not next_token:
                    break
                cursor = next_token
                
                self.stats["total"] = len(following) + len(self.processed_users)
                print_status(self.stats)
                
            # Process users in batches
            for i in range(0, len(following), batch_size):
                if self._should_stop:
                    break
                    
                batch = following[i:i + batch_size]
                await self._process_batch(batch, list_id)
                
                self.save_progress(list_id)
                
        except Exception as e:
            print(f"Error processing following: {str(e)}")
            self.save_progress(list_id)
            raise
            
    async def _process_batch(self, users: List[Dict], list_id: str):
        """Process a batch of users."""
        for user in users:
            if self._should_stop or self._is_paused:
                return
                
            try:
                # Add to list
                await self.client.add_list_member(list_id=list_id, user_id=user['id'])
                self.stats["added_to_list"] += 1
                
                # Unfollow
                while not await self.rate_limiter.check_limit("unfollow"):
                    self.stats["time_to_next"] = await self.rate_limiter.time_until_reset("unfollow")
                    print_status(self.stats)
                    await asyncio.sleep(60)
                    
                await self.client.unfollow(user_id=user['id'])
                await self.rate_limiter.increment("unfollow")
                self.stats["unfollowed"] += 1
                
                self.processed_users.add(user['id'])
                self.stats["processed"] += 1
                
            except Exception as e:
                print(f"Failed to process user {user['id']}: {str(e)}")
                self.stats["failed"] += 1
                
            print_status(self.stats)
            
    async def pause(self):
        """Pause the current operation."""
        self._is_paused = True
        self.save_progress()
        
    async def resume(self):
        """Resume the current operation."""
        self._is_paused = False
        
    async def stop(self):
        """Stop all operations."""
        self._should_stop = True
        self.save_progress()
        
    def save_progress(self, list_id: str = None):
        """Save current progress to file."""
        state = {
            "processed_users": list(self.processed_users),
            "stats": self.stats,
            "timestamp": time.time()
        }
        if list_id:
            state["list_id"] = list_id
        save_state(state, "twitter_list_manager_state.json")
        
    def load_progress(self) -> Dict:
        """Load progress from file."""
        return load_state("twitter_list_manager_state.json") 