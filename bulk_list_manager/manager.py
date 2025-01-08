from typing import Optional, Dict, List, Set
import asyncio
import time
from pathlib import Path
import json
from twikit import Client
from twikit.errors import (
    BadRequest, Unauthorized, Forbidden, NotFound,
    RequestTimeout, TooManyRequests, ServerError,
    UserNotFound, UserUnavailable
)
from .rate_limiter import RateLimiter
from .utils import print_status, save_state, load_state, create_progress_bar

class TwitterListManager:
    """Manages bulk operations for Twitter lists and following status."""
    
    def __init__(self):
        """Initialize the manager."""
        self.client = Client('en-US')  # Twikit requires locale
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
        self.cookies_file = "twitter_cookies.json"
        
    async def login(self, username: str, email: str, password: str):
        """Login to Twitter and save cookies."""
        try:
            # Try loading existing cookies first
            if Path(self.cookies_file).exists():
                await self.client.load_cookies(self.cookies_file)
                print("Loaded existing session from cookies")
                return

            # If no cookies or they're invalid, perform fresh login
            await self.client.login(
                auth_info_1=username,
                auth_info_2=email,
                password=password
            )
            # Save cookies for future use
            await self.client.save_cookies(self.cookies_file)
            print("Successfully logged in and saved session")
        except Exception as e:
            print(f"Login failed: {str(e)}")
            raise
        
    async def create_list(self, name: str, description: Optional[str] = None, 
                         is_private: bool = True) -> Dict:
        """Create a new Twitter list."""
        try:
            print(f"Creating list '{name}'...")
            # Add cooldown before request
            await asyncio.sleep(2)
            
            response = await self.client.create_list(
                name=name,
                description=description,
                private=is_private  # Twikit uses 'private' instead of 'is_private'
            )
            
            if not response:
                raise BadRequest("Failed to create list")
                
            return response
        except Exception as e:
            print(f"Failed to create list: {str(e)}")
            raise
    
    async def process_following(self, list_id: str):
        """Process all following accounts in batches."""
        batch_size = 450  # Conservative with rate limits
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
                
                try:
                    response = await self.client.get_user_follows(cursor=cursor)
                    if not response:
                        raise NotFound("Failed to get following")

                    # Handle twikit's response format
                    users = response.get('users', []) if isinstance(response, dict) else []
                    
                    new_users = [user for user in users 
                               if user.get('rest_id') not in self.processed_users]
                    following.extend(new_users)
                    
                    await self.rate_limiter.increment("get_following")
                    
                    if len(users) < batch_size:  # No more users to fetch
                        break
                    cursor = users[-1].get('rest_id')  # Use last user's ID as cursor
                    
                    self.stats["total"] = len(following) + len(self.processed_users)
                    print_status(self.stats)
                except (UserNotFound, UserUnavailable) as e:
                    print(f"User error: {str(e)}")
                    continue
                
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
                user_id = user.get('rest_id')
                if not user_id:
                    continue

                # Add cooldown between operations
                await asyncio.sleep(2)

                # Add to list
                await self.client.add_list_member(list_id, user_id)
                self.stats["added_to_list"] += 1
                
                # Add cooldown between operations
                await asyncio.sleep(2)
                
                # Unfollow
                while not await self.rate_limiter.check_limit("unfollow"):
                    self.stats["time_to_next"] = await self.rate_limiter.time_until_reset("unfollow")
                    print_status(self.stats)
                    await asyncio.sleep(60)
                    
                await self.client.unfollow(user_id)
                await self.rate_limiter.increment("unfollow")
                self.stats["unfollowed"] += 1
                
                self.processed_users.add(user_id)
                self.stats["processed"] += 1
                
            except (BadRequest, Forbidden, NotFound, UserNotFound, UserUnavailable) as e:
                print(f"Failed to process user {user.get('rest_id', 'unknown')}: {str(e)}")
                self.stats["failed"] += 1
            except TooManyRequests:
                print("Rate limit exceeded. Waiting...")
                await asyncio.sleep(900)  # Wait 15 minutes
            except Exception as e:
                print(f"Unexpected error processing user: {str(e)}")
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