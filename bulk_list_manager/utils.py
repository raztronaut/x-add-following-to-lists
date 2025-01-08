import json
from typing import Dict, Any
from pathlib import Path

def format_time(seconds: float) -> str:
    """Format seconds into MM:SS format."""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"

def create_progress_bar(current: int, total: int, width: int = 50) -> str:
    """Create a progress bar string."""
    filled = int(width * current / total)
    bar = "=" * filled + "-" * (width - filled)
    percent = current / total * 100
    return f"[{bar}] {percent:.1f}%"

def save_state(state: Dict[str, Any], filename: str):
    """Save current state to a JSON file."""
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w') as f:
        json.dump(state, f)
        
def load_state(filename: str) -> Dict[str, Any]:
    """Load state from a JSON file."""
    path = Path(filename)
    
    if not path.exists():
        return {}
        
    with open(path) as f:
        return json.load(f)

def print_status(stats: Dict[str, Any]):
    """Print current status in a formatted way."""
    print("\n=== Current Status ===")
    print(f"Processed: {stats['processed']}/{stats['total']} accounts")
    print(f"Added to list: {stats['added_to_list']}")
    print(f"Unfollowed: {stats['unfollowed']}")
    print(f"Failed: {stats['failed']}")
    if stats.get('time_to_next'):
        print(f"Time until next batch: {format_time(stats['time_to_next'])}")
    print("=" * 20) 