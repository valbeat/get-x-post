#!/usr/bin/env python3
import argparse
import json
import re
import sys
import requests
from bs4 import BeautifulSoup

def get_tweet_content(url):
    """
    Xの投稿URLから投稿内容を取得する
    
    Args:
        url (str): XのツイートURL (例: https://x.com/username/status/1234567890)
    
    Returns:
        dict: 投稿の情報（テキスト、日時、ユーザー名など）
    """
    # URLのバリデーション
    if not re.match(r'https?://(twitter|x)\.com/\w+/status/\d+', url):
        raise ValueError("Invalid X/Twitter URL format")
    
    # ツイートIDとユーザー名を抽出
    tweet_id = url.split('/')[-1].split('?')[0]
    username = url.split('/')[3]
    
    # 結果を格納する辞書
    result = {
        'text': "",
        'created_at': "",
        'user_name': username,
        'screen_name': username,
        'tweet_id': tweet_id,
        'url': url
    }
    
    # ユーザーエージェントを設定 (ブラウザからのアクセスに見せる)
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
    
    # 方法1: Twitter OEmbed APIを試す
    try:
        oembed_url = f"https://publish.twitter.com/oembed?url={url}"
        response = requests.get(oembed_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            html_content = data.get('html', '')
            
            soup = BeautifulSoup(html_content, 'html.parser')
            tweet_text = soup.get_text().strip()
            
            # テキストからツイート本文だけを抽出
            # パターン: ツイート本文 — ユーザー名 (@スクリーン名) 日付
            tweet_match = re.match(r'(.*?)(?:\s+)?(?:—|\-)(?:\s+)?(.+?) \(@(.+?)\) (.+)$', tweet_text)
            if tweet_match:
                tweet_body, user, screen_name, date = tweet_match.groups()
                result['text'] = tweet_body.strip()
                result['user_name'] = user.strip()
                result['screen_name'] = screen_name.strip()
                
                # 日付情報を抽出する試み
                date_str = date.strip()
                if date_str:
                    result['created_at'] = date_str
            else:
                # 通常のクリーンアップ
                tweet_text = re.sub(r'\s+', ' ', tweet_text)
                result['text'] = tweet_text
                result['user_name'] = data.get('author_name', username)
                
            # OEmbedからメディア情報を抽出
            if 'html' in data:
                media_match = re.search(r'pic\.twitter\.com/([a-zA-Z0-9]+)', data['html'])
                if media_match:
                    # メディアURLの存在を示す（実際のURLは取得できない）
                    result['has_media'] = True
            
            # 追加情報を返す
            return result
    except Exception as e:
        print(f"Twitter OEmbed API failed: {e}")
    
    # 方法2: ウェブページを直接スクレイピング
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # メタデータから情報を取得
            meta_description = soup.find('meta', attrs={'property': 'og:description'})
            if meta_description and meta_description.get('content'):
                description = meta_description.get('content')
                # 末尾の「— ユーザー名 (@スクリーン名) 日付」を除去
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
            
            # 画像情報を取得
            meta_image = soup.find('meta', attrs={'property': 'og:image'})
            if meta_image and meta_image.get('content'):
                image_url = meta_image.get('content')
                # Twitterアイコンの画像は除外
                if not ('responsive-web' in image_url or 'profile_images' in image_url):
                    result['media'] = [image_url]
            
            # 投稿日時の取得を試みる (複数の方法で試す)
            # 方法1: timeタグから
            time_element = soup.find('time')
            if time_element and time_element.get('datetime'):
                result['created_at'] = time_element.get('datetime')
            
            # 方法2: メタデータから
            if not result['created_at']:
                meta_date = soup.find('meta', attrs={'property': 'og:article:published_time'})
                if meta_date and meta_date.get('content'):
                    result['created_at'] = meta_date.get('content')
            
            # 方法3: JSON-LDからの抽出
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
            
            # テキストが取得できていれば結果を返す
            if result['text']:
                return result
    except Exception as e:
        print(f"Direct webpage scraping failed: {e}")
    
    # 方法3: 埋め込みツイート生成を試す
    try:
        # 埋め込みツイートページをリクエスト
        embed_url = f"https://platform.twitter.com/embed/Tweet.html?id={tweet_id}"
        response = requests.get(embed_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # ツイートの本文を探す
            tweet_text_element = soup.select_one('.tweet-text')
            if tweet_text_element:
                result['text'] = tweet_text_element.get_text().strip()
            
            # 投稿者情報を探す
            user_element = soup.select_one('.tweet-header .fullname')
            if user_element:
                result['user_name'] = user_element.get_text().strip()
            
            # スクリーンネームを探す
            screen_name_element = soup.select_one('.tweet-header .username')
            if screen_name_element:
                result['screen_name'] = screen_name_element.get_text().strip().replace('@', '')
            
            # ここでメディア情報も取得できる可能性がある
            media_elements = soup.select('.MediaCard img')
            if media_elements:
                result['media'] = [img.get('src') for img in media_elements if img.get('src')]
            
            # 日付情報の取得を試みる
            timestamp_element = soup.select_one('.tweet-header time')
            if timestamp_element and timestamp_element.get('datetime'):
                result['created_at'] = timestamp_element.get('datetime')
            elif timestamp_element and timestamp_element.get('title'):
                # タイトル属性から日付を抽出
                result['created_at'] = timestamp_element.get('title')
            
            # テキストが取得できていれば結果を返す
            if result['text']:
                return result
    except Exception as e:
        print(f"Embed page scraping failed: {e}")
    
    # すべての方法が失敗した場合は、基本情報だけを返す
    if not result['text']:
        result['text'] = f"X/Twitterの制限によりコンテンツを取得できませんでした。直接リンクを訪問してください: {url}"
    
    return result

# CSVサポートは削除 - UNIXの哲学に従い、専門ツールに任せる


def clean_tweet_data(tweet_data):
    """ツイートデータをクリーニング"""
    cleaned_data = {}
    for key, value in tweet_data.items():
        # 有効なJSONデータのみ含める
        if value or key in ['has_media']:
            cleaned_data[key] = value
    return cleaned_data

def process_url(url, verbose=False):
    """単一のURLを処理"""
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
    
    # 入力ソース
    input_group = parser.add_argument_group('Input options')
    input_group.add_argument('urls', nargs='*', help='URL(s) of the X post(s)')
    input_group.add_argument('--stdin', action='store_true', help='Read URLs from stdin (one URL per line)')
    input_group.add_argument('--limit', type=int, help='Limit the number of tweets to process')
    
    # 出力形式
    output_group = parser.add_argument_group('Output options')
    output_group.add_argument('--format', choices=['json', 'jsonl'], default='json',
                        help='Output format: json (default, array) or jsonl (one JSON per line)')
    output_group.add_argument('--output', '-o', help='Output file path (optional)')
    output_group.add_argument('--quiet', '-q', action='store_true', help='Suppress progress messages')
    
    args = parser.parse_args()
    
    urls_to_process = []
    verbose = not args.quiet
    
    # 標準入力からURLを読み込む
    if args.stdin:
        for line in sys.stdin:
            url = line.strip()
            if url and (url.startswith('http://') or url.startswith('https://')):
                urls_to_process.append(url)
        if verbose:
            print(f"Loaded {len(urls_to_process)} URLs from stdin", file=sys.stderr)
    
    # コマンドラインで指定されたURLを追加
    if args.urls:
        urls_to_process.extend(args.urls)
    
    # URLが指定されていない場合はエラー
    if not urls_to_process:
        print("Error: No URLs provided. Use --stdin or provide URLs as arguments.", file=sys.stderr)
        sys.exit(1)
    
    # 処理数を制限（指定された場合）
    if args.limit and args.limit > 0:
        urls_to_process = urls_to_process[:args.limit]
        if verbose:
            print(f"Processing limited to {args.limit} URLs", file=sys.stderr)
    
    # 出力ファイルを開く（指定されている場合）
    output_file = None
    if args.output:
        try:
            output_file = open(args.output, 'w', encoding='utf-8')
        except Exception as e:
            print(f"Error opening output file: {e}", file=sys.stderr)
            sys.exit(1)
    
    # 結果を格納するリスト（JSON配列形式の場合のみ使用）
    all_results = []
    
    try:
        # 全体の処理数
        total_urls = len(urls_to_process)
        if verbose:
            print(f"Processing {total_urls} URLs...", file=sys.stderr)
        
        # 複数URLの場合はそれぞれ処理
        for i, url in enumerate(urls_to_process):
            if verbose:
                progress = f"[{i+1}/{total_urls}]"
                print(f"{progress} Processing: {url}", file=sys.stderr)
            
            # URLを処理
            tweet_data = process_url(url, verbose=False)
            if not tweet_data:
                continue
            
            # クリーニング（不要なフィールドの削除）
            tweet_data = clean_tweet_data(tweet_data)
            
            # 出力形式に応じた処理
            if args.format == 'jsonl':
                # JSONLinesとして1行ずつ出力
                if output_file:
                    print(json.dumps(tweet_data, ensure_ascii=False), file=output_file)
                else:
                    print(json.dumps(tweet_data, ensure_ascii=False))
            
            elif args.format == 'json':
                # JSON配列用にデータを保存
                all_results.append(tweet_data)
        
        # JSON配列形式の場合は最後にまとめて出力
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
        # 出力ファイルを閉じる
        if output_file:
            output_file.close()
            if verbose:
                print(f"Results saved to {args.output}", file=sys.stderr)

if __name__ == "__main__":
    main()