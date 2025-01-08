# Twitter List Manager

A Python tool that helps you manage your Twitter following list by moving all followed accounts to a single list and then unfollowing them. Built with [twikit](https://github.com/d60/twikit).

## Features

- Create a new Twitter list (public or private)
- Move all followed accounts to the list
- Unfollow accounts after adding them to the list
- Respect Twitter API rate limits
- Save progress and resume capability
- Interactive CLI with real-time status updates
- Pause/Resume/Stop functionality

## Installation

```bash
# Clone the repository
git clone [repository-url]
cd twitter-list-manager

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
python -m bulk_list_manager.example
```

The tool will:
1. Ask for your Twitter auth token (or use from environment variable `TWITTER_AUTH_TOKEN`)
2. Create a new list with your specified name and settings
3. Process all your following accounts in batches
4. Show real-time progress and statistics

### Rate Limits

The tool respects Twitter's rate limits:
- Following retrieval: 500 requests per 15 minutes
- Unfollowing: 187 requests per 15 minutes

### Progress Tracking

Progress is automatically saved after each batch and can be resumed later. The tool tracks:
- Total accounts processed
- Accounts added to list
- Accounts unfollowed
- Failed operations
- Time until next batch (when rate limited)

## Requirements

- Python 3.7+
- twikit library
- Internet connection
- Twitter auth token

## Error Handling

The tool includes comprehensive error handling:
- Graceful handling of rate limits with waiting periods
- Progress saving on errors or interruptions
- Detailed error logging for failed operations
- Option to resume from last saved state

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[Add your license here] 