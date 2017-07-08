#-*- coding:utf-8 -*-
import re
import urllib2
import urlparse
import itertools
import robotparser
from datetime import datetime
import Queue

class Throttle(object):
    """Throttle downloading by sleeping between requests to same domain

    """
    def __init__(self, delay):
        self.delay = delay
        self.domains = {}

    def wait(self, url):
        domain = urlparse.urlparse(url).netloc
        last_accessed = self.domains.get(domain)

        if self.delay > 0 and last_accessed is not None:
            sleep_secs = self.delay - (datetime.now() - last_accessed).seconds
            if sleep_secs > 0:
                time.sleep(sleep_secs)
        self.domains[domain] = datetime.now()

def download(url, headers, proxy, num_retries, data=None):
    print("Downloading: {}".format(url))
    request = urllib2.Request(url, data, headers)
    opener = urllib2.build_opener()
    if proxy:
        proxy_params = {urlparse.urlparse(url).scheme: proxy}
        opener.add_handler(urllib2.ProxyHandler(proxy_params))

    try:
        response = opener.open(request)
        html = response.read()
        code = response.code
    except urllib2.URLError as e:
        print("Download error: {}".format(e.reason))
        html = ""
        if hasattr(e, 'code'):
            code = e.code
            if num_retries > 0 and 500 <= e.code < 600:
                return download(url, headers, proxy, num_retries - 1, data)
        else:
            code = None
    return html

def crawl_sitemap(url):
    #download the sitemap file
    sitemap = download(url)
    #extract the sitemap links
    print("{}".format(sitemap))
    links = re.findall('<loc>(.*?)</loc>', sitemap)
    #download each link
    for link in links:
        print("link: {}".format(link))
        html = download(link)

def crawl_num(url_prefix):
    # maximum number of consecutive download errors allowed
    max_errors = 5
    # current number of consecutive download errors
    num_errors = 0

    for page in itertools.count(1):
        url = "{}/{}".format(url_prefix, page)
        print("url: {}".format(url))
        html = download(url)
        if html is None:
            # received an error trying to download this webpage
            num_errors += 1
            if num_errors == max_errors:
                break
        else:
            #sucess - can scrape the result
            num_errors = 0

def normalize(seed_url, link):
    """Normalize this URL by removing hash and adding domain

    """
    link, _ = urlparse.urldefrag(link)
    return urlparse.urljoin(seed_url, link)

def same_domain(url1, url2):
    """Return True if both URL is belong to same domain

    """
    return urlparse.urlparse(url1).netloc == urlparse.urlparse(url2).netloc

def link_crawler(seed_url, link_regex=None, delay=5, max_depth=-1, max_urls=-1, headers=None, user_agent="wswp", proxy=None, num_retries=1):
    """Crawl from the given sedd URL following links matched by link_regex

    """
    crawl_queue = Queue.deque([seed_url])
    seen = {seed_url:0}
    num_urls = 0
    #加载robots.txt
    rp = get_robots(seed_url)
    throttle = Throttle(delay)
    headers = headers or {}
    if user_agent:
        headers["User-agent"] = user_agent

    while crawl_queue:
        url = crawl_queue.pop()
        #添加过滤条件
        if rp.can_fetch(user_agent, url):
            throttle.wait(url)
            html = download(url, headers, proxy = proxy, num_retries = num_retries)
            links = []
            
            depth = seen[url]
            if depth != max_depth:
                if link_regex:
                    links.extend(link for link in get_links(html) if re.match(link_regex, link))
            
            for link in links:
                link = normalize(seed_url, link)
                if link not in seen:
                    seen[link] = depth + 1
                    if same_domain(seed_url, link):
                        crawl_queue.append(link)
            num_urls += 1
            if num_urls == max_urls:
                break
        else:
            print("Blocked by robots.txt: {}".format(url))

def get_robots(url):
    """Initialize robots parser for this domain
    
    """
    rp = robotparser.RobotFileParser()
    rp.set_url(urlparse.urljoin(url, '/robots.txt'))
    rp.read()
    return rp

def get_links(html):
    """Return a list of links from html

    """
    # a regular expression to extract all links from the webpage
    webpage_regex = re.compile('<a[^>]+href=["\'](.*?)["\']', re.IGNORECASE)
    # list of all links from the webpage
    return webpage_regex.findall(html)

if __name__ == "__main__":
    link_crawler('http://example.webscraping.com', r'/places/default/(index|view)', delay=0, num_retries=1, user_agent='BadCrawler')
    link_crawler('http://example.webscraping.com', r'/places/default/(index|view)', delay=0, num_retries=1, max_depth=1, user_agent='GoodCrawler')
