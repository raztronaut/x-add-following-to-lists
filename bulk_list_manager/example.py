import asyncio
import os
from pathlib import Path
from twikit.errors import (
    BadRequest, Unauthorized, Forbidden, NotFound,
    RequestTimeout, TooManyRequests, ServerError,
    UserNotFound, UserUnavailable
)
from .manager import TwitterListManager
from .utils import load_state

async def get_credentials():
    """Get user credentials."""
    print("\nPlease enter your Twitter credentials:")
    username = input("Username: ").strip()
    email = input("Email: ").strip()
    password = input("Password: ").strip()
    return username, email, password

async def main():
    # Initialize manager
    manager = TwitterListManager()
    
    # Get credentials and login
    try:
        username, email, password = await get_credentials()
        await manager.login(username, email, password)
        print("Successfully authenticated!")
    except Unauthorized:
        print("Error: Authentication failed. Please check your credentials.")
        return
    except Exception as e:
        print(f"Login error: {str(e)}")
        return
    
    # Now check for saved state
    saved_state = load_state("twitter_list_manager_state.json")
    
    if saved_state:
        print("\nFound saved progress:")
        print(f"Processed: {len(saved_state.get('processed_users', []))} accounts")
        resume = input("Would you like to resume? (y/n): ").lower() == 'y'
        
        if resume:
            list_id = saved_state.get("list_id")
            if not list_id:
                print("Error: Could not find list ID in saved state")
                return
            
            print("\nResuming previous operation...")
            try:
                await manager.process_following(list_id)
            except Exception as e:
                print(f"Error resuming operation: {str(e)}")
                manager.save_progress()
            return
    
    # Get list details
    list_name = input("Enter name for your new list: ").strip()
    list_description = input("Enter description (optional): ").strip()
    is_private = input("Make list private? (y/n): ").lower() == 'y'
    
    try:
        # Create list
        print("\nCreating list...")
        list_data = await manager.create_list(
            name=list_name,
            description=list_description,
            is_private=is_private
        )
        
        print(f"\nCreated list: {list_name}")
        print("Starting to process following...")
        
        # Process following
        await manager.process_following(list_data['id'])
        
    except KeyboardInterrupt:
        print("\nOperation paused. Choose an option:")
        print("1. Resume")
        print("2. Save progress and exit")
        print("3. Cancel remaining operations")
        
        while True:
            try:
                choice = input("Enter choice (1-3): ").strip()
                if choice not in ['1', '2', '3']:
                    print("Invalid choice. Please enter 1, 2, or 3.")
                    continue
                break
            except KeyboardInterrupt:
                choice = '2'
                break
        
        if choice == '1':
            print("\nResuming operations...")
            await manager.resume()
        elif choice == '2':
            manager.save_progress()
            print("Progress saved. You can resume later.")
        else:
            await manager.stop()
            print("Operations cancelled.")
    
    except Unauthorized:
        print("Error: Authentication failed. Please check your credentials.")
        manager.save_progress()
    except Forbidden:
        print("Error: You don't have permission to perform this action.")
        manager.save_progress()
    except TooManyRequests:
        print("Rate limit exceeded. Please try again later.")
        manager.save_progress()
    except (UserNotFound, UserUnavailable):
        print("Error: User account is not accessible.")
        manager.save_progress()
    except ServerError:
        print("Twitter's servers are experiencing issues. Please try again later.")
        manager.save_progress()
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        manager.save_progress()
        print("Progress saved due to error.")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nApplication error: {str(e)}")
        print("The application has been terminated. Your progress has been saved.") 