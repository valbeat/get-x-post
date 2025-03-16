# get-x-post

A command-line tool to extract post content from X (formerly Twitter) URLs.

## Installation

```bash
# Install required packages
pip install requests beautifulsoup4
```

## Usage

```bash
# Get content from a single URL (outputs JSON by default)
python get_x_post.py https://x.com/user/status/123456789

# Get content from multiple URLs
python get_x_post.py https://x.com/user1/status/123456789 https://x.com/user2/status/987654321

# Read URLs from stdin (works automatically with pipes)
cat urls.txt | python get_x_post.py

# Output as JSONL (one JSON object per line)
python get_x_post.py https://x.com/user/status/123456789 --format jsonl

# Suppress progress messages
python get_x_post.py https://x.com/user/status/123456789 --quiet
```

## Options

```
Input:
  urls                  URL(s) of X/Twitter post(s)
  --limit N             Process only N URLs
  
  Note: The tool automatically detects if data is piped via stdin

Output:
  --format FORMAT       Output format: json (default) or jsonl
  --output, -o FILE     Write output to file instead of stdout
  --quiet, -q           Suppress progress messages
```

## Output Formats

### JSON (default)
```json
{
  "text": "This is a sample tweet with an image.",
  "created_at": "2023-01-01T12:34:56Z",
  "user_name": "Sample User",
  "screen_name": "sample_user",
  "tweet_id": "123456789012345678",
  "url": "https://x.com/sample_user/status/123456789012345678",
  "has_media": true
}
```

### JSONL
```
{"text":"First tweet","user_name":"User1","screen_name":"user1","tweet_id":"123456789","url":"https://x.com/user1/status/123456789"}
{"text":"Second tweet","user_name":"User2","screen_name":"user2","tweet_id":"987654321","url":"https://x.com/user2/status/987654321"}
```

## How It Works

This tool retrieves post content without using X/Twitter's official API. It tries multiple methods sequentially:

1. Twitter OEmbed API
2. Web page metadata scraping
3. Embedded tweet page parsing

X/Twitter may change their platform, potentially affecting this tool's functionality.

## License

MIT
