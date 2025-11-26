"""
LLM-Powered Web Scraping Agent
Intelligently scrapes static and dynamic web pages, and handles various file types
"""

import asyncio
import json
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, urlsplit, urljoin
import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup
from requests_html import AsyncHTMLSession
import mimetypes
from concurrent.futures import ThreadPoolExecutor
import time
from functools import lru_cache


class WebScraper:
    """
    High-performance intelligent web scraper with connection pooling and retry logic
    """
    
    def __init__(self, timeout: int = 15, max_workers: int = 10):
        self.timeout = timeout
        self.max_workers = max_workers
        self.session = requests.Session()
        
        # Configure retry strategy with exponential backoff
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        # Configure connection pooling for performance
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,
            pool_maxsize=20,
            pool_block=False
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        })
        
        # Thread pool for parallel operations
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    @lru_cache(maxsize=256)
    def _detect_content_type(self, url: str, response_headers: tuple = None) -> str:
        """
        Detect content type from URL or response headers (cached for performance)
        """
        # Convert tuple back to dict if provided
        if response_headers:
            response_headers = dict(response_headers)
        # Check Content-Type header first
        if response_headers and 'content-type' in response_headers:
            content_type = response_headers['content-type'].lower()
            if 'text/html' in content_type or 'application/xhtml' in content_type:
                return 'webpage'
            elif 'application/json' in content_type:
                return 'json'
            elif 'text/csv' in content_type or 'application/csv' in content_type:
                return 'csv'
            elif 'application/pdf' in content_type:
                return 'pdf'
            elif 'image/' in content_type:
                return 'image'
            elif 'audio/' in content_type:
                return 'audio'
            elif 'video/' in content_type:
                return 'video'
            elif 'text/plain' in content_type:
                return 'text'
        
        # Fallback to URL extension
        path = urlsplit(url).path.lower()
        if path.endswith('.json'):
            return 'json'
        elif path.endswith('.csv'):
            return 'csv'
        elif path.endswith('.pdf'):
            return 'pdf'
        elif path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp')):
            return 'image'
        elif path.endswith(('.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac')):
            return 'audio'
        elif path.endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            return 'video'
        elif path.endswith('.txt'):
            return 'text'
        elif path.endswith(('.xml', '.rss')):
            return 'xml'
        
        # Default to webpage
        return 'webpage'
        
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
        Fetch static page using optimized HTTP request
        """
        try:
            # Use asyncio to not block event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                lambda: self.session.get(url, timeout=self.timeout, stream=False)
            )
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
        Fetch dynamic page using requests-html with optimized settings
        """
        session = None
        try:
            session = AsyncHTMLSession()
            response = await session.get(url, timeout=self.timeout)
            
            # Render JavaScript with optimized timeout and minimal sleep
            await response.html.arender(
                timeout=self.timeout,
                sleep=1,  # Reduced from 2 to 1 second
                keep_page=False,  # Don't keep page in memory
                scrolldown=1  # Minimal scrolling
            )
            
            html = response.html.html
            
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
        finally:
            if session:
                await session.close()
    
    def _extract_data(self, html: str, url: str) -> Dict[str, Any]:
        """
        Extract and parse relevant information from HTML using fast lxml parser
        """
        # Use lxml parser for 5-10x speed improvement over html.parser
        try:
            soup = BeautifulSoup(html, 'lxml')
        except:
            # Fallback to html.parser if lxml not available
            soup = BeautifulSoup(html, 'html.parser')
        
        # Extract audio elements BEFORE removing script tags (optimized)
        audio_elements = []
        for audio_tag in soup.find_all('audio'):
            src = audio_tag.get('src')
            if src:
                # Make absolute URL (urljoin already imported at top)
                if not src.startswith(('http://', 'https://')):
                    src = urljoin(url, src)
                audio_elements.append({
                    'src': src,
                    'controls': audio_tag.has_attr('controls')
                })
        
        # Remove script and style tags
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()
        
        # Extract metadata
        title = soup.find('title')
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        
        # Extract all text content
        text_content = soup.get_text(separator='\n', strip=True)
        
        # Extract all links (convert all to absolute URLs)
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Convert relative URLs to absolute
            if not href.startswith(('http://', 'https://', 'mailto:', 'tel:', 'javascript:')):
                href = urljoin(url, href)
            links.append({
                'text': link.get_text(strip=True),
                'href': href
            })
        
        # Extract images (convert all to absolute URLs)
        images = []
        for img in soup.find_all('img', src=True):
            src = img['src']
            # Convert relative URLs to absolute
            if not src.startswith(('http://', 'https://', 'data:')):
                src = urljoin(url, src)
            images.append({
                'alt': img.get('alt', ''),
                'src': src
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
        
        # Transcribe audio files if found (parallel processing for speed)
        audio_transcriptions = []
        if audio_elements:
            print(f"🎵 Found {len(audio_elements)} audio element(s) on the page")
            
            def transcribe_single_audio(idx_audio_tuple):
                idx, audio = idx_audio_tuple
                try:
                    audio_response = self.session.get(audio['src'], timeout=self.timeout)
                    audio_response.raise_for_status()
                    transcription = self._transcribe_audio(audio_response.content, audio['src'])
                    print(f"  ✅ Audio {idx} transcribed")
                    return {
                        'url': audio['src'],
                        'transcription': transcription,
                        'status': 'success' if not transcription.startswith('[Error') else 'failed'
                    }
                except Exception as e:
                    print(f"  ❌ Audio {idx} failed: {e}")
                    return {
                        'url': audio['src'],
                        'transcription': f"[Error: {str(e)}]",
                        'status': 'failed'
                    }
            
            # Process audio files in parallel for speed
            with ThreadPoolExecutor(max_workers=min(3, len(audio_elements))) as executor:
                audio_transcriptions = list(executor.map(
                    transcribe_single_audio,
                    enumerate(audio_elements, 1)
                ))
        
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
            'html_length': len(html),
            'raw_html': html,  # NEW: Raw HTML content
            'audio_elements': audio_elements,  # NEW: Audio elements found
            'audio_transcriptions': audio_transcriptions  # NEW: Transcribed audio
        }
    
    def _transcribe_audio(self, audio_content: bytes, url: str) -> str:
        """
        Transcribe audio file using speech_recognition
        """
        tmp_audio_path = None
        wav_path = None
        
        try:
            import speech_recognition as sr
            from pydub import AudioSegment
            import tempfile
            import os
            
            # Detect file extension from URL
            file_ext = '.mp3'
            if url.endswith('.opus'):
                file_ext = '.opus'
            elif url.endswith('.ogg'):
                file_ext = '.ogg'
            elif url.endswith('.wav'):
                file_ext = '.wav'
            elif url.endswith('.m4a'):
                file_ext = '.m4a'
            
            # Save audio to temp file with correct extension
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_audio:
                tmp_audio.write(audio_content)
                tmp_audio_path = tmp_audio.name
            
            # Convert to WAV format with optimized settings
            audio = AudioSegment.from_file(tmp_audio_path)
            wav_path = tmp_audio_path.replace(file_ext, '.wav')
            # Optimize: mono channel, 16kHz sample rate for faster processing
            audio = audio.set_channels(1).set_frame_rate(16000)
            audio.export(wav_path, format='wav', parameters=["-ac", "1", "-ar", "16000"])
            
            # Transcribe
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data)
                return text
                    
        except ImportError as e:
            return f"[Error: Required library not installed - {str(e)}. Install with: pip install SpeechRecognition pydub]"
        except sr.UnknownValueError:
            return "[Error: Google Speech Recognition could not understand the audio]"
        except sr.RequestError as e:
            return f"[Error: Could not request results from Google Speech Recognition service: {e}]"
        except Exception as e:
            return f"[Error transcribing audio: {str(e)}]"
        finally:
            # Cleanup temp files
            import os
            if tmp_audio_path and os.path.exists(tmp_audio_path):
                try:
                    os.remove(tmp_audio_path)
                except:
                    pass
            if wav_path and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except:
                    pass
    
    async def _handle_special_content(self, url: str, content_type: str) -> Dict[str, Any]:
        """
        Handle special content types (JSON, CSV, PDF, images, audio, etc.) with async optimization
        """
        try:
            # Async fetch for non-blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                lambda: self.session.get(url, timeout=self.timeout, stream=True)
            )
            response.raise_for_status()
            
            result = {
                'success': True,
                'method': f'direct_fetch ({content_type})',
                'data': {
                    'url': url,
                    'content_type': content_type,
                    'size': len(response.content),
                    'status_code': response.status_code
                }
            }
            
            if content_type == 'json':
                result['data']['json_data'] = response.json()
                result['data']['title'] = f'JSON API: {url}'
                
            elif content_type == 'csv':
                result['data']['csv_preview'] = response.text[:5000]
                result['data']['title'] = f'CSV File: {url}'
                
            elif content_type == 'pdf':
                result['data']['title'] = f'PDF File: {url}'
                result['data']['download_instructions'] = 'Use libraries like PyPDF2, pdfplumber, or pypdf to extract text'
                
            elif content_type == 'image':
                result['data']['title'] = f'Image File: {url}'
                result['data']['image_info'] = 'Use PIL/Pillow or computer vision libraries to process'
                
            elif content_type == 'audio':
                result['data']['title'] = f'Audio File: {url}'
                # Attempt to transcribe the audio in executor for non-blocking
                print(f"🎵 Transcribing audio file...")
                loop = asyncio.get_event_loop()
                transcription = await loop.run_in_executor(
                    self.executor,
                    self._transcribe_audio,
                    response.content,
                    url
                )
                result['data']['transcription'] = transcription
                result['data']['transcription_status'] = 'success' if not transcription.startswith('[Error') else 'failed'
                print(f"✅ Transcription complete")
                
            elif content_type == 'text':
                result['data']['text_content'] = response.text
                result['data']['title'] = f'Text File: {url}'
            
            elif content_type == 'xml':
                result['data']['xml_content'] = response.text[:5000]
                result['data']['title'] = f'XML File: {url}'
                
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to fetch {content_type}: {str(e)}',
                'method': f'direct_fetch ({content_type})'
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
        
        # Detect content type by making a fast HEAD request
        try:
            loop = asyncio.get_event_loop()
            head_response = await loop.run_in_executor(
                self.executor,
                lambda: self.session.head(url, timeout=5, allow_redirects=True)
            )
            # Convert headers dict to tuple for caching
            content_type = self._detect_content_type(url, tuple(head_response.headers.items()))
        except:
            content_type = self._detect_content_type(url, None)
        
        # Handle non-webpage content types
        if content_type != 'webpage':
            return await self._handle_special_content(url, content_type)
        
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
        Convert scraping result to optimized Markdown format for LLM analysis
        Structures data in clear sections with proper hierarchy
        """
        if not result.get('success'):
            return f"# ❌ Scraping Failed\n\n**Error:** {result.get('error', 'Unknown error')}\n"
        
        data = result['data'] 
        md = []
        
        # Detect content type
        content_type = data.get('content_type', 'webpage')
        
        # ============ HEADER SECTION ============
        md.append(f"# 📋 Quiz Page Analysis Report\n")
        md.append(f"\n⚠️ **CRITICAL**: This report contains ALL extracted data from the quiz page.\n")
        md.append(f"\n## 🎯 Quick Navigation Guide\n")
        md.append(f"1. **Read SECTION 1 (Text Content)** → Understand what the quiz is asking\n")
        md.append(f"2. **Check URL Parameters** → Email, ID, or other values needed for submission\n")
        md.append(f"3. **Look for data sources:**\n")
        md.append(f"   - SECTION 2 (Links) → External files, APIs, data endpoints\n")
        md.append(f"   - SECTION 3 (Tables) → Structured tabular data\n")
        md.append(f"   - SECTION 6 (Raw HTML) → JavaScript variables, hidden data, Base64\n")
        md.append(f"4. **Find submission endpoint** → Look for POST URLs in SECTION 2 or forms in SECTION 6\n")
        md.append(f"5. **Extract/Process data** → Use appropriate method (scraping, API call, data extraction)\n")
        md.append(f"6. **Format answer** → Match exact JSON structure required\n")
        md.append(f"7. **Submit** → POST to the submission endpoint\n")
        md.append(f"\n## 🌐 Page Metadata\n")
        md.append(f"- **Original URL:** {data['url']}\n")
        md.append(f"- **Content Type:** {content_type.upper()}\n")
        md.append(f"- **Scraping Method:** {result['method']}\n")
        
        if data.get('title'):
            md.append(f"- **Page Title:** {data['title']}\n")
        if data.get('meta_description'):
            md.append(f"- **Meta Description:** {data['meta_description']}\n")
        if data.get('size'):
            md.append(f"- **Content Size:** {data['size']:,} bytes\n")
        
        # Extract URL components - CRITICAL for quiz solving
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(data['url'])
        
        # Show URL components
        md.append(f"\n### 🔗 URL Components:\n")
        md.append(f"- **Scheme:** {parsed_url.scheme}\n")
        md.append(f"- **Domain:** {parsed_url.netloc}\n")
        md.append(f"- **Path:** {parsed_url.path}\n")
        
        if parsed_url.query:
            params = parse_qs(parsed_url.query)
            md.append(f"\n### 🔑 URL Query Parameters (⚠️ IMPORTANT for task!):\n")
            for key, values in params.items():
                md.append(f"- **{key}:** `{values[0]}`\n")
                # Highlight common quiz parameters
                if key.lower() in ['email', 'id', 'user', 'student', 'token', 'secret']:
                    md.append(f"  ⚡ *This parameter may be required for submission!*\n")
        else:
            md.append(f"- **Query Parameters:** None\n")
        
        md.append("\n" + "="*80 + "\n")
        
        # Handle different content types
        if content_type == 'json':
            md.append(f"\n## JSON Data\n")
            md.append("```json\n")
            md.append(json.dumps(data.get('json_data', {}), indent=2))
            md.append("\n```\n")
            return "\n".join(md)
        
        elif content_type == 'csv':
            md.append(f"\n## CSV Data\n")
            md.append("```csv\n")
            md.append(data.get('csv_preview', ''))
            md.append("\n```\n")
            return "\n".join(md)
        
        elif content_type == 'pdf':
            md.append(f"\n## PDF Document\n")
            md.append(f"Download URL: {data['url']}\n")
            return "\n".join(md)
        
        elif content_type == 'audio':
            md.append(f"\n## Audio File\n")
            md.append(f"URL: {data['url']}\n")
            md.append(f"Size: {data.get('size', 0):,} bytes\n")
            if 'transcription' in data:
                md.append(f"\n### Transcription:\n```\n{data['transcription']}\n```\n")
            return "\n".join(md)
        
        elif content_type == 'image':
            md.append(f"\n## Image File\n")
            md.append(f"URL: {data['url']}\n")
            return "\n".join(md)
        
        elif content_type == 'text':
            md.append(f"\n## Text Content\n")
            md.append(f"```\n{data.get('text_content', '')}\n```\n")
            return "\n".join(md)
        
        # ============ SECTION 1: TEXT CONTENT ============
        md.append(f"\n## 📝 SECTION 1: Page Text Content\n")
        md.append(f"**→ This section contains the visible text and instructions from the quiz page.**\n")
        md.append(f"**⚠️ READ THIS FIRST to understand what the task is asking!**\n\n")
        text_content = data.get('text_content', '')
        if text_content:
            # Detect key instruction words
            keywords = ['submit', 'post', 'endpoint', 'api', 'scrape', 'fetch', 'download', 'analyze', 'calculate', 'extract', 'format', 'json']
            found_keywords = [kw for kw in keywords if kw.lower() in text_content.lower()]
            if found_keywords:
                md.append(f"**🎯 Detected Task Keywords:** {', '.join(found_keywords)}\n\n")
            
            # Show first 15000 chars for better context
            md.append("```text\n")
            md.append(text_content[:15000])
            if len(text_content) > 15000:
                md.append(f"\n\n... [Truncated: {len(text_content) - 15000} more characters]\n")
            md.append("```\n")
        else:
            md.append("*No text content found*\n")
        
        # ============ SECTION 2: LINKS ============
        md.append(f"\n## 🔗 SECTION 2: All Links Found\n")
        md.append(f"**→ Links to data files, APIs, or other pages mentioned in the quiz.**\n")
        md.append(f"**⚠️ If task asks to 'scrape' or 'fetch' data, check these URLs!**\n\n")
        if data.get('links'):
            # Categorize links with more granularity
            data_links = []
            api_links = []
            media_links = []
            submission_links = []
            other_links = []
            
            for link in data['links'][:100]:  # Increased to 100
                href = link['href'].lower()
                text = link.get('text', '').lower()
                
                # Check if it's a submission endpoint
                if any(word in text for word in ['submit', 'post', 'answer']) or any(word in href for word in ['submit', 'answer', 'check']):
                    submission_links.append(link)
                elif any(ext in href for ext in ['.csv', '.json', '.pdf', '.xlsx', '.xml', '.txt']):
                    data_links.append(link)
                elif 'api' in href or '/data' in href or 'endpoint' in href:
                    api_links.append(link)
                elif any(ext in href for ext in ['.jpg', '.png', '.gif', '.mp3', '.mp4', '.wav', '.opus', '.ogg']):
                    media_links.append(link)
                else:
                    other_links.append(link)
            
            if submission_links:
                md.append(f"### ⚡ SUBMISSION ENDPOINTS (CRITICAL!):\n")
                for i, link in enumerate(submission_links, 1):
                    text = link.get('text', '').strip() or 'Submit'
                    md.append(f"{i}. **[{text}]({link['href']})**\n")
                    md.append(f"   - Full URL: `{link['href']}`\n")
                md.append(f"\n⚠️ **Use these URLs to POST your answer!**\n")
            
            if data_links:
                md.append(f"\n### 📊 Data Files:\n")
                for i, link in enumerate(data_links, 1):
                    text = link.get('text', '').strip() or 'Download'
                    md.append(f"{i}. [{text}]({link['href']})\n")
                    # Show file extension
                    ext = link['href'].split('.')[-1].upper() if '.' in link['href'] else 'Unknown'
                    md.append(f"   - Type: {ext}\n")
            
            if api_links:
                md.append(f"\n### 🌐 API/Data Endpoints:\n")
                for i, link in enumerate(api_links, 1):
                    text = link.get('text', '').strip() or 'Endpoint'
                    md.append(f"{i}. [{text}]({link['href']})\n")
            
            if media_links:
                md.append(f"\n### 🎬 Media Files:\n")
                for i, link in enumerate(media_links, 1):
                    text = link.get('text', '').strip() or 'File'
                    md.append(f"{i}. [{text}]({link['href']})\n")
            
            if other_links:
                md.append(f"\n### 🔗 Other Links:\n")
                for i, link in enumerate(other_links[:30], 1):  # Limit other links to 30
                    text = link.get('text', '').strip() or '[Link]'
                    md.append(f"{i}. {text} → {link['href']}\n")
                if len(other_links) > 30:
                    md.append(f"... and {len(other_links) - 30} more links\n")
        else:
            md.append("*No links found*\n")
        
        # ============ SECTION 3: TABLES ============
        md.append(f"\n## 📊 SECTION 3: Tables & Structured Data\n")
        md.append(f"**→ Tabular data extracted from the page.**\n")
        md.append(f"**⚠️ If task involves data analysis, this data may be here!**\n\n")
        if data.get('tables'):
            for table in data['tables']:
                md.append(f"### Table {table['table_index']}")
                if table['caption']:
                    md.append(f" - {table['caption']}")
                md.append("\n")
                
                # Add table dimensions
                num_rows = len(table.get('rows', []))
                num_cols = len(table.get('headers', []))
                md.append(f"**Dimensions:** {num_rows} rows × {num_cols} columns\n\n")
                
                if table['headers'] and table['rows']:
                    # Markdown table format
                    md.append("| " + " | ".join(str(h) for h in table['headers']) + " |\n")
                    md.append("|" + "|".join(["---" for _ in table['headers']]) + "|\n")
                    for row in table['rows'][:100]:  # Increased to 100 rows
                        padded_row = row + [''] * (len(table['headers']) - len(row))
                        md.append("| " + " | ".join(str(cell) for cell in padded_row[:len(table['headers'])]) + " |\n")
                    if len(table['rows']) > 100:
                        md.append(f"\n*... {len(table['rows']) - 100} more rows not shown*\n")
                elif table['rows']:
                    for i, row in enumerate(table['rows'][:50], 1):
                        md.append(f"Row {i}: {' | '.join(str(cell) for cell in row)}\n")
                    if len(table['rows']) > 50:
                        md.append(f"\n*... {len(table['rows']) - 50} more rows*\n")
                md.append("\n")
        else:
            md.append("*No tables found*\n")
        
        # ============ SECTION 4: IMAGES ============
        if data.get('images'):
            md.append(f"\n## 🖼️ SECTION 4: Images\n")
            md.append(f"**→ Image references found on the page.**\n\n")
            for i, img in enumerate(data['images'][:30], 1):
                md.append(f"{i}. Alt: `{img.get('alt', '[no alt]')}` | Src: {img['src']}\n")
            if len(data['images']) > 30:
                md.append(f"\n*... and {len(data['images']) - 30} more images*\n")
        
        # ============ SECTION 5: AUDIO FILES ============
        if data.get('audio_elements') or data.get('audio_transcriptions'):
            md.append(f"\n## 🎵 SECTION 5: Audio Files & Transcriptions\n")
            md.append(f"**→ Audio files found and their transcriptions (if available).**\n\n")
            
            # Show audio elements
            if data.get('audio_elements'):
                md.append("### Audio Files:\n")
                for idx, audio_elem in enumerate(data['audio_elements'], 1):
                    md.append(f"{idx}. {audio_elem['src']}\n")
                md.append("\n")
            
            # Show transcriptions
            if data.get('audio_transcriptions'):
                md.append("### Audio Transcriptions:\n")
                for idx, trans in enumerate(data['audio_transcriptions'], 1):
                    md.append(f"**Audio {idx}:** {trans['url']}\n")
                    md.append(f"**Status:** {trans['status']}\n")
                    if trans['status'] == 'success':
                        md.append(f"**Transcription:**\n```\n{trans['transcription']}\n```\n\n")
                    else:
                        md.append(f"**Error:** {trans['transcription']}\n\n")
        
        # ============ SECTION 6: RAW HTML SOURCE ============
        md.append(f"\n## 🔍 SECTION 6: Raw HTML Source Code\n")
        md.append(f"**→ Complete HTML including JavaScript, hidden data, and encoded values.**\n")
        md.append(f"\n**⚠️ CRITICAL CHECKS:**\n")
        md.append(f"- Look for `<script>` tags with JavaScript variables (var data = ..., const info = ...)\n")
        md.append(f"- Search for `<input type=\"hidden\">` elements with encoded data\n")
        md.append(f"- Check for Base64 strings (if you see atob() or btoa() functions)\n")
        md.append(f"- Look for JSON data embedded in JavaScript (JSON.parse(...))\n")
        md.append(f"- Find submission endpoints in <form> action attributes or fetch() calls\n\n")
        
        raw_html = data.get('raw_html', '')
        if raw_html:
            # Try to detect important patterns before showing HTML
            patterns_found = []
            if '<form' in raw_html.lower():
                patterns_found.append('Forms')
            if '<script' in raw_html.lower():
                patterns_found.append('JavaScript')
            if 'fetch(' in raw_html or 'axios.' in raw_html or '$.ajax' in raw_html:
                patterns_found.append('AJAX/API calls')
            if 'atob(' in raw_html or 'btoa(' in raw_html:
                patterns_found.append('Base64 encoding/decoding')
            if 'type="hidden"' in raw_html:
                patterns_found.append('Hidden inputs')
            if 'json.parse' in raw_html.lower():
                patterns_found.append('JSON data')
            
            if patterns_found:
                md.append(f"**🔍 Detected in HTML:** {', '.join(patterns_found)}\n\n")
            
            md.append("```html\n")
            # Increased limit to 150K for better coverage
            if len(raw_html) > 150000:
                md.append(raw_html[:150000])
                md.append(f"\n\n<!-- TRUNCATED: {len(raw_html) - 150000} more characters -->\n")
            else:
                md.append(raw_html)
            md.append("\n```\n")
        else:
            md.append("*No HTML source available*\n")
        
        # ============ FOOTER ============
        md.append(f"\n{'='*80}\n")
        md.append(f"📌 **End of Report** - All webpage content has been extracted and organized above.\n")
        
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
        "url": "https://tds-llm-analysis.s-anand.net/demo-audio",
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