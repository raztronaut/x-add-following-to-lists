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
        self.client = Client('en-US')  # Initialize with locale
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

    async def login(self, username: str = None, email: str = None, password: str = None, 
                   auth_token: str = None, ct0: str = None):
        """Login to Twitter using either credentials or cookies."""
        try:
            # If auth_token and ct0 are provided, use them
            if auth_token and ct0:
                # Create a cookies dictionary
                cookies = {
                    "auth_token": auth_token,
                    "ct0": ct0,
                    "x-csrf-token": ct0  # Add CSRF token as cookie
                }
                # Set cookies using client's method
                self.client.set_cookies(cookies)
                print("Successfully set authentication cookies")
                return

            # If credentials provided, use them
            if username and email and password:
                await self.client.login(
                    auth_info_1=username,
                    auth_info_2=email,
                    password=password
                )
                print("Successfully logged in")
            else:
                raise ValueError("Either credentials or auth cookies must be provided")
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
                is_private=is_private
            )
            
            if not response:
                raise BadRequest("Failed to create list")
            
            # Extract list ID from response
            list_id = getattr(response, 'id', None)
            if not list_id:
                raise BadRequest("Failed to get list ID from response")
                
            return {"id": list_id, "name": name}
        except Exception as e:
            print(f"Failed to create list: {str(e)}")
            raise
    
    async def process_following(self, list_id: str):
        """Process all following accounts in batches."""
        batch_size = 200  # Increased since we have 500 requests per 15 min window
        following = []
        cursor = None
        
        # Load any saved progress
        saved_state = self.load_progress()
        if saved_state:
            self.processed_users = set(saved_state.get("processed_users", []))
            self.stats = saved_state.get("stats", self.stats)
        
        try:
            # Get the authenticated user's ID
            user_id = await self.client.user_id()
            
            # Fetch all following
            while True:
                if self._should_stop:
                    return
                    
                # Check rate limit for get_user_following (500 per 15 min)
                while not await self.rate_limiter.check_limit("get_user_following"):
                    self.stats["time_to_next"] = await self.rate_limiter.time_until_reset("get_user_following")
                    print_status(self.stats)
                    await asyncio.sleep(60)
                
                try:
                    # Get following using the user_id, count, and cursor
                    response = await self.client.get_user_following(
                        user_id=user_id,
                        count=batch_size,
                        cursor=cursor
                    )
                    if not response:
                        raise NotFound("Failed to get following")

                    # Handle twikit's Result[User] format
                    users = response
                    
                    new_users = [user for user in users 
                               if str(getattr(user, 'id', None)) not in self.processed_users]
                    following.extend(new_users)
                    
                    await self.rate_limiter.increment("get_user_following")
                    
                    # Update cursor for next iteration
                    cursor = response.next_cursor
                    if not cursor or len(response) < batch_size:  # No more users to fetch
                        break
                    
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
                user_id = str(getattr(user, 'id', None))
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
                    
                await self.client.unfollow_user(user_id)
                await self.rate_limiter.increment("unfollow")
                self.stats["unfollowed"] += 1
                
                self.processed_users.add(user_id)
                self.stats["processed"] += 1
                
            except (BadRequest, Forbidden, NotFound, UserNotFound, UserUnavailable) as e:
                print(f"Failed to process user {getattr(user, 'id', 'unknown')}: {str(e)}")
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