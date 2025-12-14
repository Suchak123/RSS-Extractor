import sys
import asyncio
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
from csv_handler import CSVHandler
from feed_finder import FeedFinder
from hub_parser import RSSHubParser
from utils import (
    normalize_url,
    normalize_feed_url,
    create_db_pool,
    init_db_schema,
    save_batch_results
)


async def process_website(url, feed_finder, hub_parser, session, semaphore):
    async with semaphore:
        original_url = url
        url = normalize_url(url)
        
        if not url:
            print(f"Invalid URL: {original_url}")
            return {'website': original_url, 'rss': 'Not found'}
        
        try:
            if await is_hub_page(url, session):
                print(f"{url} detected as RSS hub page")
                feed_objects = await hub_parser.parse_feeds(url, session)
                
                if not feed_objects:
                    print(f"No feeds found on hub page")
                    feeds = []
                else:
                    if len(feed_objects) > 5:
                        print(f"Validating {len(feed_objects)} feeds from hub...")
                        feed_objects = await hub_parser.validate_feeds(feed_objects, session)
                    
                    feeds = []
                    for f in feed_objects:
                        if isinstance(f, dict) and 'url' in f:
                            normalized = normalize_feed_url(f['url'])
                            if normalized:
                                feeds.append(normalized)
                    
                    feeds = list(dict.fromkeys(feeds))
                    
                    print(f"Found {len(feeds)} valid feed(s) from hub page")
            else:
                found_feeds = await feed_finder.find_feeds(url, session)
                
                feeds = []
                for feed_url in found_feeds:
                    normalized = normalize_feed_url(feed_url)
                    if normalized:
                        feeds.append(normalized)
                
                feeds = list(dict.fromkeys(feeds))

            if feeds:
                print(f"Found {len(feeds)} feed(s) for {url}")
            else:
                print(f"No feeds found for {url}")
                
        except asyncio.TimeoutError:
            print(f"Timeout while processing {url}")
            feeds = []
        except Exception as e:
            print(f"Error finding feeds for {url}: {str(e)}")
            feeds = []
        
        rss_str = '; '.join(feeds) if feeds else 'Not found'
        return {'website': url, 'rss': rss_str}
    

async def is_hub_page(url, session):
    url_lower = url.lower()
    hub_patterns = ['/rss', '/feeds', '/feed-list', '/subscribe', '/syndication']
    return any(pattern in url_lower for pattern in hub_patterns)


async def process_all(websites, feed_finder, hub_parser, max_concurrent=20):
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async with AsyncSession(impersonate="chrome110") as session:
        tasks = [
            process_website(site, feed_finder, hub_parser, session, semaphore) 
            for site in websites
        ]
        
        results = []
        for i, coro in enumerate(asyncio.as_completed(tasks), 1):
            try:
                result = await coro
                results.append(result)
                print(f"[{i}/{len(websites)}] Completed {result['website']}")
            except Exception as e:
                print(f"[{i}/{len(websites)}] Failed with error: {str(e)}")
        
        return results


def print_summary(results):
    total = len(results)
    with_feeds = sum(1 for r in results if r['rss'] != 'Not found')
    without_feeds = total - with_feeds
    
    print("\n" + "="*60)
    print("PROCESSING SUMMARY")
    print("="*60)
    print(f"Total websites processed: {total}")
    print(f"Websites with RSS feeds: {with_feeds}")
    print(f"Websites without RSS feeds: {without_feeds}")
    
    if with_feeds > 0:
        total_feeds = sum(
            len(r['rss'].split(';')) 
            for r in results 
            if r['rss'] != 'Not found'
        )
        avg_feeds = total_feeds / with_feeds
        print(f"Total RSS feeds found: {total_feeds}")
        print(f"Average feeds per website: {avg_feeds:.1f}")
    print("="*60 + "\n")


async def main_async():
    input_csv = 'input_websites.csv'
    
    if len(sys.argv) > 1:
        input_csv = sys.argv[1]
    
    print(f"Reading websites from: {input_csv}")
    websites = CSVHandler.read_websites(input_csv)
    
    if not websites:
        print("No websites to process. Add websites to the input CSV and run again.")
        return
    
    print(f"Loaded {len(websites)} website(s) to process\n")
    
    feed_finder = FeedFinder()
    hub_parser = RSSHubParser()

    print("Connecting to database...")
    try:
        pool = await create_db_pool(
            db_host="localhost",
            db_port=5432,
            db_name="rss_extractor",
            db_user="rss_user",
            db_password="rss_password"
        )
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        return

    await init_db_schema(pool)
    print("Database ready\n")

    print(f"Starting to process {len(websites)} websites...\n")
    results = await process_all(websites, feed_finder, hub_parser)

    print("\nSaving results to database...")
    try:
        await save_batch_results(pool, results)
        print("Successfully saved all results to PostgreSQL")
    except Exception as e:
        print(f"Error saving to database: {e}")
    finally:
        await pool.close()

    print_summary(results)


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()