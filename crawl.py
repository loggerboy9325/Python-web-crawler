import asyncio
import sys
from urllib.parse import urljoin, urlsplit

import aiohttp
import requests
from bs4 import BeautifulSoup, Tag


def normalize_url(url: str):
    result = urlsplit(url)
    return result.netloc.lower() + result.path.lower().rstrip("/")


def get_heading_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    heading2 = soup.find("h2")
    if heading != None:
        return heading.get_text(strip=True)
    else:
        if heading2 != None:
            return heading2.get_text(strip=True)
        return ""


def get_first_paragraph_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main")

    if isinstance(main, Tag):
        paragraph = main.find("p")
    else:
        paragraph = soup.find("p")

    if isinstance(paragraph, Tag):
        return paragraph.get_text(strip=True)
    return ""


def get_urls_from_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    a_tags = soup.find_all("a")
    urls = []
    for anchor in a_tags:
        href = anchor.get("href")

        if href is not None:
            urls.append(urljoin(base_url, href))
    return urls


def get_images_from_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    img_tags = soup.find_all("img")
    imgs = []

    for anchor in img_tags:
        src = anchor.get("src")

        if src is not None:
            imgs.append(urljoin(base_url, src))
    return imgs


def extract_page_data(html: str, page_url: str):
    heading = get_heading_from_html(html)
    url = page_url
    first_paragraph = get_first_paragraph_from_html(html)
    outgoing_links = get_urls_from_html(html, page_url)
    image_urls = get_images_from_html(html, page_url)

    return {
        "url": url,
        "heading": heading,
        "first_paragraph": first_paragraph,
        "outgoing_links": outgoing_links,
        "image_urls": image_urls,
    }


def get_html(url):
    headers = {"user-agent": "my-app/0.0.1"}
    r = requests.get(url, headers=headers)
    header = r.headers["Content-Type"]
    if not header.startswith("text/html"):
        raise Exception(f"header = {header}")
    r.raise_for_status()
    return r.text


def crawl_page(base_url, current_url=None, page_data=None):
    if current_url is None:
        current_url = base_url
    if page_data is None:
        page_data = {}
    base = urlsplit(base_url)
    current = urlsplit(current_url)
    normal_url = normalize_url(current_url)

    if base.netloc != current.netloc:
        return page_data

    if normal_url in page_data:
        return page_data

    print(f"crawling {current_url}")
    try:
        html = get_html(current_url)
    except Exception as e:
        print(f"Error fetching {current_url}: {e}")
        return page_data

    extracted = extract_page_data(html, current_url)
    page_data[normal_url] = extracted

    for next_url in extracted["outgoing_links"]:
        page_data = crawl_page(base_url, next_url, page_data)
    return page_data


class AsyncCrawler:
    def __init__(self, base_url):
        self.base_url = base_url
        self.base_domain = urlsplit(base_url).netloc
        self.page_data = {}
        self.visited = set()
        self.lock = asyncio.Lock()
        self.max_concurrency = int(sys.argv[2])
        self.semaphore = asyncio.Semaphore(self.max_concurrency)
        self.session = None
        self.max_pages = sys.argv[3]
        self.should_stop = False
        self.all_tasks = set()

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    async def add_page_visit(self, normalized_url):

        async with self.lock:
            if self.should_stop == True:
                return False
            if len(self.visited) >= int(self.max_pages):
                self.should_stop = True
                print("Reached maximum number of pages to crawl.")
                return False

            if normalized_url in self.visited:
                return False
            else:
                self.visited.add(normalized_url)
                return True

    async def get_html(self, url):
        async with self.session.get(url) as response:
            if response.status > 399:
                raise RuntimeError("Not expecting error code over 399")
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                raise RuntimeError("content-type header is invalid")
            return await response.text()

    async def crawl_page(self, current_url):
        if self.should_stop == True:
            return
        url_obj = urlsplit(current_url)
        if url_obj.netloc != self.base_domain:
            return
        normal_url = normalize_url(current_url)
        is_new = await self.add_page_visit(normal_url)
        if not is_new:
            return
        async with self.semaphore:
            html = await self.get_html(current_url)
            print(current_url)
            if html is None:
                return
            page_info = extract_page_data(html, current_url)
            async with self.lock:
                self.page_data[normal_url] = page_info
        tasks = []
        for next_url in page_info["outgoing_links"]:
            task = asyncio.create_task(self.crawl_page(next_url))
            tasks.append(task)
            self.all_tasks.add(task)
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                self.all_tasks.discard(task)

    async def crawl(self):
        await self.crawl_page(self.base_url)
        return self.page_data


async def crawl_site_async(base_url):
    async with AsyncCrawler(base_url) as crawler:
        return await crawler.crawl()
