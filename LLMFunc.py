"""
LLM-Powered Web Scraping Agent
Intelligently scrapes static and dynamic web pages, and handles various file types
"""

import asyncio
import json
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, urlsplit
import requests
from bs4 import BeautifulSoup
from requests_html import AsyncHTMLSession
import mimetypes


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
    
    def _detect_content_type(self, url: str, response_headers: Dict = None) -> str:
        """
        Detect content type from URL or response headers
        """
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
        
        # Extract audio elements BEFORE removing script tags
        audio_elements = []
        for audio_tag in soup.find_all('audio'):
            src = audio_tag.get('src')
            if src:
                # Make absolute URL
                if not src.startswith(('http://', 'https://')):
                    from urllib.parse import urljoin
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
        
        # Transcribe audio files if found
        audio_transcriptions = []
        if audio_elements:
            print(f"🎵 Found {len(audio_elements)} audio element(s) on the page")
            for idx, audio in enumerate(audio_elements, 1):
                print(f"  Transcribing audio {idx}: {audio['src']}")
                try:
                    audio_response = self.session.get(audio['src'], timeout=30)
                    audio_response.raise_for_status()
                    transcription = self._transcribe_audio(audio_response.content, audio['src'])
                    audio_transcriptions.append({
                        'url': audio['src'],
                        'transcription': transcription,
                        'status': 'success' if not transcription.startswith('[Error') else 'failed'
                    })
                    print(f"  ✅ Transcription complete for audio {idx}")
                except Exception as e:
                    print(f"  ❌ Failed to transcribe audio {idx}: {e}")
                    audio_transcriptions.append({
                        'url': audio['src'],
                        'transcription': f"[Error: Failed to download or transcribe: {str(e)}]",
                        'status': 'failed'
                    })
        
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
            
            # Convert to WAV format (required for speech_recognition)
            audio = AudioSegment.from_file(tmp_audio_path)
            wav_path = tmp_audio_path.replace(file_ext, '.wav')
            audio.export(wav_path, format='wav')
            
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
        Handle special content types (JSON, CSV, PDF, images, audio, etc.)
        """
        try:
            response = self.session.get(url, timeout=30)
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
                # Attempt to transcribe the audio
                print(f"🎵 Attempting to transcribe audio file...")
                transcription = self._transcribe_audio(response.content, url)
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
        
        # Detect content type by making a HEAD request
        try:
            head_response = self.session.head(url, timeout=10, allow_redirects=True)
            content_type = self._detect_content_type(url, head_response.headers)
        except:
            content_type = self._detect_content_type(url)
        
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
        Convert scraping result to Markdown format
        """
        if not result.get('success'):
            return f"# Scraping Failed\n\n**Error:** {result.get('error', 'Unknown error')}\n"
        
        data = result['data']
        md = []
        
        # Detect content type
        content_type = data.get('content_type', 'webpage')
        
        # Header
        md.append(f"# Content Analysis Report\n")
        md.append(f"**URL:** {data['url']}\n")
        md.append(f"**Content Type:** {content_type.upper()}\n")
        md.append(f"**Method:** {result['method']}\n")
        if data.get('title'):
            md.append(f"**Title:** {data['title']}\n")
        if data.get('meta_description'):
            md.append(f"**Description:** {data['meta_description']}\n")
        if data.get('size'):
            md.append(f"**Size:** {data['size']:,} bytes\n")
        md.append("\n---\n")
        
        # Handle different content types
        if content_type == 'json':
            md.append(f"## 📊 JSON API Data\n")
            md.append("```json")
            md.append(json.dumps(data.get('json_data', {}), indent=2))
            md.append("```\n")
            md.append("\n**Instructions for LLM:**")
            md.append("- This is JSON data from an API endpoint")
            md.append("- Parse the JSON structure to extract required information")
            md.append("- Apply filters, aggregations, or transformations as needed\n")
            md.append("\n---\n")
            return "\n".join(md)
        
        elif content_type == 'csv':
            md.append(f"## 📈 CSV Data Preview\n")
            md.append("```csv")
            md.append(data.get('csv_preview', ''))
            md.append("```\n")
            md.append("\n**Instructions for LLM:**")
            md.append("- This is CSV (Comma-Separated Values) data")
            md.append("- Use pandas.read_csv() to load and process the data")
            md.append("- Perform required analysis: filtering, sorting, aggregation, statistics\n")
            md.append(f"\n**Python Code to Load:**")
            md.append("```python")
            md.append(f"import pandas as pd")
            md.append(f"df = pd.read_csv('{data['url']}')")
            md.append("```\n")
            md.append("\n---\n")
            return "\n".join(md)
        
        elif content_type == 'pdf':
            md.append(f"## 📄 PDF Document\n")
            md.append(f"**Download URL:** {data['url']}\n")
            md.append("\n**Instructions for LLM:**")
            md.append("- This is a PDF file that needs to be downloaded and processed")
            md.append("- Use PyPDF2, pdfplumber, or pypdf library to extract text")
            md.append("- Parse the extracted text to find required information\n")
            md.append(f"\n**Python Code to Process:**")
            md.append("```python")
            md.append("import requests")
            md.append("import PyPDF2  # or pdfplumber")
            md.append("from io import BytesIO")
            md.append("")
            md.append(f"response = requests.get('{data['url']}')")
            md.append("pdf_file = BytesIO(response.content)")
            md.append("reader = PyPDF2.PdfReader(pdf_file)")
            md.append("text = ''")
            md.append("for page in reader.pages:")
            md.append("    text += page.extract_text()")
            md.append("# Now parse 'text' to extract required data")
            md.append("```\n")
            md.append("\n---\n")
            return "\n".join(md)
        
        elif content_type == 'audio':
            md.append(f"## 🎵 Audio File\n")
            md.append(f"**Audio URL:** {data['url']}\n")
            md.append(f"**Size:** {data.get('size', 0):,} bytes\n")
            
            # Show transcription if available
            if 'transcription' in data:
                md.append(f"**Transcription Status:** {data.get('transcription_status', 'unknown')}\n")
                md.append("\n### 📝 Audio Transcription\n")
                
                transcription = data['transcription']
                if transcription.startswith('[Error'):
                    md.append(f"**{transcription}**\n")
                    md.append("\n**Note:** Automatic transcription failed. You may need to:")
                    md.append("- Install required libraries: `pip install SpeechRecognition pydub`")
                    md.append("- Ensure ffmpeg is installed for audio format conversion")
                    md.append("- Check internet connection (Google Speech Recognition requires internet)")
                else:
                    md.append("```")
                    md.append(transcription)
                    md.append("```\n")
                
                md.append("\n**Instructions for LLM:**")
                md.append("- The audio has been transcribed to text above")
                md.append("- Parse the transcription to extract required information")
                md.append("- Use regex or string operations to find specific data")
                md.append("- Follow the instructions mentioned in the audio transcription\n")
            else:
                md.append("\n**Instructions for LLM:**")
                md.append("- This is an audio file that needs transcription")
                md.append("- Download and transcribe using speech_recognition library")
                md.append("- Process the transcribed text to extract required information\n")
                md.append(f"\n**Python Code for Transcription:**")
                md.append("```python")
                md.append("import speech_recognition as sr")
                md.append("import requests")
                md.append("from pydub import AudioSegment")
                md.append("")
                md.append("# Download audio file")
                md.append(f"response = requests.get('{data['url']}')")
                md.append("with open('audio_file.mp3', 'wb') as f:")
                md.append("    f.write(response.content)")
                md.append("")
                md.append("# Transcribe")
                md.append("recognizer = sr.Recognizer()")
                md.append("# Convert to WAV if needed, then transcribe")
                md.append("```\n")
            
            md.append("\n---\n")
            return "\n".join(md)
        
        elif content_type == 'image':
            md.append(f"## 🖼️ Image File\n")
            md.append(f"**Image URL:** {data['url']}\n")
            md.append("\n**Instructions for LLM:**")
            md.append("- This is an image file that may need OCR or vision analysis")
            md.append("- Use pytesseract for OCR (Optical Character Recognition)")
            md.append("- Or use computer vision libraries (OpenCV, PIL) for image analysis")
            md.append("- Or use vision APIs (Google Vision, OpenAI Vision, etc.)\n")
            md.append(f"\n**Python Code for OCR:**")
            md.append("```python")
            md.append("import requests")
            md.append("from PIL import Image")
            md.append("import pytesseract")
            md.append("from io import BytesIO")
            md.append("")
            md.append(f"response = requests.get('{data['url']}')")
            md.append("image = Image.open(BytesIO(response.content))")
            md.append("text = pytesseract.image_to_string(image)")
            md.append("# Process extracted text")
            md.append("```\n")
            md.append("\n---\n")
            return "\n".join(md)
        
        elif content_type == 'text':
            md.append(f"## 📝 Text File Content\n")
            md.append("```")
            md.append(data.get('text_content', ''))
            md.append("```\n")
            md.append("\n**Instructions for LLM:**")
            md.append("- This is plain text content")
            md.append("- Parse the text to extract required information")
            md.append("- Use regex or string operations as needed\n")
            md.append("\n---\n")
            return "\n".join(md)
        
        # For webpages, continue with existing logic
        md.append(f"## 📊 Webpage Analysis\n")
        
        # Statistics
        md.append(f"## 📈 Statistics\n")
        md.append(f"- **Total Links:** {len(data.get('links', []))}")
        md.append(f"- **Total Images:** {len(data.get('images', []))}")
        md.append(f"- **Total Headings:** {len(data.get('headings', []))}")
        md.append(f"- **Total Tables:** {len(data.get('tables', []))}")
        md.append(f"- **HTML Length:** {data.get('html_length', 0):,} characters")
        md.append(f"- **Text Content Length:** {len(data.get('text_content', '')):,} characters\n")
        md.append("\n---\n")
        
        # Headings
        if data.get('headings'):
            md.append(f"## 📋 Headings ({len(data['headings'])})\n")
            for i, heading in enumerate(data['headings'], 1):
                md.append(f"{i}. **H{heading['level']}:** {heading['text']}")
            md.append("\n---\n")
        
        # Links
        if data.get('links'):
            md.append(f"## 🔗 Links ({len(data['links'])})\n")
            md.append("\n**Instructions for LLM:**")
            md.append("- These are links found on the webpage")
            md.append("- Check if any link points to external data sources (PDF, CSV, API, etc.)")
            md.append("- Use LLMScraperHandler to scrape additional URLs if needed\n")
            for i, link in enumerate(data['links'], 1):
                link_text = link['text'] if link['text'] else '[No text]'
                md.append(f"{i}. [{link_text}]({link['href']})")
            md.append("\n---\n")
        
        # Images
        if data.get('images'):
            md.append(f"## 🖼️ Images ({len(data['images'])})\n")
            for i, img in enumerate(data['images'], 1):
                alt_text = img['alt'] if img['alt'] else '[No alt text]'
                md.append(f"{i}. **Alt:** {alt_text}")
                md.append(f"   **Src:** {img['src']}")
            md.append("\n---\n")
        
        # Tables
        if data.get('tables'):
            md.append(f"## 📊 Tables ({len(data['tables'])})\n")
            md.append("\n**Instructions for LLM:**")
            md.append("- These are tables extracted from the webpage")
            md.append("- Parse table data to extract numbers, perform calculations, or find specific values")
            md.append("- Apply filters, aggregations, or transformations as needed\n")
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
        
        # Audio Elements (for audio embedded in webpages)
        if data.get('audio_elements'):
            md.append(f"## 🎵 Audio Files Found on Page ({len(data['audio_elements'])})\n")
            md.append("\n**⚠️ IMPORTANT: Audio files detected that need transcription!**\n")
            md.append("\n**Instructions for LLM:**")
            md.append("- Audio elements were found embedded in the webpage")
            md.append("- You MUST download and transcribe these audio files")
            md.append("- The audio likely contains important instructions or data for solving the quiz")
            md.append("- Use the following code to transcribe the audio:\n")
            
            for idx, audio_elem in enumerate(data['audio_elements'], 1):
                md.append(f"\n### Audio #{idx}\n")
                md.append(f"**Audio URL:** `{audio_elem['src']}`\n")
                md.append("\n**Python Code to Transcribe:**")
                md.append("```python")
                md.append("import requests")
                md.append("import speech_recognition as sr")
                md.append("from pydub import AudioSegment")
                md.append("import tempfile")
                md.append("import os")
                md.append("")
                md.append("# Download audio file")
                md.append("headers = {")
                md.append("    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'")
                md.append("}")
                md.append(f"audio_url = '{audio_elem['src']}'")
                md.append("response = requests.get(audio_url, headers=headers)")
                md.append("response.raise_for_status()")
                md.append("")
                md.append("# Save to temp file (detect extension)")
                md.append("file_ext = audio_url.split('.')[-1] if '.' in audio_url else 'mp3'")
                md.append("with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{{file_ext}}') as tmp:")
                md.append("    tmp.write(response.content)")
                md.append("    tmp_path = tmp.name")
                md.append("")
                md.append("try:")
                md.append("    # Convert to WAV format")
                md.append("    audio = AudioSegment.from_file(tmp_path)")
                md.append("    wav_path = tmp_path.replace(f'.{{file_ext}}', '.wav')")
                md.append("    audio.export(wav_path, format='wav')")
                md.append("    ")
                md.append("    # Transcribe using Google Speech Recognition")
                md.append("    recognizer = sr.Recognizer()")
                md.append("    with sr.AudioFile(wav_path) as source:")
                md.append("        audio_data = recognizer.record(source)")
                md.append("        transcription = recognizer.recognize_google(audio_data)")
                md.append("    ")
                md.append("    print(f'Audio Transcription: {{transcription}}')")
                md.append("    ")
                md.append("    # Clean up")
                md.append("    os.remove(tmp_path)")
                md.append("    os.remove(wav_path)")
                md.append("except Exception as e:")
                md.append("    print(f'Transcription error: {{e}}')")
                md.append("    # Cleanup on error")
                md.append("    if os.path.exists(tmp_path):")
                md.append("        os.remove(tmp_path)")
                md.append("```\n")
                md.append("\n**Alternative: Use LLMScraperHandler to get transcription**")
                md.append("The audio file will be automatically transcribed if you use the scraper.\n")
            
            # Also show transcriptions if available
            if data.get('audio_transcriptions'):
                for idx, audio_data in enumerate(data['audio_transcriptions'], 1):
                    transcription = audio_data['transcription']
                    if not transcription.startswith('[Error'):
                        md.append(f"\n**✅ Pre-transcribed Audio #{idx}:**")
                        md.append("```")
                        md.append(transcription)
                        md.append("```\n")
            
            md.append("\n---\n")
        
        # Structured Data
        if data.get('structured_data'):
            md.append(f"## 📊 Structured Data (JSON-LD)\n")
            md.append("\n**Instructions for LLM:**")
            md.append("- This is structured data embedded in the webpage (JSON-LD format)")
            md.append("- Often contains rich metadata about the page content")
            md.append("- Parse to extract specific information\n")
            md.append("```json")
            md.append(json.dumps(data['structured_data'], indent=2))
            md.append("```\n")
            md.append("\n---\n")
        
        # Text Content
        md.append(f"## 📄 Text Content\n")
        md.append("\n**Instructions for LLM:**")
        md.append("- This is the cleaned text content extracted from the webpage")
        md.append("- Search for specific patterns, numbers, or keywords using regex")
        md.append("- Extract relevant information based on the quiz question\n")
        text_preview = data.get('text_content', '')[:5000]
        if len(data.get('text_content', '')) > 5000:
            text_preview += "\n\n... (truncated)"
        md.append("```")
        md.append(text_preview)
        md.append("```\n")
        md.append("\n---\n")
        
        # Raw HTML Page
        md.append(f"## 🔧 Raw Page Content\n")
        md.append("\n**Instructions for LLM:**")
        md.append("- This is the complete HTML source with JavaScript and all tags")
        md.append("- Use if you need to extract data from specific HTML elements or scripts")
        md.append("- Parse with BeautifulSoup to find specific tags, classes, or IDs")
        md.append("- Look for embedded JSON data in <script> tags\n")
        md.append("```html")
        # Limit raw HTML to reasonable size (50000 chars)
        raw_html = data.get('raw_html', '')
        if len(raw_html) > 50000:
            md.append(raw_html[:50000])
            md.append("\n\n... (truncated - total length: " + str(len(raw_html)) + " characters)")
        else:
            md.append(raw_html)
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