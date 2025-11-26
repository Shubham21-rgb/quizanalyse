from fastapi import FastAPI, Request ,BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import json
import os
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse
import requests

app = FastAPI()
load_dotenv()

# Configuration
api_key = os.getenv("AI_PIPE_TOKEN_1")
EXPECTED_SECRET = os.getenv("SECRET_KEY", "23SHWEBGPT")
STUDENT_EMAIL = os.getenv("STUDENT_EMAIL", "23f2004891@ds.study.iitm.ac.in")


class AIPipeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://aipipe.org/openai/v1"

    class Chat:
        def __init__(self, parent):
            self.parent = parent

        class Completions:
            def __init__(self, parent):
                self.parent = parent

            def create(self, model, messages, temperature=0.7):
                url = f"{self.parent.parent.base_url}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.parent.parent.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature
                }
                resp = requests.post(url, headers=headers, json=payload)
                resp_json = resp.json()
                
                # Debug: Print raw response
                print("Raw API Response:", json.dumps(resp_json, indent=2))
                
                # Return object with proper structure
                class Response:
                    def __init__(self, data):
                        self.raw_data = data
                        self.model = data.get("model", "")
                        self.choices = [Choice(c) for c in data.get("choices", [])]
                
                class Choice:
                    def __init__(self, data):
                        self.message = Message(data.get("message", {}))
                
                class Message:
                    def __init__(self, data):
                        self.content = data.get("content", "")
                
                return Response(resp_json)

        @property
        def completions(self):
            return self.Completions(self)

    @property
    def chat(self):
        return self.Chat(self)

client = AIPipeClient(api_key)


###################################################


@app.get("/")
def greet_json():
    # Check if we can write files (important for Hugging Face)
    try:
        test_file = "test_write.tmp"
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        write_permission = True
    except:
        write_permission = False
    
    return {
        "message": "Quiz Solver API is running",
        "status": "ready",
        "write_permission": write_permission,
        "working_directory": os.getcwd(),
        "environment": "huggingface" if os.getenv("SPACE_ID") else "local"
    }

@app.post("/quiz")
async def handle_quiz(request: Request):
    """
    Main endpoint to receive quiz requests and solve them
    Expected payload: {"email": "...", "secret": "...", "url": "..."}
    """
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON payload"})
    
    # Validate required fields
    email = body.get("email")
    secret = body.get("secret")
    url = body.get("url")
    
    if not email or not secret or not url:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing required fields: email, secret, url"}
        )
    
    # Verify secret
    if secret != EXPECTED_SECRET:
        return JSONResponse(
            status_code=403,
            content={"error": "Invalid secret"}
        )
    
    # Start solving the quiz
    print(f"\n{'='*60}")
    print(f"🎯 New Quiz Request Received")
    print(f"Email: {email}")
    print(f"Starting URL: {url}")
    print(f"Request Body: {json.dumps(body, indent=2)}")
    print(f"{'='*60}\n")
    
    # Process the quiz URL with full request body
    result = await process_quiz_url(url, email, body)
    
    return JSONResponse(content=result)

async def process_quiz_url(url: str, email: str, request_body: dict = None, force_dynamic: bool = True, depth: int = 0, max_retries: int = 3):
    """
    Process a single quiz URL and return the result
    Supports recursive quiz chaining and retries for incorrect answers
    
    Args:
        url: The quiz URL to process
        email: Student email
        request_body: Original request body with email/secret
        force_dynamic: Whether to force dynamic rendering
        depth: Quiz sequence depth (for tracking)
        max_retries: Maximum retry attempts for incorrect answers (default: 3)
    """
    from LLMFunc import LLMScraperHandler
    
    print(f"\n{'='*60}")
    print(f"📥 Quiz #{depth + 1} - Scraping URL: {url}")
    print(f"📁 Working Directory: {os.getcwd()}")
    print(f"{'='*60}")
    handler = LLMScraperHandler()
    
    # Scrape the webpage
    scrape_request = {
        "url": url,
        "force_dynamic": force_dynamic
    }
    scrape_result = await handler.handle_request(scrape_request)
    
    if not scrape_result.get('success'):
        return {
            "success": False,
            "error": f"Scraping failed: {scrape_result.get('error', 'Unknown error')}"
        }
    
    # Generate markdown and save to question.md
    markdown_output = handler.format_as_markdown(scrape_result)
    
    # Use absolute path for Hugging Face compatibility
    current_dir = os.path.dirname(os.path.abspath(__file__))
    question_md_path = os.path.join(current_dir, "question.md")
    
    try:
        with open(question_md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_output)
        print(f"✅ Generated {question_md_path}")
    except Exception as e:
        print(f"⚠️ Error writing question.md: {e}")
        # Fallback to current directory
        question_md_path = "question.md"
        with open(question_md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_output)
        print(f"✅ Generated {question_md_path} (fallback)")
    
    # Read question.md content
    with open(question_md_path, 'r', encoding='utf-8') as f:
        question_md_content = f.read()
    
    # Prepare additional context from request body
    additional_context = ""
    if request_body:
        additional_context = f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n📨 REQUEST BODY DATA:\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n{json.dumps(request_body, indent=2)}\n\n⚠️ IMPORTANT: Use this request body data (email, secret, etc.) if the task requires it.\n"
    
    # Retry loop for incorrect answers
    retry_attempt = 0
    previous_errors = []
    
    while retry_attempt <= max_retries:
        if retry_attempt > 0:
            print(f"\n🔄 Retry attempt {retry_attempt}/{max_retries}")
        
        # Update prompt to use question.md content + request body + previous errors
        error_context = ""
        if previous_errors:
            error_context = f"\n\n⚠️ PREVIOUS ATTEMPTS FAILED:\n"
            for i, error in enumerate(previous_errors, 1):
                error_context += f"\nAttempt {i}: {error}\n"
            error_context += "\n🔧 ANALYZE THE ERROR AND TRY A DIFFERENT APPROACH!\n"
        
        # Use replace instead of format to avoid issues with {{ }} in examples
        prompt_final = prompt.replace("{content}", question_md_content + additional_context + error_context)
        
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt_final},
                    {"role": "user", "content": "Generate the complete Python script to solve this quiz."}
                ],
                temperature=0.4 + (retry_attempt * 0.1)  # Increase temperature on retries
            )
        
            if not hasattr(resp, 'choices') or len(resp.choices) == 0:
                return {
                    "success": False,
                    "error": "No response from LLM"
                }
            
            message_text = resp.choices[0].message.content
            
            # Extract Python code from the response
            python_code = None
            if "```python" in message_text:
                start_idx = message_text.find("```python") + len("```python")
                end_idx = message_text.find("```", start_idx)
                if end_idx != -1:
                    python_code = message_text[start_idx:end_idx].strip()
            elif "```" in message_text:
                start_idx = message_text.find("```") + len("```")
                end_idx = message_text.find("```", start_idx)
                if end_idx != -1:
                    python_code = message_text[start_idx:end_idx].strip()
            
            if not python_code:
                return {
                    "success": False,
                    "error": "No Python code generated by LLM"
                }
            
            # Save and execute the generated code
            # Use absolute path for Hugging Face compatibility
            current_dir = os.path.dirname(os.path.abspath(__file__))
            generate_py_path = os.path.join(current_dir, "generate.py")
            
            try:
                with open(generate_py_path, 'w', encoding='utf-8') as f:
                    f.write(python_code)
                print(f"✅ Saved Python code to {generate_py_path}")
            except Exception as e:
                print(f"⚠️ Error writing generate.py: {e}")
                # Fallback to current directory
                generate_py_path = "generate.py"
                with open(generate_py_path, 'w', encoding='utf-8') as f:
                    f.write(python_code)
                print(f"✅ Saved Python code to {generate_py_path} (fallback)")
            
            # Execute generate.py
            print(f"🚀 Executing {generate_py_path}...")
            import subprocess
            
            # Ensure working directory is set correctly for Hugging Face
            work_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
            
            result = subprocess.run(
                ["python3", os.path.basename(generate_py_path)],
                capture_output=True,
                text=True,
                timeout=150,  # 2.5 minutes to stay within 3 minute limit
                env=os.environ.copy(),  # Pass all environment variables to subprocess
                cwd=work_dir  # Set working directory for subprocess
            )
            
            execution_result = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
            
            if result.returncode == 0:
                print(f"✅ Successfully executed {generate_py_path}")
                print(f"Output:\n{result.stdout}")
                
                # Try to extract submission response
                import re
                submission_response = None
                is_correct = None
                reason = None
                next_url = None
                delay = None
                
                # Try multiple patterns to extract submission response
                # Look for various response patterns
                response_markers = [
                    "📥 Submission response:",
                    "Submission response:",
                    "📥 Response:",
                    "Response:",
                    "Server response:",
                    "submission response:"
                ]
                
                found_marker = None
                for marker in response_markers:
                    if marker in result.stdout:
                        found_marker = marker
                        break
                
                if found_marker:
                    json_start = result.stdout.find(found_marker) + len(found_marker)
                    remaining_text = result.stdout[json_start:].strip()
                    
                    try:
                        # Try to parse first line as JSON
                        first_line = remaining_text.split('\n')[0].strip()
                        
                        # Try standard JSON parsing first
                        try:
                            submission_response = json.loads(first_line)
                        except json.JSONDecodeError:
                            # If JSON fails, try to convert Python dict format to JSON
                            # Replace single quotes with double quotes, handle True/False/None
                            converted = first_line.replace("'", '"').replace('True', 'true').replace('False', 'false').replace('None', 'null')
                            submission_response = json.loads(converted)
                    except json.JSONDecodeError:
                        # Try to find JSON object with regex
                        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', remaining_text)
                        if json_match:
                            try:
                                dict_str = json_match.group(0)
                                # Try to convert Python dict format to JSON
                                converted = dict_str.replace("'", '"').replace('True', 'true').replace('False', 'false').replace('None', 'null')
                                submission_response = json.loads(converted)
                            except Exception as e:
                                print(f"⚠️ Could not parse JSON: {e}")
                    except Exception as e:
                        print(f"⚠️ Error extracting response: {e}")
                else:
                    # If no explicit response marker, try to find any JSON object that looks like a response
                    json_matches = re.findall(r'\{[^{}]*["\']correct["\'][^{}]*\}', result.stdout)
                    if json_matches:
                        try:
                            dict_str = json_matches[-1]  # Use last match
                            # Try standard JSON first
                            try:
                                submission_response = json.loads(dict_str)
                            except json.JSONDecodeError:
                                # Convert Python dict format to JSON
                                converted = dict_str.replace("'", '"').replace('True', 'true').replace('False', 'false').replace('None', 'null')
                                submission_response = json.loads(converted)
                        except Exception as e:
                            print(f"⚠️ Could not parse JSON: {e}")
                
                # Process the submission response (regardless of which parsing method was used)
                if isinstance(submission_response, dict):
                    is_correct = submission_response.get('correct')
                    reason = submission_response.get('reason', '')
                    next_url = submission_response.get('url')
                    delay = submission_response.get('delay')
                    
                    # Log the submission response details
                    print(f"\n📋 Server Response Summary:")
                    print(f"   Correct: {is_correct}")
                    if reason:
                        print(f"   Reason: {reason}")
                    if next_url:
                        print(f"   Next URL: {next_url}")
                    if delay:
                        print(f"   Delay: {delay}s")
                    
                    if is_correct:
                        print(f"\n✅ CORRECT ANSWER! 🎯")
                        print(f"🎉 Quiz #{depth + 1} solved successfully!")
                        
                        # Check if there's a next URL to process
                        if next_url and next_url.strip():
                            print(f"🔗 Next quiz URL provided: {next_url}")
                            
                            # Add delay if specified by server
                            if delay and delay > 0:
                                print(f"⏳ Waiting {delay} seconds as requested by server...")
                                import time
                                time.sleep(delay)
                            
                            # Recursively process next URL
                            print(f"\n{'='*60}")
                            print(f"🔄 Moving to Next Quiz (#{depth + 2})")
                            print(f"{'='*60}\n")
                            return await process_quiz_url(next_url, email, request_body, force_dynamic, depth + 1, max_retries)
                        else:
                            # No next URL - quiz sequence complete
                            print(f"\n🎉 QUIZ SEQUENCE COMPLETE!")
                            print(f"📊 Total quizzes solved: {depth + 1}")
                            print(f"🏆 All answers correct!")
                            return {
                                "success": True,
                                "correct": True,
                                "total_quizzes": depth + 1,
                                "execution_output": result.stdout,
                                "final_quiz": True
                            }
                    else:
                        # Incorrect answer
                        print(f"\n❌ INCORRECT ANSWER")
                        print(f"💡 Reason: {reason}")
                        
                        # Add to previous errors for retry
                        previous_errors.append(f"Incorrect: {reason}")
                        
                        # If we have retries left, continue the loop
                        if retry_attempt < max_retries:
                            print(f"🔄 Will retry with corrected approach (Attempt {retry_attempt + 1}/{max_retries})")
                            retry_attempt += 1
                            continue  # Retry with the error context
                        else:
                            print(f"🛑 Maximum retries ({max_retries}) reached for this quiz")
                            
                            # Check if there's a next URL even after incorrect answer
                            if next_url and next_url.strip():
                                print(f"⚠️ Server provided next URL despite incorrect answer: {next_url}")
                                print(f"🔄 Continuing to next quiz...")
                                
                                # Add delay if specified
                                if delay and delay > 0:
                                    import time
                                    time.sleep(delay)
                                
                                return await process_quiz_url(next_url, email, request_body, force_dynamic, depth + 1, max_retries)
                            
                            return {
                                "success": False,
                                "correct": False,
                                "reason": reason,
                                "retries_exhausted": True,
                                "execution_output": result.stdout
                            }
                
                # If no submission response was captured, treat as execution success but no validation
                if not submission_response:
                    print("⚠️ WARNING: No submission response found in output")
                    print("⚠️ This might indicate the script didn't submit properly")
                
                return {
                    "success": True,
                    "correct": is_correct,
                    "reason": reason,
                    "next_url": next_url,
                    "execution_output": result.stdout,
                    "quiz_number": depth + 1
                }
            else:
                # Execution failed
                error_msg = f"Execution failed with code {result.returncode}: {result.stderr}"
                print(f"❌ {error_msg}")
                
                # Add to previous errors for retry
                previous_errors.append(error_msg)
                
                # If we have retries left, continue the loop
                if retry_attempt < max_retries:
                    print(f"🔄 Will retry (Attempt {retry_attempt + 1}/{max_retries})")
                    retry_attempt += 1
                    continue
                
                return {
                    "success": False,
                    "error": error_msg,
                    "code": result.returncode
                }
                
        except subprocess.TimeoutExpired:
            error_msg = "Execution timeout (exceeded 2.5 minutes)"
            print(f"⏱️ {error_msg}")
            
            # Add to previous errors for retry
            previous_errors.append(error_msg)
            
            # If we have retries left, continue the loop
            if retry_attempt < max_retries:
                print(f"🔄 Will retry (Attempt {retry_attempt + 1}/{max_retries})")
                retry_attempt += 1
                continue
            
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            import traceback
            error_msg = f"Unexpected error: {str(e)}"
            print(f"❌ {error_msg}")
            print(traceback.format_exc())
            
            # Add to previous errors for retry
            previous_errors.append(error_msg)
            
            # If we have retries left, continue the loop
            if retry_attempt < max_retries:
                print(f"🔄 Will retry (Attempt {retry_attempt + 1}/{max_retries})")
                retry_attempt += 1
                continue
            
            return {
                "success": False,
                "error": error_msg,
                "traceback": traceback.format_exc()
            }

prompt="""You are a quiz-solving expert. The webpage content below is fully extracted and organized for you.

📋 CONTENT SECTIONS:
- SECTION 1 (Text Content): Task instructions, visible data, submission URLs
- SECTION 2 (Links): CSV/JSON/PDF files, APIs, external pages to scrape
- SECTION 3 (Tables): Pre-extracted tabular data
- SECTION 6 (Raw HTML): JS variables, hidden inputs, Base64, form actions
- URL Parameters & Request Body: Email, ID, secrets

🎯 QUICK STRATEGY:
1. Read SECTION 1 → Understand the task
2. Find data source:
   - Visible answer? → SECTION 1 (Text Content)
   - Hidden data? → SECTION 6 (Raw HTML - JS vars, hidden inputs)
   - External file/URL? → SECTION 2 (Links)
   - Table data? → SECTION 3 (Tables)
3. Extract/compute → Format as exact JSON → Submit with print statements

⚡ DATA EXTRACTION METHODS:

**Method 1: Current Page Data (No external fetch)**
```python
from bs4 import BeautifulSoup
import re, json

# For visible text: Check SECTION 1 (Text Content) directly
# For hidden data: Parse SECTION 6 (Raw HTML)
html = "..."  # From SECTION 6
soup = BeautifulSoup(html, 'html.parser')

# Extract JS variables
scripts = soup.find_all('script')
for script in scripts:
    if script.string and 'var ' in script.string:
        match = re.search(r'var\s+(\w+)\s*=\s*(\{{.*?\}}|".*?"|[\d.]+)', script.string)

# Extract hidden inputs
hidden = soup.find_all('input', type='hidden')
```

**Method 2: Simple Downloads (CSV/JSON/API)**
```python
import requests, pandas as pd
from io import StringIO

# JSON API
data = requests.get(url, headers={{"User-Agent": "Mozilla/5.0"}}).json()

# CSV file
df = pd.read_csv(StringIO(requests.get(url).text))
```

**Method 3: Complex Scraping (ONLY when task explicitly says "scrape")**
```python
import asyncio, requests, json, os
from LLMFunc import LLMScraperHandler

async def ai_scrape(url, task):
    handler = LLMScraperHandler()
    result = await handler.handle_request({{"url": url, "force_dynamic": True}})
    if not result.get('success'): return None
    
    # Option A: Use pre-extracted data (FASTEST)
    data = result['data']
    text = data.get('text_content', '')
    links = data.get('links', [])
    tables = data.get('tables', [])
    return {{"text": text, "links": links, "tables": tables}}
    
    # Option B: AI extraction (ONLY for complex parsing)
    # Use ONLY when simple parsing fails
    markdown = handler.format_as_markdown(result)
    ai_key = os.getenv("AI_PIPE_TOKEN_1")
    resp = requests.post("https://aipipe.org/openai/v1/chat/completions",
        headers={{"Authorization": f"Bearer {{ai_key}}", "Content-Type": "application/json"}},
        json={{"model": "gpt-4o-mini", "messages": [
            {{"role": "system", "content": "Extract data as JSON only"}},
            {{"role": "user", "content": f"Extract: {{task}}\\n\\nContent:\\n{{markdown}}"}}
        ], "temperature": 0.3}})
    return json.loads(resp.json()['choices'][0]['message']['content'])

# Use: data = asyncio.run(ai_scrape("https://url.com", "get table rows"))
```

⚠️ CRITICAL RULES:
- Try simple extraction FIRST (Method 1 or 2)
- Use AI scraping (Method 3 Option B) ONLY when:
  * Task explicitly says "scrape complex data"
  * Simple parsing fails
  * Data structure is too complex
- For most tasks: Direct extraction from sections is enough!

🔧 SCRAPING TOOLS - USE WHEN TASK ASKS TO SCRAPE:

**⚡ SMART SCRAPING WITH AI ASSISTANT (RECOMMENDED):**

When the task requires scraping external URLs, use the AI-powered scraping assistant that will:
1. Scrape the external URL
2. Extract and analyze the data intelligently
3. Return the processed results to you

```python
import asyncio
import requests
import json
import os
from LLMFunc import LLMScraperHandler

# AI-Powered Scraping Function (Use this when you need to scrape external URLs)
async def ai_scrape_and_extract(url_to_scrape: str, extraction_instructions: str):
    "
    Scrape a URL and use AI to extract specific data based on instructions.
    
    Args:
        url_to_scrape: The URL to scrape
        extraction_instructions: What you want to extract (e.g., "Extract all product prices", "Get the table data")
    
    Returns:
        Extracted data as a dictionary or list
    "
    print(f"🤖 AI-Powered Scraping: {{url_to_scrape}}")
    print(f"📝 Task: {{extraction_instructions}}")
    
    # Step 1: Scrape the URL
    handler = LLMScraperHandler()
    result = await handler.handle_request({{"url": url_to_scrape, "force_dynamic": True}})
    
    if not result.get('success'):
        print(f"❌ Scraping failed: {{result.get('error')}}")
        return None
    
    # Step 2: Format as markdown for AI processing
    markdown_content = handler.format_as_markdown(result)
    
    # Step 3: Call AI to extract data
    api_key = os.getenv("AI_PIPE_TOKEN_1")
    ai_prompt = f'''You are a data extraction expert. Extract the requested data from the webpage content below.

EXTRACTION TASK: {{extraction_instructions}}

WEBPAGE CONTENT:
{{markdown_content}}

Return ONLY a valid JSON object with the extracted data. No explanations, just the JSON.
'''
    
    ai_url = "https://aipipe.org/openai/v1/chat/completions"
    ai_headers = {{
        "Authorization": f"Bearer {{api_key}}",
        "Content-Type": "application/json"
    }}
    ai_payload = {{
        "model": "gpt-4o-mini",
        "messages": [
            {{"role": "system", "content": "You are a data extraction expert. Return only valid JSON."}},
            {{"role": "user", "content": ai_prompt}}
        ],
        "temperature": 0.3
    }}
    
    try:
        ai_response = requests.post(ai_url, headers=ai_headers, json=ai_payload, timeout=60)
        ai_result = ai_response.json()
        extracted_text = ai_result['choices'][0]['message']['content']
        
        # Try to parse as JSON
        if '```json' in extracted_text:
            json_start = extracted_text.find('```json') + 7
            json_end = extracted_text.find('```', json_start)
            extracted_text = extracted_text[json_start:json_end].strip()
        elif '```' in extracted_text:
            json_start = extracted_text.find('```') + 3
            json_end = extracted_text.find('```', json_start)
            extracted_text = extracted_text[json_start:json_end].strip()
        
        extracted_data = json.loads(extracted_text)
        print(f"✅ AI Extraction Complete!")
        return extracted_data
        
    except Exception as e:
        print(f"⚠️ AI extraction failed, returning raw text content")
        # Fallback: return the text content directly
        return result.get('data', {{}}).get('text_content', '')

# EXAMPLE USAGE:
# If task says "Scrape https://example.com/products and get all prices"
prices_data = asyncio.run(ai_scrape_and_extract(
    url_to_scrape="https://example.com/products",z
    extraction_instructions="Extract all product prices as a list of numbers"
))

# If task says "Scrape the data page and get the table"
table_data = asyncio.run(ai_scrape_and_extract(
    url_to_scrape="https://example.com/data",
    extraction_instructions="Extract the data table as a list of dictionaries with column names as keys"
))
```

**Method 2: Manual Scraping (if you need full control):**
```python
import asyncio
from LLMFunc import LLMScraperHandler
from bs4 import BeautifulSoup

async def scrape_external_page(url):
    print(f"🌐 Scraping external URL: {{url}}")
    handler = LLMScraperHandler()
    result = await handler.handle_request({{"url": url, "force_dynamic": True}})
    
    if result.get('success'):
        data = result.get('data', {{}})
        text_content = data.get('text_content', '')
        html_content = data.get('raw_html', '')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        return {{"text": text_content, "html": html_content, "soup": soup, "data": data}}
    else:
        print(f"❌ Scraping failed: {{result.get('error')}}")
        return None

# Use it:
scraped_data = asyncio.run(scrape_external_page("https://example.com/data"))
if scraped_data:
    text = scraped_data['text']
    soup = scraped_data['soup']
    # ... manual parsing
```

**Method 3: Download API/JSON/CSV Data (Direct):**
```python
import requests
import pandas as pd
from io import StringIO

# For JSON APIs
response = requests.get("https://api.example.com/data", headers={{"User-Agent": "Mozilla/5.0"}})
data = response.json()

# For CSV files (use AI assistant if complex)
csv_response = requests.get("https://example.com/data.csv", headers={{"User-Agent": "Mozilla/5.0"}})
df = pd.read_csv(StringIO(csv_response.text))

# For plain text/HTML (simple GET)
text_response = requests.get("https://example.com/page.html", headers={{"User-Agent": "Mozilla/5.0"}})
html_text = text_response.text
soup = BeautifulSoup(html_text, 'html.parser')
```

**Method 4: Extract from Current Page Content (no external fetch needed):**
```python
from bs4 import BeautifulSoup
import re
import json

# STEP 1: Check SECTION 1 (Text Content) first for visible answers
# If the question asks "What is X?" and X is shown on the page, it's here!

# STEP 2: If data is hidden, check SECTION 6 (Raw HTML)
# Look for these patterns in the Raw HTML section below:

# Pattern 1: JavaScript variables
# var data = {{"key": "value"}};
# const info = [...];
# let result = "answer";

# Pattern 2: Hidden form inputs
# <input type="hidden" id="answer" value="...">

# Pattern 3: JSON in script tags
# <script type="application/json">{{...}}</script>

# Pattern 4: Base64 encoded data
# var encoded = "SGVsbG8gV29ybGQ=";
# function decode() {{ return atob(encoded); }}

# Example extraction:
html_from_raw_section = "..."  # Copy from SECTION 6: Raw HTML Source Code below
soup = BeautifulSoup(html_from_raw_section, 'html.parser')

# Extract hidden inputs
hidden_inputs = soup.find_all('input', type='hidden')
for inp in hidden_inputs:
    print(f"Hidden: {{inp.get('id')}} = {{inp.get('value')}}")

# Extract JavaScript variables
script_tags = soup.find_all('script')
for script in script_tags:
    script_text = script.string or ''
    
    # Look for var/const/let declarations
    if 'var ' in script_text or 'const ' in script_text or 'let ' in script_text:
        # Extract JSON objects
        json_match = re.search(r'(?:var|const|let)\s+\w+\s*=\s*(\{{.*?\}});', script_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                print(f"Found data: {{data}}")
            except:
                pass
```

📤 SUBMISSION:
```python
print("📤 Submitting:", json.dumps(answer, indent=2))
response = requests.post(submit_url, json=answer, headers={{"User-Agent": "Mozilla/5.0"}})
print("📥 Response:", response.json())
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 COMPLETE WEBPAGE CONTENT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{content}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Now generate a complete, executable Python script that:
1. Analyzes the content above
2. Determines if external scraping is needed or if data is already provided
3. **If scraping is needed: Use ai_scrape_and_extract() function (AI-powered assistant)**
4. Extracts/computes the required data
5. Formats the answer correctly
6. Submits it with proper print statements

🤖 **IMPORTANT**: When you need to scrape external URLs, USE the ai_scrape_and_extract() function!
It will automatically:
- Scrape the URL for you
- Use AI to extract the exact data you need
- Return clean, structured data
- Handle complex HTML parsing automatically

Example: Instead of manually parsing HTML, just call:
```python
data = asyncio.run(ai_scrape_and_extract(
    url_to_scrape="https://example.com/data",
    extraction_instructions="Extract all table rows as a list of dictionaries"
))
```

Write the COMPLETE code with NO placeholders. Use AI-powered scraping when needed!"""


if __name__ == "__main__":
    import uvicorn
    import signal
    import sys
    
    def signal_handler(sig, frame):
        print("\n🛑 Shutting down server...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        sys.exit(0)