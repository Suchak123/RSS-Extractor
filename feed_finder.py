import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from utils import detect_cms, get_cms_feed_paths, get_headers, normalize_url, normalize_feed_url

class FeedFinder:
    def __init__(self):
        self.headers = get_headers()
    
    async def find_feeds(self, url, session):
        """Find all RSS/Atom feeds for a given URL"""
        try:
            response = await session.get(
                url, 
                headers=self.headers, 
                timeout=10,
                verify=False
            )
            response.raise_for_status()
            html_text = response.text
        except Exception as e:
            print(f"Failed to fetch {url}: {str(e)}")
            return []

        soup = BeautifulSoup(html_text, 'html.parser')
        base_url = normalize_url(url)
        parsed = urlparse(url)

        cms = detect_cms(soup, html_text)
        if cms:
            print(f"Detected CMS: {cms}")

        results = await asyncio.gather(
            self._try_cms_paths(base_url, cms, session) if cms else self._return_empty(),
            self._extract_from_link_tags(url, soup, session),
            self._extract_from_anchor_tags(url, soup, session),
            self._try_common_paths(base_url, session),
            self._try_nested_paths(base_url, parsed, session),
            return_exceptions=True
        )

        feeds = []
        seen = set()
        
        for result in results:
            if isinstance(result, list):
                for feed_url in result:
                    normalized = normalize_feed_url(feed_url)
                    if normalized and normalized not in seen:
                        feeds.append(normalized)
                        seen.add(normalized)
            elif isinstance(result, Exception):
                pass
        
        return feeds
    
    async def _return_empty(self):
        return []
    
    async def _try_cms_paths(self, base_url, cms, session):
        cms_paths = get_cms_feed_paths(cms)
        
        tasks = []
        urls = []
        for path in cms_paths:
            test_url = base_url + path
            urls.append(test_url)
            tasks.append(self._check_feed(test_url, session))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [url for url, is_feed in zip(urls, results) if is_feed is True]
    
    async def _extract_from_link_tags(self, url, soup, session):
        """Extract feeds from <link> tags in HTML head"""
        link_tags = soup.find_all('link', type=['application/rss+xml', 'application/atom+xml'])
        
        tasks = []
        urls = []
        for tag in link_tags:
            href = tag.get('href')
            if href:
                full = urljoin(url, href)
                urls.append(full)
                tasks.append(self._check_feed(full, session))
        
        if not tasks:
            return []
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [url for url, is_feed in zip(urls, results) if is_feed is True]
    
    async def _extract_from_anchor_tags(self, url, soup, session):
        """Extract feeds from <a> tags that look like feed links"""
        candidate_urls = []
        seen = set()
        
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if any(x in href for x in ['rss', 'feed', 'xml', 'atom']):
                full = urljoin(url, a['href'])
                if full not in seen:
                    candidate_urls.append(full)
                    seen.add(full)
        
        candidate_urls = candidate_urls[:30]
        
        if not candidate_urls:
            return []
        
        tasks = [self._check_feed(feed_url, session) for feed_url in candidate_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [url for url, is_feed in zip(candidate_urls, results) if is_feed is True]
    
    async def _try_common_paths(self, base_url, session):
        common_paths = [
            '/rss',
            '/feed',
            '/rss.xml',
            '/feed.xml',
            '/atom.xml',
            '/index.xml',
            '/feeds',
            '/blog/feed',
            '/rss-feed',
            '/site/rss',
            '/site/feed',
            '/syndication',
            '/feed/rss',
            '/atom',
            '/news/rss',
            '/blog/rss'
        ]
        
        tasks = []
        urls = []
        for path in common_paths:
            test_url = base_url + path
            urls.append(test_url)
            tasks.append(self._check_feed(test_url, session))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [url for url, is_feed in zip(urls, results) if is_feed is True]
    
    async def _try_nested_paths(self, base_url, parsed, session):
        if not parsed.path or not parsed.path.strip('/'):
            return []
        
        nested_paths = ['/feed', '/feed.xml', '/rss', '/rss.xml', '/atom.xml']
        tasks = []
        urls = []
        
        for sub in nested_paths:
            test_url = base_url + parsed.path.rstrip('/') + sub
            urls.append(test_url)
            tasks.append(self._check_feed(test_url, session))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [url for url, is_feed in zip(urls, results) if is_feed is True]
    
    async def _check_feed(self, url, session):
        """Check if a URL is a valid RSS/Atom feed"""
        try:
            response = await session.get(
                url, 
                headers=self.headers, 
                timeout=5,
                verify=False,
                allow_redirects=True
            )
            
            if response.status_code != 200:
                return False
            
            content_type = response.headers.get('Content-Type', '').lower()
            if any(t in content_type for t in ['xml', 'rss', 'atom']):
                return True
            
            text = response.text[:500].lower()  
            return any(marker in text for marker in ['<rss', '<feed', '<?xml', '<atom'])
            
        except asyncio.TimeoutError:
            return False
        except Exception:
            return False