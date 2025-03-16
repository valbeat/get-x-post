#!/usr/bin/env python3
import argparse
import json
import re
import sys
import requests
from bs4 import BeautifulSoup

def get_tweet_content(url):
    """
    Extract content from an X (formerly Twitter) post URL.
    
    Args:
        url (str): X post URL (e.g., https://x.com/username/status/1234567890)
    
    Returns:
        dict: Post information (text, timestamp, username, etc.)
    """
    # URL validation
    if not re.match(r'https?://(twitter|x)\.com/\w+/status/\d+', url):
        raise ValueError("Invalid X/Twitter URL format")
    
    # Extract tweet ID and username
    tweet_id = url.split('/')[-1].split('?')[0]
    username = url.split('/')[3]
    
    # Initialize result dictionary
    result = {
        'text': "",
        'created_at': "",
        'user_name': username,
        'screen_name': username,
        'tweet_id': tweet_id,
        'url': url
    }
    
    # Set up browser-like headers for requests
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://twitter.com/',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    
    # Method 1: Try Twitter OEmbed API
    try:
        oembed_url = f"https://publish.twitter.com/oembed?url={url}"
        response = requests.get(oembed_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            html_content = data.get('html', '')
            
            soup = BeautifulSoup(html_content, 'html.parser')
            tweet_text = soup.get_text().strip()
            
            # Extract tweet text from the pattern: Tweet text — Username (@ScreenName) Date
            tweet_match = re.match(r'(.*?)(?:\s+)?(?:—|\-)(?:\s+)?(.+?) \(@(.+?)\) (.+)$', tweet_text)
            if tweet_match:
                tweet_body, user, screen_name, date = tweet_match.groups()
                result['text'] = tweet_body.strip()
                result['user_name'] = user.strip()
                result['screen_name'] = screen_name.strip()
                
                # Try to extract date information
                date_str = date.strip()
                if date_str:
                    result['created_at'] = date_str
            else:
                # Regular cleanup if the pattern doesn't match
                tweet_text = re.sub(r'\s+', ' ', tweet_text)
                result['text'] = tweet_text
                result['user_name'] = data.get('author_name', username)
                
            # Extract media information from OEmbed
            if 'html' in data:
                media_match = re.search(r'pic\.twitter\.com/([a-zA-Z0-9]+)', data['html'])
                if media_match:
                    # Indicate media presence (actual URL can't be retrieved)
                    result['has_media'] = True
            
            # Return the result with additional info
            return result
    except Exception as e:
        print(f"Twitter OEmbed API failed: {e}", file=sys.stderr)
    
    # Method 2: Direct webpage scraping
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Get information from metadata
            meta_description = soup.find('meta', attrs={'property': 'og:description'})
            if meta_description and meta_description.get('content'):
                description = meta_description.get('content')
                # Remove trailing "— Username (@ScreenName) Date"
                if ' — ' in description:
                    result['text'] = description.split(' — ')[0].strip()
                elif 'pic.twitter.com/' in description:
                    result['text'] = description.split('pic.twitter.com/')[0].strip()
                else:
                    result['text'] = description
            
            meta_title = soup.find('meta', attrs={'property': 'og:title'})
            if meta_title and meta_title.get('content'):
                title_text = meta_title.get('content')
                if ' on Twitter:' in title_text:
                    result['user_name'] = title_text.split(' on Twitter:')[0]
                elif ' on X:' in title_text:
                    result['user_name'] = title_text.split(' on X:')[0]
            
            # Get image information
            meta_image = soup.find('meta', attrs={'property': 'og:image'})
            if meta_image and meta_image.get('content'):
                image_url = meta_image.get('content')
                # Exclude Twitter icon images
                if not ('responsive-web' in image_url or 'profile_images' in image_url):
                    result['media'] = [image_url]
            
            # Try multiple methods to get the post timestamp
            # Method 1: From time tag
            time_element = soup.find('time')
            if time_element and time_element.get('datetime'):
                result['created_at'] = time_element.get('datetime')
            
            # Method 2: From metadata
            if not result['created_at']:
                meta_date = soup.find('meta', attrs={'property': 'og:article:published_time'})
                if meta_date and meta_date.get('content'):
                    result['created_at'] = meta_date.get('content')
            
            # Method 3: From JSON-LD extraction
            if not result['created_at']:
                for script in soup.find_all('script', type='application/ld+json'):
                    try:
                        json_data = json.loads(script.string)
                        if isinstance(json_data, dict) and 'dateCreated' in json_data:
                            result['created_at'] = json_data['dateCreated']
                            break
                        elif isinstance(json_data, dict) and 'datePublished' in json_data:
                            result['created_at'] = json_data['datePublished']
                            break
                    except:
                        pass
            
            # Return result if text was successfully retrieved
            if result['text']:
                return result
    except Exception as e:
        print(f"Direct webpage scraping failed: {e}", file=sys.stderr)
    
    # Method 3: Try embedded tweet page
    try:
        # Request embedded tweet page
        embed_url = f"https://platform.twitter.com/embed/Tweet.html?id={tweet_id}"
        response = requests.get(embed_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find tweet text
            tweet_text_element = soup.select_one('.tweet-text')
            if tweet_text_element:
                result['text'] = tweet_text_element.get_text().strip()
            
            # Find author information
            user_element = soup.select_one('.tweet-header .fullname')
            if user_element:
                result['user_name'] = user_element.get_text().strip()
            
            # Find screen name
            screen_name_element = soup.select_one('.tweet-header .username')
            if screen_name_element:
                result['screen_name'] = screen_name_element.get_text().strip().replace('@', '')
            
            # Media information may also be available here
            media_elements = soup.select('.MediaCard img')
            if media_elements:
                result['media'] = [img.get('src') for img in media_elements if img.get('src')]
            
            # Try to get date information
            timestamp_element = soup.select_one('.tweet-header time')
            if timestamp_element and timestamp_element.get('datetime'):
                result['created_at'] = timestamp_element.get('datetime')
            elif timestamp_element and timestamp_element.get('title'):
                # Extract date from title attribute
                result['created_at'] = timestamp_element.get('title')
            
            # Return result if text was successfully retrieved
            if result['text']:
                return result
    except Exception as e:
        print(f"Embed page scraping failed: {e}", file=sys.stderr)
    
    # If all methods fail, return basic information only
    if not result['text']:
        result['text'] = f"Content couldn't be retrieved due to X/Twitter limitations. Please visit the link directly: {url}"
    
    return result

# CSV support removed - following UNIX philosophy, let specialized tools handle it


def clean_tweet_data(tweet_data):
    """Clean tweet data to remove empty values."""
    cleaned_data = {}
    for key, value in tweet_data.items():
        # Include only valid JSON data
        if value or key in ['has_media']:
            cleaned_data[key] = value
    return cleaned_data


def process_url(url, verbose=False):
    """Process a single URL."""
    if verbose:
        print(f"Processing: {url}", file=sys.stderr)
        
    try:
        return get_tweet_content(url)
    except ValueError as e:
        print(f"Error with URL {url}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Unexpected error with URL {url}: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description='Get content from X (Twitter) post')
    
    # Input sources
    input_group = parser.add_argument_group('Input options')
    input_group.add_argument('urls', nargs='*', help='URL(s) of the X post(s)')
    input_group.add_argument('--stdin', action='store_true', help='Read URLs from stdin (one URL per line)')
    input_group.add_argument('--limit', type=int, help='Limit the number of tweets to process')
    
    # Output format
    output_group = parser.add_argument_group('Output options')
    output_group.add_argument('--format', choices=['json', 'jsonl'], default='json',
                        help='Output format: json (default, array) or jsonl (one JSON per line)')
    output_group.add_argument('--output', '-o', help='Output file path (optional)')
    output_group.add_argument('--quiet', '-q', action='store_true', help='Suppress progress messages')
    
    args = parser.parse_args()
    
    urls_to_process = []
    verbose = not args.quiet
    
    # Read URLs from stdin
    if args.stdin:
        for line in sys.stdin:
            url = line.strip()
            if url and (url.startswith('http://') or url.startswith('https://')):
                urls_to_process.append(url)
        if verbose:
            print(f"Loaded {len(urls_to_process)} URLs from stdin", file=sys.stderr)
    
    # Add URLs specified on command line
    if args.urls:
        urls_to_process.extend(args.urls)
    
    # Error if no URLs provided
    if not urls_to_process:
        print("Error: No URLs provided. Use --stdin or provide URLs as arguments.", file=sys.stderr)
        sys.exit(1)
    
    # Limit number of URLs to process (if specified)
    if args.limit and args.limit > 0:
        urls_to_process = urls_to_process[:args.limit]
        if verbose:
            print(f"Processing limited to {args.limit} URLs", file=sys.stderr)
    
    # Open output file (if specified)
    output_file = None
    if args.output:
        try:
            output_file = open(args.output, 'w', encoding='utf-8')
        except Exception as e:
            print(f"Error opening output file: {e}", file=sys.stderr)
            sys.exit(1)
    
    # List to store results (used only for JSON array format)
    all_results = []
    
    try:
        # Total number of URLs to process
        total_urls = len(urls_to_process)
        if verbose:
            print(f"Processing {total_urls} URLs...", file=sys.stderr)
        
        # Process each URL
        for i, url in enumerate(urls_to_process):
            if verbose:
                progress = f"[{i+1}/{total_urls}]"
                print(f"{progress} Processing: {url}", file=sys.stderr)
            
            # Process the URL
            tweet_data = process_url(url, verbose=False)
            if not tweet_data:
                continue
            
            # Clean data (remove empty fields)
            tweet_data = clean_tweet_data(tweet_data)
            
            # Process according to output format
            if args.format == 'jsonl':
                # Output as JSON Lines (one per line)
                if output_file:
                    print(json.dumps(tweet_data, ensure_ascii=False), file=output_file)
                else:
                    print(json.dumps(tweet_data, ensure_ascii=False))
            
            elif args.format == 'json':
                # Save data for JSON array output
                all_results.append(tweet_data)
        
        # Output JSON array format at the end
        if args.format == 'json' and all_results:
            json_output = json.dumps(
                all_results[0] if len(all_results) == 1 else all_results, 
                ensure_ascii=False, 
                indent=2
            )
            
            if output_file:
                print(json_output, file=output_file)
            else:
                print(json_output)
        
        if verbose:
            print(f"\nCompleted processing {len(all_results)} of {total_urls} URLs", file=sys.stderr)
    
    except KeyboardInterrupt:
        if verbose:
            print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(130)  # 128 + SIGINT
    
    finally:
        # Close output file
        if output_file:
            output_file.close()
            if verbose:
                print(f"Results saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()