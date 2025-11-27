"""
Simple AI Agent Architecture for Quiz Solving
Implements Think → Act → Reflect paradigm with tool usage
No LangChain dependencies - pure Python implementation
"""

import requests
import json
import re
import base64
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
import pandas as pd
from io import StringIO


# No tool classes needed for simple agent - direct implementation


class AIAgent:
    """
    Main AI Agent with reasoning and tool usage capabilities
    Implements: Think → Act → Reflect paradigm
    """
    
    def __init__(self, api_key: str, base_url: str = "https://aipipe.org/openai/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.conversation_history = []
        self.working_memory = {}
        self.iteration_count = 0
    
    def call_llm(self, messages: List[Dict[str, str]], temperature: float = 0.7, 
                 functions: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Call LLM with optional function calling capability"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": temperature
        }
        
        if functions:
            payload["functions"] = functions
            payload["function_call"] = "auto"
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ LLM call failed: {e}")
            return {"choices": [{"message": {"content": f"Error: {str(e)}"}}]}
    
    def think(self, task: str, context: str, previous_attempts: List[str] = None) -> Dict[str, Any]:
        """
        Phase 1: THINK - Analyze task and create strategic plan
        """
        print(f"\n{'='*70}")
        print(f"🧠 PHASE 1: AGENT THINKING")
        print(f"{'='*70}")
        
        error_context = ""
        if previous_attempts:
            error_context = "\n\nPREVIOUS FAILED ATTEMPTS:\n"
            for i, attempt in enumerate(previous_attempts, 1):
                error_context += f"Attempt {i}: {attempt}\n"
            error_context += "\n⚠️ Learn from these failures and try a different approach!\n"
        
        thinking_prompt = f"""You are an autonomous AI agent with advanced reasoning capabilities.
Your task is to analyze a quiz challenge and create a detailed strategic plan.

TASK CONTEXT:
{context}
{error_context}

CRITICAL ANALYSIS POINTS (FOLLOW EXACTLY):

1. **READ SECTION 1 CAREFULLY** - It contains the MAIN TASK:
   - What action is required? (scrape, calculate, analyze, extract, etc.)
   - What is the INPUT data source?
   - What is the OUTPUT format?

2. **EXTRACT BASE URL** from Original URL:
   - Example: https://tds-llm-analysis.s-anand.net/demo-scrape
   - BASE_URL = https://tds-llm-analysis.s-anand.net

3. **CONVERT RELATIVE URLs TO ABSOLUTE**:
   - If task mentions /demo-scrape-data
   - ABSOLUTE = BASE_URL + /demo-scrape-data
   - Example: https://tds-llm-analysis.s-anand.net/demo-scrape-data

4. **IDENTIFY SUBMISSION ENDPOINT**:
   - Usually /submit in SECTION 1 or SECTION 2
   - SUBMIT_URL = BASE_URL + /submit

5. **UNDERSTAND DATA EXTRACTION**:
   - What needs to be scraped? (a number, text, code, JSON, etc.)
   - Where is it located? (div id, span, table, script tag, etc.)
   - Is it plain text, base64 encoded, in JavaScript, or in HTML?

6. **IDENTIFY ANSWER FORMAT** (shown in code block in SECTION 1):
   - Check the JSON structure
   - Required fields: email, secret, url, answer
   - What type is 'answer'? (string, number, object, etc.)

Perform deep analysis and respond with a JSON plan containing:

1. **task_understanding**: Clear description of what needs to be accomplished
2. **task_type**: Type of task (scraping, calculation, visualization, data_processing, api_call, decoding, mixed)
3. **complexity**: Difficulty level (low, medium, high)
4. **base_url**: Base URL extracted from Original URL (e.g., https://domain.com)
5. **data_sources**: List of ABSOLUTE URLs to scrape/fetch data from
6. **submission_url**: ABSOLUTE URL where answer should be POSTed
7. **required_tools**: Tools/libraries needed (requests, BeautifulSoup, pandas, etc.)
8. **execution_steps**: Detailed step-by-step execution plan
9. **expected_output_format**: Structure of the expected answer JSON
10. **extraction_strategy**: Specific strategy (scrape URL X, decode Y, parse Z)
11. **potential_challenges**: Anticipated difficulties

Respond ONLY with valid JSON in this exact format:
{{
    "task_understanding": "description",
    "task_type": "scraping|calculation|visualization|mixed",
    "complexity": "low|medium|high",
    "base_url": "https://domain.com",
    "data_sources": ["https://full-url.com/data"],
    "submission_url": "https://full-url.com/submit",
    "required_tools": ["requests", "BeautifulSoup"],
    "execution_steps": ["step 1", "step 2", "step 3"],
    "expected_output_format": {{"email": "...", "answer": "..."}},
    "extraction_strategy": "strategy description",
    "potential_challenges": ["challenge 1"]
}}"""
        
        messages = [
            {"role": "system", "content": thinking_prompt},
            {"role": "user", "content": "Analyze this task deeply and create a strategic execution plan."}
        ]
        
        response = self.call_llm(messages, temperature=0.2)
        
        try:
            content = response['choices'][0]['message']['content']
            
            # Extract JSON from response
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            
            plan = json.loads(content)
            
            print(f"✅ Task Understanding: {plan.get('task_understanding', 'N/A')[:100]}...")
            print(f"✅ Task Type: {plan.get('task_type', 'unknown')}")
            print(f"✅ Complexity: {plan.get('complexity', 'medium')}")
            print(f"✅ Execution Steps: {len(plan.get('execution_steps', []))}")
            print(f"✅ Required Tools: {', '.join(plan.get('required_tools', []))}")
            
            self.working_memory['current_plan'] = plan
            return plan
            
        except Exception as e:
            print(f"⚠️ Planning phase error: {e}")
            # Fallback plan
            return {
                "task_understanding": "Solve quiz task",
                "task_type": "mixed",
                "complexity": "medium",
                "data_sources": [],
                "required_tools": ["requests", "beautifulsoup", "pandas"],
                "execution_steps": [
                    "Read SECTION 1 to understand task",
                    "Identify data sources",
                    "Extract and process data",
                    "Format answer",
                    "Submit"
                ],
                "expected_output_format": {},
                "extraction_strategy": "Analyze SECTION 1 first, then check other sections",
                "potential_challenges": []
            }
    
    def act(self, plan: Dict[str, Any], context: str, temperature: float = 0.4) -> str:
        """
        Phase 2: ACT - Execute the plan and generate solution code
        """
        print(f"\n{'='*70}")
        print(f"🎯 PHASE 2: AGENT ACTION")
        print(f"{'='*70}")
        
        action_prompt = f"""You are an AI agent executing a strategic plan to solve a quiz task.

STRATEGIC PLAN:
{json.dumps(plan, indent=2)}

FULL TASK CONTEXT:
{context}

EXECUTION INSTRUCTIONS:

**STEP 1: DEEP TASK UNDERSTANDING**

CRITICAL: Read SECTION 1 word by word!

Example: "Scrape /demo-scrape-data?email=... (relative to this page). Get the secret code from this page."

This means:
1. **SCRAPE** the URL: /demo-scrape-data?email=...
   - Convert to absolute: BASE_URL + /demo-scrape-data?email=...
   - Fetch this URL with requests.get()
   
2. **EXTRACT** from the SCRAPED page:
   - "Get the secret code from this page" = from the scraped page, NOT the quiz page
   - Look for: text content, HTML elements, JavaScript variables, base64 data
   - The secret could be in: div/span/p tags, script variables, or encoded data
   
3. **SUBMIT** the extracted data:
   - POST to /submit endpoint
   - Payload format from SECTION 1 code block
   - The 'url' field = ORIGINAL QUIZ URL (where you started)
   - The 'answer' field = the secret code you scraped

KEY DISTINCTION:
- QUIZ PAGE = Original URL (where instructions are)
- DATA PAGE = The URL you need to scrape (mentioned in SECTION 1)
- Submit 'url' field = QUIZ PAGE
- Extract answer from = DATA PAGE

**STEP 2: EXTRACT AND BUILD URLs**

From the context metadata:
- **BASE_URL**: From 'Original URL'
  * Extract: https://tds-llm-analysis.s-anand.net (scheme + domain)
  * Python: from urllib.parse import urlparse; parsed = urlparse(original_url); BASE_URL = f"{{parsed.scheme}}://{{parsed.netloc}}"
  
- **DATA_URL**: From SECTION 1 task description
  * If relative: /demo-scrape-data?email=...
  * Make absolute: BASE_URL + /demo-scrape-data?email=...
  * Include query parameters from URL Parameters section
  
- **SUBMIT_URL**: From SECTION 1 or SECTION 2
  * Usually /submit
  * Make absolute: BASE_URL + /submit
  
- **ORIGINAL_QUIZ_URL**: The 'Original URL' from metadata
  * This goes in the 'url' field of submission payload
  * NOT the data URL!

**STEP 3: ROBUST CODE GENERATION**

🚨 **ABSOLUTE REQUIREMENTS - MANDATORY:**

❌ **NEVER write code like this (BRITTLE - will crash):**
```python
# BAD - crashes if find() returns None
script = soup.find('script').string  # ❌ NO!
code = script.split('code = ')[1]     # ❌ NO!
```

✅ **ALWAYS write code like this (ROBUST - handles errors):**
```python
# GOOD - checks for None and has fallbacks
script = soup.find('script')
if script and script.string:
    if 'code = ' in script.string:
        parts = script.string.split('code = ')
        if len(parts) > 1:
            code = parts[1].split(';')[0] if ';' in parts[1] else parts[1]
```

🔒 **MANDATORY RULES:**
1. NEVER call methods on soup.find() result without checking if it's None
2. NEVER use .split()[index] without checking length
3. ALWAYS wrap each extraction strategy in try-except
4. ALWAYS have multiple fallback strategies
5. ALWAYS print what you found at each step
6. ALWAYS check if variables exist before using them

Generate a complete, bulletproof Python script:

**A. IMPORTS** (standard libraries only):
```python
import requests
from bs4 import BeautifulSoup
import json
import base64
import re
import hashlib
from urllib.parse import urlparse
```

**B. CONSTANTS** (extract from context):
```python
# Extract base URL
ORIGINAL_URL = "https://domain.com/path?params"  # From metadata
parsed = urlparse(ORIGINAL_URL)
BASE_URL = f"{{parsed.scheme}}://{{parsed.netloc}}"

# Build data URL (from SECTION 1)
DATA_URL = BASE_URL + "/path?email=..."  # Make absolute

# Build submit URL
SUBMIT_URL = BASE_URL + "/submit"

# Credentials (from metadata and request body)
EMAIL = "..."  # From URL Query Parameters
SECRET = "..."  # From REQUEST BODY DATA
```

**C. SCRAPING FUNCTION** (intelligent multi-strategy extraction with error handling):
```python
def scrape_data():
    """Extract data using multiple fallback strategies. Each strategy has error handling."""
    headers = {{"User-Agent": "Mozilla/5.0"}}
    
    try:
        response = requests.get(DATA_URL, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        print(f"✓ Successfully fetched {{DATA_URL}}")
    except Exception as e:
        print(f"❌ Failed to fetch page: {{e}}")
        return None
    
    # STRATEGY 0: If JS references emailNumber() or SHA1 calculations
    # Some tasks calculate code from email hash (see utils.js pattern)
    try:
        if 'emailNumber' in response.text or 'sha1' in response.text.lower():
            import hashlib
            sha1_hash = hashlib.sha1(EMAIL.encode()).hexdigest()
            number = int(sha1_hash[:4], 16)  # First 4 hex digits -> int
            print(f"✓ Strategy 0: Calculated from email SHA1: {{number}}")
            return str(number)
    except Exception as e:
        print(f"⚠ Strategy 0 failed: {{e}}")
    
    # Strategy 1: Common element IDs with smart extraction
    try:
        for elem_id in ['secret', 'code', 'answer', 'result', 'data', 'question']:
            elem = soup.find(id=elem_id)
            if elem:
                text = elem.get_text().strip()
                if text:
                    # Pattern matching for common formats
                    # "Secret code is 23109 and not 23294" → extract 23109
                    patterns = [
                        r'(?:secret|code|answer)\s+is\s+(\d+)',  # "code is 23109"
                        r'(?:secret|code|answer):\s*(\d+)',       # "code: 23109"
                        r'(?:secret|code|answer)\s*=\s*(\d+)',   # "code = 23109"
                        r'<strong>(\d+)</strong>',                 # <strong>23109</strong>
                        r'\b(\d{{4,}})\b'                         # Any 4+ digit number
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            value = match.group(1)
                            print(f"✓ Strategy 1: Extracted number: {{value}} from: {{text[:100]}}")
                            return value
                    # Fallback: if text is short, return it
                    if len(text) < 200:
                        print(f"✓ Strategy 1: Found text: {{text}}")
                        return text
    except Exception as e:
        print(f"⚠ Strategy 1 failed: {{e}}")
    
    # STRATEGY 2: Check for external JavaScript files
    try:
        for script_tag in soup.find_all('script', src=True):
            js_url = script_tag.get('src', '')
            if not js_url:
                continue
            if not js_url.startswith('http'):
                js_url = BASE_URL + ('/' if not js_url.startswith('/') else '') + js_url
            
            print(f"→ Checking external JS: {{js_url}}")
            try:
                js_resp = requests.get(js_url, headers=headers, timeout=30)
                js_content = js_resp.text
                
                # Check if JS uses emailNumber or SHA1 calculation
                if 'emailNumber' in js_content or 'sha1' in js_content.lower() or 'utils.js' in js_content:
                    print(f"✓ Detected email-based calculation in JS")
                    sha1_hash = hashlib.sha1(EMAIL.encode()).hexdigest()
                    number = int(sha1_hash[:4], 16)
                    print(f"✓ Strategy 2: Calculated from email: {{number}}")
                    return str(number)
                
                # Look for base64 in external JS
                b64_matches = re.findall(r'([A-Za-z0-9+/]{{20,}}={{0,2}})', js_content)
                for b64_str in b64_matches:
                    try:
                        decoded = base64.b64decode(b64_str).decode('utf-8')
                        if 5 < len(decoded) < 100:
                            print(f"✓ Strategy 2: Decoded from {{js_url}}: {{decoded}}")
                            return decoded.strip()
                    except:
                        pass
                
                # Look for secret/code variables in external JS
                var_matches = re.findall(r'(?:const|let|var)\\s+(\\w+)\\s*=\\s*["\']([^"\']+)["\']', js_content)
                for var_name, var_value in var_matches:
                    if any(kw in var_name.lower() for kw in ['secret', 'code', 'answer']):
                        print(f"✓ Strategy 2: Found in {{js_url}} variable {{var_name}}: {{var_value}}")
                        return var_value
            except Exception as js_err:
                print(f"⚠ Could not fetch {{js_url}}: {{js_err}}")
                continue
    except Exception as e:
        print(f"⚠ Strategy 2 failed: {{e}}")
    
    # STRATEGY 3: Extract from inline JavaScript (BASE64, variables)
    try:
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # Find base64 strings (20+ chars of A-Za-z0-9+/=)
                b64_matches = re.findall(r'([A-Za-z0-9+/]{{20,}}={{0,2}})', script.string)
                for b64_str in b64_matches:
                    try:
                        decoded = base64.b64decode(b64_str).decode('utf-8')
                        # If short and looks like a code
                        if 5 < len(decoded) < 100:
                            print(f"✓ Strategy 3: Decoded base64: {{decoded}}")
                            return decoded.strip()
                    except:
                        pass
                
                # Find variable assignments with secret/code/answer
                var_matches = re.findall(r'(?:const|let|var)\\s+(\\w+)\\s*=\\s*["\']([^"\']+)["\']', script.string)
                for var_name, var_value in var_matches:
                    if any(kw in var_name.lower() for kw in ['secret', 'code', 'answer']):
                        print(f"✓ Strategy 3: Found JS variable {{var_name}}: {{var_value}}")
                        return var_value
    except Exception as e:
        print(f"⚠ Strategy 3 failed: {{e}}")
    
    # STRATEGY 4: Look for hidden inputs
    try:
        for inp in soup.find_all('input', {{'type': 'hidden'}}):
            value = inp.get('value', '')
            if value:
                print(f"✓ Strategy 4: Found hidden input: {{value}}")
                return value
    except Exception as e:
        print(f"⚠ Strategy 4 failed: {{e}}")
    
    # STRATEGY 5: Extract short standalone text lines
    try:
        text = soup.get_text()
        lines = [l.strip() for l in text.split('\\n') if l.strip()]
        for line in lines:
            if 5 < len(line) < 50 and line.replace(' ', '').isalnum():
                print(f"✓ Strategy 5: Found potential code: {{line}}")
                return line
    except Exception as e:
        print(f"⚠ Strategy 5 failed: {{e}}")
    
    # Debug fallback - show what we got
    print(f"❌ No secret found using any strategy!")
    print(f"HTML preview (first 800 chars):\\n{{response.text[:800]}}")
    return None
```

**D. SUBMISSION FUNCTION** (match exact format):
```python
def submit_answer(answer):
    payload = {{
        "email": EMAIL,
        "secret": SECRET,
        "url": ORIGINAL_URL,  # The quiz URL, NOT data URL
        "answer": answer
    }}
    
    try:
        response = requests.post(SUBMIT_URL, json=payload, timeout=30)
        response.raise_for_status()
        print(f"Submission response: {{response.json()}}")
        return response.json()
    except Exception as e:
        print(f"Submission error: {{e}}")
        return None
```

**E. MAIN EXECUTION** (with fallbacks):
```python
if __name__ == "__main__":
    print(f"BASE_URL: {{BASE_URL}}")
    print(f"DATA_URL: {{DATA_URL}}")
    print(f"SUBMIT_URL: {{SUBMIT_URL}}")
    
    # Scrape data
    answer = scrape_data()
    
    if answer:
        print(f"Extracted answer: {{answer}}")
        result = submit_answer(answer)
        if result:
            print(f"Success: {{result}}")
    else:
        print("Failed to extract answer")
```

🚨 CRITICAL REQUIREMENTS (MUST FOLLOW):
✅ Use ABSOLUTE URLs (BASE_URL + relative_path, not just /path)
✅ Extract email from URL Query Parameters section
✅ Extract secret from REQUEST BODY DATA section
✅ The 'url' field in payload = ORIGINAL_URL (quiz page), NOT data URL
✅ **ALWAYS check if soup.find() returns None before calling methods**
✅ **NEVER use .split()[index] - check len() first**
✅ **Wrap EACH extraction strategy in try-except**
✅ Print debug info at each step
✅ Use try/except for all network calls
✅ Include User-Agent header
✅ Use response.raise_for_status() to catch HTTP errors
✅ Add timeout to all requests (timeout=30)

❌ FORBIDDEN PATTERNS (These will crash):
```python
script = soup.find('script').string  # ❌ Crashes if None
code = text.split('=')[1]             # ❌ Crashes if no '='
value = items[0]                      # ❌ Crashes if empty list
```

✅ REQUIRED PATTERNS (These are safe):
```python
script = soup.find('script')
if script and script.string:          # ✅ Check for None
    if '=' in text:                    # ✅ Check before split
        parts = text.split('=')
        if len(parts) > 1:             # ✅ Check length
            code = parts[1]
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 STEP 1: ANALYZE THE TASK TYPE (REQUIRED!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before writing ANY code, identify what SECTION 1 is asking:

📊 **Task Types:**
1. **Web Scraping** - Extract data from HTML/JavaScript
   → Use scraping template with multiple strategies
   
2. **Data Processing** - Calculate, aggregate, or transform data
   → Fetch data, use pandas/numpy, perform calculations
   
3. **API Request** - Call an endpoint and process JSON/CSV
   → Simple requests.get() + json parsing
   
4. **File Analysis** - Parse CSV, JSON, or other files
   → Use pandas.read_csv() or json.loads()
   
5. **Visualization** - Create charts or graphs
   → Use matplotlib/seaborn

⚠️ CRITICAL: Don't assume it's always scraping! Read SECTION 1 carefully.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 STEP 1: ANALYZE TASK TYPE (CRITICAL - DO THIS FIRST!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ NOT ALL TASKS REQUIRE SCRAPING! Read SECTION 1 carefully:

TASK TYPE CHECKLIST:

1. **SIMPLE SUBMISSION** (No scraping!)
   Keywords: "POST this JSON", "answer: anything you want"
   Example: "POST {..., answer: 'anything you want'}"
   → Just submit JSON with simple answer like "test"

2. **SCRAPING TASK** (Extract data first)
   Keywords: "scrape", "fetch data from URL", "get secret code"
   Example: "Scrape /data?email=... Get the code"
   → Use scraping strategies to extract data

3. **CALCULATION** (Math operations)
   Keywords: "calculate", "sum", "average", "compute"
   → Extract numbers and calculate

4. **API TASK** (External API call)
   Keywords: "API", "endpoint", "call service"
   → Make HTTP requests to APIs

5. **DATA PROCESSING** (Transform data)
   Keywords: "process", "transform", "filter", "clean"
   → Load and manipulate data

6. **VISUALIZATION** (Generate images)
   Keywords: "chart", "graph", "plot", "visualize"
   → Create images with matplotlib/plotly

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 AVAILABLE HELPER: LLMFunc.py (OPTIONAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For scraping tasks, you can use LLMFunc.py's LLMScraperHandler:
```python
from LLMFunc import LLMScraperHandler
scraper = LLMScraperHandler()
result = scraper.scrape_url(url)  # Advanced scraping with retry logic
```
Use only for complex scraping. The template below works for most tasks.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 TEMPLATES BY TASK TYPE 🚨
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ Choose template based on task type analysis above!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 TEMPLATE 0: SIMPLE SUBMISSION (No scraping - just POST)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use when: "POST this JSON", "answer: anything you want", no data extraction needed

```python
import requests
import json

# Extract from context metadata
BASE_URL = "https://tds-llm-analysis.s-anand.net"  # From Original URL
SUBMIT_URL = BASE_URL + "/submit"  # From SECTION 1
EMAIL = "23f2003481@ds.study.iitm.ac.in"  # From request body
SECRET = "23SHWEBGPT"  # From request body
URL_PARAM = "https://tds-llm-analysis.s-anand.net/demo"  # Original URL

def submit_answer(answer):
    """Submit answer to endpoint."""
    payload = {{
        "email": EMAIL,
        "secret": SECRET,
        "url": URL_PARAM,
        "answer": answer
    }}
    print(f"📤 Submitting to: {{SUBMIT_URL}}")
    print(f"📦 Payload: {{json.dumps(payload, indent=2)}}")
    
    response = requests.post(SUBMIT_URL, json=payload, timeout=30)
    result = response.json()
    print(f"📥 Response: {{result}}")
    return result

if __name__ == "__main__":
    # For "anything you want", use simple test value
    answer = "test"  # Or any value as instructed
    result = submit_answer(answer)
    print(f"✅ Final result: {{result}}")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 TEMPLATE 1: WEB SCRAPING (Use for HTML/JS data extraction)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CRITICAL: Copy this template character-by-character!

❌ DO NOT:
- Write your own scraping function
- Skip Strategy 2 (external JS - it's CRITICAL!)
- Remove any imports or strategies

✅ ONLY CHANGE:
- URLs (BASE_URL, DATA_URL, SUBMIT_URL)
- Credentials (EMAIL, SECRET, ORIGINAL_URL)

⚠️ When HTML shows <div id="question"></div> (empty) with <script src="demo-scrape.js">,
   the content is JavaScript-loaded! Strategy 2 fetches the JS, detects emailNumber(),
   and calculates SHA1(email)[:4] → answer. DO NOT SKIP IT!

Template includes ALL strategies:
✅ Strategy 0: Email SHA1 detection in page source
✅ Strategy 1: Pattern matching ("Secret code is 23109")
✅ Strategy 2: External JS fetching + SHA1 calculation (CRITICAL!)
✅ Strategy 3: Base64 decoding
✅ Strategy 4: Hidden inputs
✅ Strategy 5: Text extraction

COMPLETE TEMPLATE (COPY EXACTLY!):
```python
# ALWAYS include these imports at the top!
import requests
from bs4 import BeautifulSoup
import json
import base64
import re
import hashlib
import re
import hashlib
from urllib.parse import urlparse

# Step 1: Extract URLs from context
ORIGINAL_URL = "https://tds-llm-analysis.s-anand.net/demo-scrape?email=23f2003481%40ds.study.iitm.ac.in&id=10911"
parsed = urlparse(ORIGINAL_URL)
BASE_URL = f"{{parsed.scheme}}://{{parsed.netloc}}"

# Step 2: Build absolute URLs
DATA_URL = BASE_URL + "/demo-scrape-data?email=23f2003481@ds.study.iitm.ac.in"
SUBMIT_URL = BASE_URL + "/submit"

# Step 3: Extract credentials
EMAIL = "23f2003481@ds.study.iitm.ac.in"  # From URL params
SECRET = "23SHWEBGPT"  # From request body

def scrape_data():
    """Multi-strategy extraction with proper error handling."""
    headers = {{"User-Agent": "Mozilla/5.0"}}
    
    # Fetch the page
    try:
        print(f"Fetching: {{DATA_URL}}")
        response = requests.get(DATA_URL, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        print(f"✓ Page fetched successfully")
    except Exception as e:
        print(f"❌ Failed to fetch page: {{e}}")
        return None
    
    # Strategy 1: Common element IDs
    try:
        for elem_id in ['secret', 'code', 'answer', 'result', 'question']:
            elem = soup.find(id=elem_id)
            if elem:
                text = elem.get_text().strip()
                if text:
                    print(f"✓ Found by ID: {{text}}")
                    return text
    except Exception as e:
        print(f"⚠ Strategy 1 error: {{e}}")
    
    # Strategy 2: External JavaScript files
    try:
        for script_tag in soup.find_all('script', src=True):
            js_url = script_tag.get('src', '')
            if not js_url:
                continue
            if not js_url.startswith('http'):
                js_url = BASE_URL + ('/' if not js_url.startswith('/') else '') + js_url
            print(f"→ Checking: {{js_url}}")
            try:
                js_resp = requests.get(js_url, headers=headers, timeout=30)
                js_content = js_resp.text
                # Check if it imports other modules or calculates from email
                if 'emailNumber' in js_content or 'sha1' in js_content.lower():
                    sha1_hash = hashlib.sha1(EMAIL.encode()).hexdigest()
                    number = int(sha1_hash[:4], 16)
                    print(f"✓ Calculated from email: {{number}}")
                    return str(number)
            except:
                pass
    except Exception as e:
        print(f"⚠ Strategy 2 error: {{e}}")
    
    # Strategy 3: Inline JavaScript
    try:
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # Look for base64 (20+ chars of A-Za-z0-9+/=)
                b64_matches = re.findall(r'([A-Za-z0-9+/]{{20,}}={{0,2}})', script.string)
                for b64 in b64_matches:
                    try:
                        decoded = base64.b64decode(b64).decode('utf-8')
                        if 5 < len(decoded) < 100:
                            print(f"✓ Decoded: {{decoded}}")
                            return decoded.strip()
                    except:
                        pass
    except Exception as e:
        print(f"⚠ Strategy 3 error: {{e}}")
    
    # Strategy 4: Hidden inputs
    try:
        for inp in soup.find_all('input', {{'type': 'hidden'}}):
            val = inp.get('value', '')
            if val:
                print(f"✓ Hidden input: {{val}}")
                return val
    except Exception as e:
        print(f"⚠ Strategy 4 error: {{e}}")
    
    print(f"❌ No data found. HTML preview:\\n{{response.text[:500]}}")
    return None

def submit_answer(answer):
    payload = {{
        "email": EMAIL,
        "secret": SECRET,
        "url": ORIGINAL_URL,  # Quiz URL, NOT data URL!
        "answer": answer
    }}
    
    try:
        print(f"Submitting to: {{SUBMIT_URL}}")
        print(f"Payload: {{json.dumps(payload, indent=2)}}")
        response = requests.post(SUBMIT_URL, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        print(f"Response: {{result}}")
        return result
    except Exception as e:
        print(f"Submission error: {{e}}")
        return None

if __name__ == "__main__":
    print("="*60)
    print(f"BASE_URL: {{BASE_URL}}")
    print(f"DATA_URL: {{DATA_URL}}")
    print(f"SUBMIT_URL: {{SUBMIT_URL}}")
    print("="*60)
    
    answer = scrape_data()
    if answer:
        print(f"✅ Extracted: {{answer}}")
        result = submit_answer(answer)
    else:
        print("❌ Failed to extract answer")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 TEMPLATE 2: DATA PROCESSING (Use for calculations/transformations)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```python
import requests
import pandas as pd
import json

# Extract URLs and credentials
BASE_URL = "https://example.com"
DATA_URL = BASE_URL + "/data.csv"  # Or API endpoint
SUBMIT_URL = BASE_URL + "/submit"
EMAIL = "your@email.com"
SECRET = "your_secret"
ORIGINAL_URL = "https://example.com/quiz"

def process_data():
    """Fetch and process data"""
    try:
        # Fetch data (CSV, JSON, or API)
        response = requests.get(DATA_URL, timeout=30)
        response.raise_for_status()
        
        # Parse data
        if DATA_URL.endswith('.csv'):
            df = pd.read_csv(DATA_URL)
        elif DATA_URL.endswith('.json'):
            data = response.json()
            df = pd.DataFrame(data)
        else:
            data = response.json()  # Assume JSON API
            df = pd.DataFrame(data)
        
        # Perform calculations
        result = df['column_name'].mean()  # Example: calculate average
        # Or: result = df.groupby('category')['value'].sum()
        # Or: result = df.sort_values('score').head(5)
        
        print(f"✅ Calculated result: {{result}}")
        return str(result)
    except Exception as e:
        print(f"❌ Error: {{e}}")
        return None

def submit_answer(answer):
    payload = {{
        "email": EMAIL,
        "secret": SECRET,
        "url": ORIGINAL_URL,
        "answer": answer
    }}
    response = requests.post(SUBMIT_URL, json=payload)
    return response.json()

if __name__ == "__main__":
    answer = process_data()
    if answer:
        result = submit_answer(answer)
        print(f"✅ Result: {{result}}")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎨 TEMPLATE 3: VISUALIZATION (Use for chart/graph generation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```python
import requests
import matplotlib.pyplot as plt
import pandas as pd
import base64
from io import BytesIO

BASE_URL = "https://example.com"
DATA_URL = BASE_URL + "/data.csv"
SUBMIT_URL = BASE_URL + "/submit"
EMAIL = "your@email.com"
SECRET = "your_secret"
ORIGINAL_URL = "https://example.com/quiz"

def create_visualization():
    """Fetch data and create chart"""
    try:
        # Fetch and parse data
        df = pd.read_csv(DATA_URL)
        
        # Create visualization
        plt.figure(figsize=(10, 6))
        df.plot(kind='bar', x='category', y='value')
        plt.title('Data Visualization')
        plt.xlabel('Category')
        plt.ylabel('Value')
        
        # Save to buffer
        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        
        # Convert to base64
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        print(f"✅ Chart created")
        return img_base64
    except Exception as e:
        print(f"❌ Error: {{e}}")
        return None

def submit_answer(answer):
    payload = {{
        "email": EMAIL,
        "secret": SECRET,
        "url": ORIGINAL_URL,
        "answer": answer
    }}
    response = requests.post(SUBMIT_URL, json=payload)
    return response.json()

if __name__ == "__main__":
    chart = create_visualization()
    if chart:
        result = submit_answer(chart)
        print(f"✅ Result: {{result}}")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ FINAL REMINDER - ERROR HANDLING IS MANDATORY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your generated code MUST follow these rules:

1. **NEVER access attributes without None checks:**
   ```python
   elem = soup.find('div')
   if elem:  # ✅ Check first!
       text = elem.get_text()
   ```

2. **NEVER use split() with indexing directly:**
   ```python
   if '=' in text:  # ✅ Check first!
       parts = text.split('=')
       if len(parts) > 1:  # ✅ Verify length!
           value = parts[1]
   ```

3. **ALWAYS wrap strategies in try-except:**
   ```python
   try:
       # Strategy code here
   except Exception as e:
       print(f"⚠ Strategy failed: {{e}}")
       # Continue to next strategy
   ```

4. **ALWAYS have multiple fallback strategies** - don't rely on one!

5. **ALWAYS print what you're doing and what you found**

If your generated code crashes with "NoneType has no attribute" or 
"list index out of range", you FAILED to follow these rules!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Now generate your reasoning followed by the COMPLETE, ROBUST Python code."""
        
        messages = [
            {"role": "system", "content": action_prompt},
            {"role": "user", "content": "Execute the plan with explicit reasoning, then generate the complete solution code."}
        ]
        
        response = self.call_llm(messages, temperature=temperature)
        content = response['choices'][0]['message']['content']
        
        print(f"✅ Action phase completed")
        print(f"📝 Response length: {len(content)} characters")
        
        self.working_memory['last_action'] = content
        return content
    
    def reflect(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 3: REFLECT - Analyze results and determine next steps
        """
        print(f"\n{'='*70}")
        print(f"🔍 PHASE 3: AGENT REFLECTION")
        print(f"{'='*70}")
        
        success = execution_result.get('success', False)
        correct = execution_result.get('correct', False)
        error = execution_result.get('error')
        reason = execution_result.get('reason')
        
        if success and correct:
            print(f"✅ Task completed successfully!")
            print(f"✅ Answer was correct")
            return {
                "should_retry": False,
                "action": "success",
                "confidence": "high"
            }
        elif success and not correct:
            print(f"⚠️ Code executed but answer was incorrect")
            print(f"💡 Reason: {reason}")
            return {
                "should_retry": True,
                "action": "retry",
                "feedback": reason,
                "suggestion": "Analyze the error reason and adjust extraction or calculation logic",
                "confidence": "medium"
            }
        else:
            print(f"❌ Execution failed")
            print(f"❌ Error: {error}")
            return {
                "should_retry": True,
                "action": "retry",
                "feedback": error,
                "suggestion": "Fix syntax errors, import issues, or logic problems",
                "confidence": "low"
            }
    
    def solve_task(self, task_context: str, max_iterations: int = 3) -> str:
        """
        Main agent loop: Think → Act → Reflect
        Returns generated code
        """
        print(f"\n{'🤖'*35}")
        print(f"{'🤖'*15} AI AGENT ACTIVATED {'🤖'*15}")
        print(f"{'🤖'*35}")
        
        previous_attempts = []
        
        for iteration in range(max_iterations):
            self.iteration_count = iteration + 1
            print(f"\n{'━'*70}")
            print(f"📍 AGENT ITERATION {iteration + 1}/{max_iterations}")
            print(f"{'━'*70}")
            
            # Phase 1: Think - Strategic Planning
            plan = self.think("solve quiz task", task_context, previous_attempts)
            
            # Phase 2: Act - Execute Plan
            temperature = 0.4 + (iteration * 0.1)  # Increase creativity on retries
            action_result = self.act(plan, task_context, temperature)
            
            # Store in working memory
            self.working_memory[f'iteration_{iteration}'] = {
                'plan': plan,
                'action': action_result[:500],  # Store summary
                'temperature': temperature
            }
            
            # Return the generated code (reflection happens after execution in main loop)
            return action_result
        
        print(f"\n⚠️ Max iterations reached without solution")
        return None
    
    def get_memory_summary(self) -> str:
        """Get summary of agent's working memory"""
        summary = f"Agent Memory Summary:\n"
        summary += f"- Iterations completed: {self.iteration_count}\n"
        summary += f"- Memory items: {len(self.working_memory)}\n"
        if 'current_plan' in self.working_memory:
            plan = self.working_memory['current_plan']
            summary += f"- Current task type: {plan.get('task_type')}\n"
            summary += f"- Complexity: {plan.get('complexity')}\n"
        return summary
    
    def reset(self):
        """Reset agent state for new task"""
        self.conversation_history = []
        self.working_memory = {}
        self.iteration_count = 0
        print("🔄 Agent state reset")
