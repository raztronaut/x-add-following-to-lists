import asyncio
import os
from pathlib import Path
from manager import TwitterListManager
from utils import load_state

async def main():
    # Check for saved state
    saved_state = load_state("twitter_list_manager_state.json")
    
    # Get auth token from environment or user input
    auth_token = os.getenv("TWITTER_AUTH_TOKEN") or input("Enter your Twitter auth token: ").strip()
    
    # Initialize manager
    manager = TwitterListManager(auth_token)
    
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
            await manager.process_following(list_id)
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
    
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
        manager.save_progress()
        print("Progress saved due to error.")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nApplication error: {str(e)}")
        print("The application has been terminated. Your progress has been saved.") 