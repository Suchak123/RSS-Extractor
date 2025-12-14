from bs4 import BeautifulSoup
from curl_cffi import AsyncSession
import asyncpg
from urllib.parse import urlparse


async def fetch_html(url, headers=None, session=None):
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0'}
    
    close_session = False
    if session is None:
        session = AsyncSession(impersonate="chrome110")
        close_session = True
    
    try:
        response = await session.get(url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return None
    finally:
        if close_session:
            await session.close()

def detect_cms(soup, html_text):
    text = html_text.lower()

    if 'wp-content' in text or 'wp-' in text:
        return 'wordpress'

    if 'drupal' in text:
        return 'drupal'

    if '/ghost/' in text:
        return 'ghost'

    if 'medium.com' in text:
        return 'medium'

    return None

def get_cms_feed_paths(cms):
    paths = {
        'wordpress': ['/feed', '/comments/feed', '/blog/feed'],
        'drupal': ['/rss.xml', '/feed'],
        'ghost': ['/rss/'],
        'medium': ['/feed']
    }
    return paths.get(cms, [])

async def is_rss_feed(url, headers=None, session=None):
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0'}
    
    close_session = False
    if session is None:
        session = AsyncSession(impersonate="chrome110")
        close_session = True
    
    try:
        response = await session.get(url, headers=headers, timeout=8, allow_redirects=True, verify=False)

        if response.status_code != 200:
            return False
        
        content_type = response.headers.get('Content-Type', '').lower()
        if any(t in content_type for t in ['xml', 'rss', 'atom']):
            return True
    except:
        return False
    finally:
        if close_session:
            await session.close()

def normalize_url(url):
    """Normalize URL to base domain - ALWAYS removes trailing slash"""
    if not url:
        return url
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    parsed = urlparse(url)
    # Remove trailing slash from netloc if present
    netloc = parsed.netloc.rstrip('/')
    base_url = f"{parsed.scheme}://{netloc}"
    return base_url


def normalize_feed_url(feed_url):
    """Normalize a single feed URL"""
    if not feed_url or not isinstance(feed_url, str):
        return None
    
    feed_url = feed_url.strip()

    if not feed_url:
        return None
    
    if not feed_url.startswith(('http://','https://')):
        feed_url = "https://" + feed_url

    parsed = urlparse(feed_url)

    path = parsed.path.rstrip('/') if parsed.path else ''

    normalized = f"{parsed.scheme}://{parsed.netloc}{path}"

    if parsed.query:
        normalized += f"?{parsed.query}"

    return normalized


def normalize_feed_list(rss_string):
    """
    Normalize a semicolon-separated list of RSS feed URLs
    
    Args:
        rss_string: String like "url1; url2; url3" or "Not found"
    
    Returns:
        List of normalized, unique feed URLs (sorted)
    """
    if not rss_string or rss_string == "Not found":
        return []
    
    # Split by semicolon
    urls = rss_string.split(';')
    
    # Normalize each URL
    normalized_urls = []
    seen = set()
    
    for url in urls:
        # Normalize
        normalized = normalize_feed_url(url)
        
        # Skip if invalid or duplicate
        if normalized and normalized not in seen:
            normalized_urls.append(normalized)
            seen.add(normalized)
    
    # Sort for consistency
    return sorted(normalized_urls)

    

def get_headers():
    return {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


async def create_db_pool(db_host, db_port, db_name, db_user, db_password):
    return await asyncpg.create_pool(
        user=db_user,
        password=db_password,
        database=db_name,
        host=db_host,
        port=db_port,
        min_size=1,
        max_size=5
    )


async def init_db_schema(pool):
    create_table_sql = """
        CREATE TABLE IF NOT EXISTS rss_feeds (
            id SERIAL PRIMARY KEY,
            website_url VARCHAR(500) UNIQUE NOT NULL,
            feed_urls TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """

    create_index_sql = """
        CREATE INDEX IF NOT EXISTS idx_rss_feeds_website_url
        ON rss_feeds(website_url);
    """

    async with pool.acquire() as conn:
        await conn.execute(create_table_sql)
        await conn.execute(create_index_sql)


async def save_website_result(pool, website_url, rss_string):
    """
    rss_string: 'url1; url2; url3' or 'Not found'
    """
    website_url = normalize_url(website_url)

    new_list = normalize_feed_list(rss_string)
    new_count = len(new_list)

    new_feed_string = "; ".join(new_list) if new_list else None

    async with pool.acquire() as conn:
        async with conn.transaction():

            old_row = await conn.fetchrow(
                "SELECT feed_urls FROM rss_feeds WHERE website_url = $1;",
                website_url
            )

            if old_row:
                old_feed_string = old_row["feed_urls"]

                if old_feed_string:
                    old_list = [u.strip() for u in old_feed_string.split(";") if u.strip()]
                else:
                    old_list = []

                old_count = len(old_list)

                if new_count <= old_count:
                    print(f"Skipping update for {website_url} - existing ({old_count}) >= new({new_count})")
                    return  # ← ADDED: Actually skip the update
                
                print(f"Updating {website_url} - new feed count ({new_count}) > old ({old_count})")

            await conn.execute(
                """
                INSERT INTO rss_feeds (website_url, feed_urls)
                VALUES ($1, $2)
                ON CONFLICT (website_url)
                DO UPDATE SET feed_urls = EXCLUDED.feed_urls;
                """,
                website_url, new_feed_string
            )


async def save_batch_results(pool, results):
    for item in results:
        await save_website_result(pool, item["website"], item["rss"])


async def cleanup_duplicates(pool):
    """
    Remove duplicate entries, keeping the one with most feed URLs.
    Run this once to clean existing data.
    """
    async with pool.acquire() as conn:
        # Find duplicates (URLs that differ only by trailing slash)
        duplicates_sql = """
        WITH normalized AS (
            SELECT 
                id,
                website_url,
                feed_urls,
                REGEXP_REPLACE(website_url, '/$', '') as normalized_url,
                ARRAY_LENGTH(STRING_TO_ARRAY(feed_urls, ';'), 1) as feed_count
            FROM rss_feeds
            WHERE feed_urls IS NOT NULL
        )
        SELECT 
            normalized_url,
            ARRAY_AGG(id ORDER BY feed_count DESC NULLS LAST, id) as ids
        FROM normalized
        GROUP BY normalized_url
        HAVING COUNT(*) > 1;
        """
        
        duplicates = await conn.fetch(duplicates_sql)
        
        for record in duplicates:
            ids_to_delete = record['ids'][1:]  # Keep first (most feeds), delete rest
            if ids_to_delete:
                await conn.execute(
                    "DELETE FROM rss_feeds WHERE id = ANY($1);",
                    ids_to_delete
                )
                print(f"Cleaned up {len(ids_to_delete)} duplicate(s) for {record['normalized_url']}")