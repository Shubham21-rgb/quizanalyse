"""
LLM-Powered Web Scraping Agent
Intelligently scrapes static and dynamic web pages
"""

import asyncio
import json
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from requests_html import AsyncHTMLSession


class WebScraper:
    """
    Intelligent web scraper that detects and handles both static and dynamic pages
    """
    
    def __init__(self, timeout: int = 30000):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def _is_likely_dynamic(self, html: str) -> bool:
        """
        Heuristic to detect if a page is likely JavaScript-rendered
        """
        indicators = [
            # React/Vue/Angular indicators
            r'<div[^>]+id=["\']root["\']',
            r'<div[^>]+id=["\']app["\']',
            r'react',
            r'vue',
            r'angular',
            # SPA frameworks
            r'__NEXT_DATA__',
            r'__NUXT__',
            # Very little content in body
            len(re.findall(r'<p[^>]*>.*?</p>', html, re.DOTALL)) < 3,
        ]
        
        dynamic_score = 0
        for indicator in indicators[:-1]:
            if re.search(indicator, html, re.IGNORECASE):
                dynamic_score += 1
        
        # Check if body has minimal content
        soup = BeautifulSoup(html, 'html.parser')
        body = soup.find('body')
        if body:
            text_length = len(body.get_text(strip=True))
            if text_length < 100:
                dynamic_score += 2
                
        return dynamic_score >= 2
    
    async def _fetch_static(self, url: str) -> Dict[str, Any]:
        """
        Fetch static page using standard HTTP request
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return {
                'success': True,
                'html': response.text,
                'status_code': response.status_code,
                'method': 'static'
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'method': 'static'
            }
    
    async def _fetch_dynamic(self, url: str) -> Dict[str, Any]:
        """
        Fetch dynamic page using requests-html (lighter than Playwright)
        """
        try:
            session = AsyncHTMLSession()
            response = await session.get(url)
            
            # Render JavaScript (downloads Chromium on first run, but lighter than Playwright)
            await response.html.arender(timeout=30, sleep=2)
            
            html = response.html.html
            await session.close()
            
            return {
                'success': True,
                'html': html,
                'status_code': response.status_code,
                'method': 'dynamic'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'method': 'dynamic'
            }
    
    def _extract_data(self, html: str, url: str) -> Dict[str, Any]:
        """
        Extract and parse relevant information from HTML
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style tags
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()
        
        # Extract metadata
        title = soup.find('title')
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        
        # Extract all text content
        text_content = soup.get_text(separator='\n', strip=True)
        
        # Extract all links
        links = []
        for link in soup.find_all('a', href=True):
            links.append({
                'text': link.get_text(strip=True),
                'href': link['href']
            })
        
        # Extract images
        images = []
        for img in soup.find_all('img', src=True):
            images.append({
                'alt': img.get('alt', ''),
                'src': img['src']
            })
        
        # Extract headings
        headings = []
        for i in range(1, 7):
            for heading in soup.find_all(f'h{i}'):
                headings.append({
                    'level': i,
                    'text': heading.get_text(strip=True)
                })
        
        # Extract structured data (JSON-LD)
        structured_data = []
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                structured_data.append(json.loads(script.string))
            except:
                pass
        
        # Extract tables
        tables = []
        for table_idx, table in enumerate(soup.find_all('table')):
            table_data = {
                'table_index': table_idx + 1,
                'headers': [],
                'rows': [],
                'caption': None
            }
            
            # Get table caption if exists
            caption = table.find('caption')
            if caption:
                table_data['caption'] = caption.get_text(strip=True)
            
            # Extract headers
            headers = []
            header_row = table.find('thead')
            if header_row:
                for th in header_row.find_all('th'):
                    headers.append(th.get_text(strip=True))
            else:
                # Try to find headers in first row
                first_row = table.find('tr')
                if first_row:
                    for th in first_row.find_all('th'):
                        headers.append(th.get_text(strip=True))
            
            table_data['headers'] = headers
            
            # Extract rows
            tbody = table.find('tbody') if table.find('tbody') else table
            for row in tbody.find_all('tr'):
                cells = []
                for cell in row.find_all(['td', 'th']):
                    cells.append(cell.get_text(strip=True))
                if cells:  # Only add non-empty rows
                    table_data['rows'].append(cells)
            
            # Only add table if it has content
            if table_data['rows'] or table_data['headers']:
                tables.append(table_data)
        
        return {
            'url': url,
            'title': title.get_text(strip=True) if title else None,
            'meta_description': meta_desc['content'] if meta_desc else None,
            'text_content': text_content,
            'links': links[:50],  # Limit to first 50 links
            'images': images[:20],  # Limit to first 20 images
            'headings': headings,
            'tables': tables,  # NEW: Table data
            'structured_data': structured_data,
            'html_length': len(html)
        }
    
    async def scrape(self, url: str, force_dynamic: bool = False) -> Dict[str, Any]:
        """
        Main scraping method that intelligently chooses static or dynamic approach
        """
        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return {
                    'success': False,
                    'error': 'Invalid URL format'
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'URL parsing error: {str(e)}'
            }
        
        # If force_dynamic is True, use dynamic rendering directly
        if force_dynamic:
            dynamic_result = await self._fetch_dynamic(url)
            
            if not dynamic_result['success']:
                return {
                    'success': False,
                    'error': dynamic_result['error'],
                    'method': dynamic_result['method']
                }
            
            extracted = self._extract_data(dynamic_result['html'], url)
            return {
                'success': True,
                'method': 'dynamic',
                'data': extracted
            }
        
        # Otherwise, try static fetch first
        static_result = await self._fetch_static(url)
        
        if static_result['success']:
            # Check if page is likely dynamic
            is_dynamic = self._is_likely_dynamic(static_result['html'])
            
            if not is_dynamic:
                # Page is static, use the fetched HTML
                extracted = self._extract_data(static_result['html'], url)
                return {
                    'success': True,
                    'method': 'static',
                    'data': extracted
                }
            else:
                # Page seems dynamic, try dynamic rendering
                dynamic_result = await self._fetch_dynamic(url)
                
                if dynamic_result['success']:
                    extracted = self._extract_data(dynamic_result['html'], url)
                    return {
                        'success': True,
                        'method': 'dynamic',
                        'data': extracted
                    }
                else:
                    # Dynamic failed, fallback to static result
                    extracted = self._extract_data(static_result['html'], url)
                    return {
                        'success': True,
                        'method': 'static (fallback)',
                        'data': extracted
                    }
        
        # Static fetch failed
        return {
            'success': False,
            'error': static_result['error'],
            'method': 'static'
        }


class LLMScraperHandler:
    """
    Handler interface for LLM to interact with the scraper
    """
    
    def __init__(self):
        self.scraper = WebScraper()
    
    def format_as_markdown(self, result: Dict[str, Any]) -> str:
        """
        Convert scraping result to Markdown format
        """
        if not result.get('success'):
            return f"# Scraping Failed\n\n**Error:** {result.get('error', 'Unknown error')}\n"
        
        data = result['data']
        md = []
        
        # Header
        md.append(f"# Web Scraping Report\n")
        md.append(f"**URL:** {data['url']}\n")
        md.append(f"**Method:** {result['method']}\n")
        if data['title']:
            md.append(f"**Title:** {data['title']}\n")
        if data['meta_description']:
            md.append(f"**Description:** {data['meta_description']}\n")
        md.append("\n---\n")
        
        # Statistics
        md.append(f"## 📈 Statistics\n")
        md.append(f"- **Total Links:** {len(data['links'])}")
        md.append(f"- **Total Images:** {len(data['images'])}")
        md.append(f"- **Total Headings:** {len(data['headings'])}")
        md.append(f"- **Total Tables:** {len(data['tables'])}")
        md.append(f"- **HTML Length:** {data['html_length']:,} characters")
        md.append(f"- **Text Content Length:** {len(data['text_content']):,} characters\n")
        md.append("\n---\n")
        
        # Headings
        if data['headings']:
            md.append(f"## 📋 Headings ({len(data['headings'])})\n")
            for i, heading in enumerate(data['headings'], 1):
                md.append(f"{i}. **H{heading['level']}:** {heading['text']}")
            md.append("\n---\n")
        
        # Links
        if data['links']:
            md.append(f"## 🔗 Links ({len(data['links'])})\n")
            for i, link in enumerate(data['links'], 1):
                link_text = link['text'] if link['text'] else '[No text]'
                md.append(f"{i}. [{link_text}]({link['href']})")
            md.append("\n---\n")
        
        # Images
        if data['images']:
            md.append(f"## 🖼️ Images ({len(data['images'])})\n")
            for i, img in enumerate(data['images'], 1):
                alt_text = img['alt'] if img['alt'] else '[No alt text]'
                md.append(f"{i}. **Alt:** {alt_text}")
                md.append(f"   **Src:** {img['src']}")
            md.append("\n---\n")
        
        # Tables
        if data['tables']:
            md.append(f"## 📊 Tables ({len(data['tables'])})\n")
            for table in data['tables']:
                md.append(f"\n### Table #{table['table_index']}")
                if table['caption']:
                    md.append(f"**Caption:** {table['caption']}\n")
                
                if table['headers'] and table['rows']:
                    # Create markdown table
                    md.append("| " + " | ".join(table['headers']) + " |")
                    md.append("|" + "|".join(["---" for _ in table['headers']]) + "|")
                    for row in table['rows']:
                        # Ensure row has same length as headers
                        padded_row = row + [''] * (len(table['headers']) - len(row))
                        md.append("| " + " | ".join(padded_row[:len(table['headers'])]) + " |")
                elif table['rows']:
                    # No headers, just rows
                    for i, row in enumerate(table['rows'], 1):
                        md.append(f"**Row {i}:** {' | '.join(row)}")
                md.append("")
            md.append("\n---\n")
        
        # Structured Data
        if data['structured_data']:
            md.append(f"## 📊 Structured Data\n")
            md.append("```json")
            md.append(json.dumps(data['structured_data'], indent=2))
            md.append("```\n")
            md.append("\n---\n")
        
        # Text Content
        md.append(f"## 📄 Text Content\n")
        text_preview = data['text_content'][:5000]
        if len(data['text_content']) > 5000:
            text_preview += "\n\n... (truncated)"
        md.append("```")
        md.append(text_preview)
        md.append("```\n")
        
        return "\n".join(md)
        
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main handler method for LLM interaction
        
        Expected input format:
        {
            "url": "https://example.com",
            "force_dynamic": false  # Optional
        }
        """
        if 'url' not in request:
            return {
                'success': False,
                'error': 'Missing required field: url'
            }
        
        url = request['url']
        force_dynamic = request.get('force_dynamic', False)
        
        result = await self.scraper.scrape(url, force_dynamic=force_dynamic)
        
        return result
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return information about scraper capabilities for LLM
        """
        return {
            'description': 'Web scraping agent that can fetch and parse both static and dynamic web pages',
            'features': [
                'Automatic detection of static vs dynamic pages',
                'Headless browser support for JavaScript-rendered content',
                'Extraction of text, links, images, headings, tables, and structured data',
                'Metadata extraction (title, description)',
                'Support for JSON-LD structured data',
                'Table extraction with headers and rows'
            ],
            'input_format': {
                'url': 'string (required) - The URL to scrape',
                'force_dynamic': 'boolean (optional) - Force use of headless browser'
            },
            'output_format': {
                'success': 'boolean - Whether scraping succeeded',
                'method': 'string - "static" or "dynamic"',
                'data': 'object - Extracted data including title, content, links, etc.',
                'error': 'string - Error message if success is false'
            }
        }


# Example usage
async def main():
    handler = LLMScraperHandler()
    
    # Example request
    request = {
        "url": "http://localhost:5500/demol.html",
        "force_dynamic": True  # Set to True to force dynamic rendering with JS
    }
    
    print("Scraper Capabilities:")
    print(json.dumps(handler.get_capabilities(), indent=2))
    print("\n" + "="*50 + "\n")
    
    print(f"Scraping: {request['url']}")
    result = await handler.handle_request(request)
    
    # Generate Markdown output
    markdown_output = handler.format_as_markdown(result)
    
    # Save to question.md file
    output_file = "question.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown_output)
    
    print(f"\n✅ Markdown report saved to: {output_file}")
    print(f"\n📄 Preview (first 1000 characters):\n")
    print(markdown_output[:1000])
    print("\n... (see question.md for full content)")


if __name__ == "__main__":
    asyncio.run(main())