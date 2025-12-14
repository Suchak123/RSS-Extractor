import asyncio
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import csv
from utils import get_headers, normalize_url, normalize_feed_url

class RSSHubParser:
    def __init__(self):
        self.headers = get_headers()

        self.hub_paths = [
            '/rss',
            '/feeds',
            '/feed-list',
            '/rss-feeds',
            '/subscribe',
            '/syndication',
            '/news/rss',
            '/blog/rss',
            '/feeds.html',
            '/rss.html',
            '/rss-feeds.html',
            '/feed',
            '/atom',
            '/rss.xml',
            '/feeds.xml'
        ]
        
    async def fetch_page(self, url, session=None):

        close_session = False
        if session is None:
            session = AsyncSession(impersonate="chrome110")
            close_session = True
        
        try:
            response = await session.get(
                url, 
                headers=self.headers, 
                timeout=15,
                verify=False
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching page: {e}")
            return None
        finally:
            if close_session:
                await session.close()

    async def discover_hub_pages(self, base_url, session):
        # Use normalized base URL
        base = normalize_url(base_url)
        
        discovered_hubs = []
        
        print(f"Searching for hub pages...")
        
        for path in self.hub_paths:
            test_url = base + path
            try:
                response = await session.get(test_url, headers=self.headers, timeout=8, verify=False)
                if response.status_code == 200:
                    
                    if await self.looks_like_hub_page(response.text):
                        discovered_hubs.append(test_url)
                        print(f"Found hub page: {test_url}")
            except:
                continue

        if not discovered_hubs:
            print(f"No hub pages")
        
        return discovered_hubs
    
    async def looks_like_hub_page(self, html_content):
        content_lower = html_content.lower()
        
        hub_indicators = [
            'rss feed',
            'subscribe to',
            'feed url',
            'syndication',
            'available feeds',
            'rss feeds',
            'atom feed',
            'news feeds',
            'feed list',
            'rss channels',
            'subscribe via rss'
        ]
        
        indicator_count = sum(1 for indicator in hub_indicators if indicator in content_lower)
        
        feed_link_count = (
            content_lower.count('.xml') + 
            content_lower.count('href="/feed') + 
            content_lower.count('href="/rss') +
            content_lower.count('atom.xml')
        )
        
        is_hub = indicator_count >= 2 or feed_link_count >= 3
        
        return is_hub
    
    def is_feed_url(self, url):
        if not url:
            return False
        
        feed_patterns = [
            r'\.rss$',
            r'\.xml$',
            r'\.atom$',
            r'/rss/',
            r'/feed/',
            r'/feeds/',
            r'/atom/',
            r'/rss$',
            r'/feed$',
            r'/atom$',
            r'rss\.xml',
            r'feed\.xml',
            r'atom\.xml'
        ]
        
        url_lower = url.lower()
        return any(re.search(pattern, url_lower) for pattern in feed_patterns)
    
    def extract_category(self, link_element):

        category = "General"
        
        parent_li = link_element.find_parent('li')
        if parent_li:
            for heading_tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                heading = parent_li.find_previous_sibling(heading_tag)
                if not heading:
                    heading = parent_li.find_previous(heading_tag)
                if heading and heading.text.strip():
                    category = heading.text.strip()
                    return category
        
        for parent in link_element.parents:
            for i in range(1, 7):
                heading = parent.find_previous(f'h{i}')
                if heading and heading.text.strip():
                    category = heading.text.strip()
                    return category
            
            if parent.name in ['section', 'div', 'article']:
                if parent.get('class'):
                    class_name = ' '.join(parent.get('class'))
                    if any(word in class_name.lower() for word in ['category', 'section', 'topic', 'group']):
                        for cls in parent.get('class'):
                            if any(word in cls.lower() for word in ['category', 'section', 'topic']):
                                category = cls.replace('-', ' ').replace('_', ' ').title()
                                return category
        
        for parent in link_element.parents:
            if parent.get('data-category'):
                return parent.get('data-category')
            if parent.get('data-section'):
                return parent.get('data-section')
        
        return category
    
    def extract_title(self, link):
        title = link.text.strip()
        if title and len(title) > 2:
            return title
        
        title = link.get('title', '').strip()
        if title and len(title) > 2:
            return title
        
        title = link.get('aria-label', '').strip()
        if title and len(title) > 2:
            return title
        
        if link.parent:
            parent_text = link.parent.get_text(strip=True)
            if parent_text and len(parent_text) < 100:
                return parent_text
        
        url = link.get('href', '')
        if url:
            parts = url.split('/')
            for part in reversed(parts):
                if part and not part.endswith(('.xml', '.rss', '.atom')):
                    clean = part.replace('-', ' ').replace('_', ' ').title()
                    if len(clean) > 2:
                        return clean
        
        return "Untitled Feed"
    
    async def parse_feeds(self, hub_url, session=None):
        base_url = normalize_url(hub_url)
        
        content = await self.fetch_page(hub_url, session)
        if not content:
            print(f" Could not fetch hub page")
            return []
        
        soup = BeautifulSoup(content, 'lxml')
        seen_urls = set()
        feeds = []
        
        link_tags = soup.find_all('link', type=['application/rss+xml', 'application/atom+xml'])
        for link_tag in link_tags:
            href = link_tag.get('href')
            if href:
                full_url = urljoin(base_url, href)
                # Normalize feed URL before adding
                normalized_url = normalize_feed_url(full_url)
                if normalized_url and normalized_url not in seen_urls:
                    seen_urls.add(normalized_url)
                    title = link_tag.get('title', self.extract_title_from_url(normalized_url))
                    feeds.append({
                        'category': 'General',
                        'title': title,
                        'url': normalized_url
                    })
        
        all_links = soup.find_all('a', href=True)
        print(f"    → Found {len(all_links)} total links on page")
            
        for link in all_links:
            href = link.get('href')
            
            if not self.is_feed_url(href):
                continue
            
            full_url = urljoin(base_url, href)
            normalized_url = normalize_feed_url(full_url)
            
            if not normalized_url or normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            
            title = self.extract_title(link)
            category = self.extract_category(link)
            
            feeds.append({
                'category': category,
                'title': title,
                'url': normalized_url
            })

        print(f"Extracted {len(feeds)} feed URLs")
        

        if feeds and len(feeds) <= 5:
            print(f"Feeds found:")
            for feed in feeds[:5]:
                print(f"{feed['title']}: {feed['url']}")
        
        return feeds
    
    async def validate_feeds(self, feeds, session):
        print(f"Validating {len(feeds)} feeds...")
        
        async def check_feed(feed):
            try:
                response = await session.get(
                    feed['url'],
                    headers=self.headers,
                    timeout=5,
                    verify=False
                )
                
                if response.status_code != 200:
                    return None
                
                content_type = response.headers.get('Content-Type', '').lower()
                if any(t in content_type for t in ['xml', 'rss', 'atom']):
                    return feed
                
                text = response.text[:500].lower()
                if any(marker in text for marker in ['<rss', '<feed', '<?xml', '<atom']):
                    return feed
                
                return None
            except:
                return None
        
        semaphore = asyncio.Semaphore(10)
        
        async def validate_with_limit(feed):
            async with semaphore:
                return await check_feed(feed)
        
        tasks = [validate_with_limit(feed) for feed in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_feeds = [f for f in results if f is not None and isinstance(f, dict)]
        print(f"{len(valid_feeds)} feeds validated successfully")
        
        return valid_feeds
    
    @staticmethod
    def display_feeds(feeds):
        if not feeds:
            print("No feeds found!")
            return
        
        feeds.sort(key=lambda x: (x['category'], x['title']))
        
        print(f"Found {len(feeds)} RSS/Atom feeds")
        
        current_category = None
        for feed in feeds:
            if feed['category'] != current_category:
                current_category = feed['category']
                print(f"\n[{current_category}]")
            
            print(f"{feed['title']}")
            print(f"{feed['url']}")

    async def is_hub_page_url(self, url):
        url_lower = url.lower()
        hub_patterns = ['/rss', '/feeds', '/feed-list', '/subscribe', '/syndication']
        return any(pattern in url_lower for pattern in hub_patterns)
    
    def extract_title_from_url(self, url):
        """Extract a title from a feed URL"""
        parts = url.split('/')
        for part in reversed(parts):
            if part and not part.endswith(('.xml', '.rss', '.atom')):
                clean = part.replace('-', ' ').replace('_', ' ').title()
                if len(clean) > 2:
                    return clean
        return "RSS Feed"