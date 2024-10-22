import os  # Provides functions for interacting with the operating system
import json  # For JSON serialization and deserialization

from urllib.parse import urlparse, urljoin  # For URL parsing and manipulation

import scrapy  # Scrapy framework for web crawling
from scrapy.http.response.text import TextResponse  # To check if the response is a text response
from scrapy.spidermiddlewares.httperror import HttpError  # For handling HTTP errors in Scrapy
from twisted.internet.error import DNSLookupError, TCPTimedOutError, TimeoutError  # For handling network errors
from scrapy.linkextractors import LinkExtractor  # To extract links from web pages

class LinksSpider(scrapy.Spider):
    name = ""  # Name of the spider

    # Starting URLs for the spider to crawl
    start_urls = [""]
    
    # Domains considered as internal links
    search_domains = [
        "",
    ]

    def start_requests(self):
        """
        Initializes the crawling by sending requests to the start URLs.
        Attaches metadata and error handling to each request.
        """
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                self.parse,  # Callback method to handle the response
                errback=self.handle_error,  # Method to handle errors
                meta={"origin": f"start_{url}"}  # Metadata to track the origin of the request
            )

    def parse(self, response):
        """
        Parses the response from each request.
        Extracts links and handles them based on whether they are internal or external.
        """
        request = response.request
        origin = urlparse(request.url).path  # Extracts the path from the request URL
        self.save_scraped_page(request.url)  # Saves the URL of the successfully scraped page

        if not isinstance(response, TextResponse) and response.status != 200:
            # If the response is not a text response and the status is not 200, log an error
            self.save_error_to_json(
                request.url,
                f"status {response.status}",
                request.meta["origin"]
            )
            yield None  # Stop processing this response
        else:
            # Extract all internal and external links from the page
            internal_links = LinkExtractor(allow_domains=self.search_domains).extract_links(response)
            external_links = LinkExtractor(deny_domains=self.search_domains).extract_links(response)

            # Process external links
            for link in external_links:
                yield scrapy.Request(
                    link.url,
                    callback=self.NO_CALLBACK,  # No processing needed for external links
                    errback=self.handle_error,
                    meta={"origin": origin}
                )

            # Process internal links
            for link in internal_links:
                link_url = link.url
                # Skip specific URLs that match a hardcoded pattern (to avoid thousands of bot-generated links)
                if not link_url.startswith(""):
                    yield scrapy.Request(
                        link_url,
                        callback=self.parse,  # Recursively parse the internal link
                        errback=self.handle_error,
                        meta={"origin": origin}
                    )

    def NO_CALLBACK(self, response):
        """
        Placeholder method for external links; does nothing with the response.
        """
        pass

    def handle_error(self, failure):
        """
        Handles errors that occur during requests.
        Logs different types of errors to JSON files.
        """
        request = failure.request
        origin = request.meta["origin"]  # Retrieves the origin from the request metadata

        if failure.check(HttpError):
            # Handles HTTP errors (e.g., 404, 500)
            response = failure.value.response
            self.save_error_to_json(
                request.url,
                f"error {response.status}",
                origin
            )
        elif failure.check(DNSLookupError):
            # Handles DNS lookup errors
            self.save_error_to_json(
                request.url,
                "error DNSLookupError",
                origin
            )
        elif failure.check(TCPTimedOutError, TimeoutError):
            # Handles timeout errors
            self.save_error_to_json(
                request.url,
                "error TimeoutError",
                origin
            )

    def save_to_json(self, data, filepath):
        """
        Saves data to a JSON file, appending each entry as a new line.
        """
        with open(filepath, 'a') as f:
            json.dump(data, f)
            f.write('\n')

    def save_scraped_page(self, page_url):
        """
        Logs the URL of a successfully scraped page.
        """
        data = {"url": page_url}
        filename = "scraped_pages.json"  # Name of the file to store scraped page URLs
        filepath = os.path.join('reports', filename)  # Path to the reports directory
        self.save_to_json(data, filepath)

    def save_error_to_json(self, url, status, origin):
        """
        Logs error information to a JSON file named after the origin of the request.
        """
        data = {"link": url, "status": status}
        # Formats the filename by replacing slashes with double underscores
        filename = origin.replace("/", "__") + '.json'
        filepath = os.path.join('reports', filename)
        self.save_to_json(data, filepath)
