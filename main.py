from fastapi import FastAPI, Request ,BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import json
import os
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse
import requests

# Import LangChain Agent (with fallback to simple agent)
try:
    from langchain_agent import create_quiz_agent
    LANGCHAIN_AVAILABLE = True
    print("✅ LangChain agent loaded")
except ImportError as e:
    print(f"⚠️ LangChain not available: {e}")
    print("📦 Falling back to simple agent")
    from agent import AIAgent
    LANGCHAIN_AVAILABLE = False

app = FastAPI()
load_dotenv()

# Configuration
api_key = os.getenv("AI_PIPE_TOKEN_1")
EXPECTED_SECRET = os.getenv("SECRET_KEY", "23SHWEBGPT")
STUDENT_EMAIL = os.getenv("STUDENT_EMAIL", "23f2004891@ds.study.iitm.ac.in")

if not api_key:
    print("❌ WARNING: AI_PIPE_TOKEN_1 not found in environment!")

# Agent will be created per request, not globally

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
    
    # Create agent instance for this request
    try:
        if LANGCHAIN_AVAILABLE:
            print("🤖 Initializing LangChain Agent...")
            agent = create_quiz_agent(api_key)
        else:
            print("🤖 Initializing Simple Agent...")
            agent = AIAgent(api_key)
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        return {
            "success": False,
            "error": f"Agent initialization failed: {str(e)}"
        }
    
    # Retry loop for incorrect answers
    retry_attempt = 0
    previous_errors = []
    
    while retry_attempt <= max_retries:
        if retry_attempt > 0:
            print(f"\n🔄 Retry attempt {retry_attempt}/{max_retries}")
            # Reset agent for fresh attempt
            try:
                agent.reset()
            except:
                pass  # Simple agent might not have reset method
        
        # Prepare full context for the agent
        full_context = f"""
QUIZ PAGE CONTENT:
{question_md_content}

{additional_context}
"""
        
        if previous_errors:
            full_context += f"\n\n⚠️ PREVIOUS ATTEMPTS FAILED:\n"
            for i, error in enumerate(previous_errors, 1):
                full_context += f"\nAttempt {i}: {error}\n"
            full_context += "\n🔧 ANALYZE THE ERROR AND TRY A DIFFERENT APPROACH!\n"
        
        try:
            # Use agent to solve the quiz
            print(f"\n🤖 Invoking Agent to analyze and solve quiz...")
            if LANGCHAIN_AVAILABLE:
                message_text = agent.solve_quiz(full_context, max_attempts=1)
            else:
                message_text = agent.solve_task(full_context, max_iterations=1)
            
            if not message_text:
                return {
                    "success": False,
                    "error": "No response from LangChain Agent"
                }
            
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

prompt=r"""You are a quiz-solving expert who performs data extraction EXPLICITLY before writing code.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚫 CRITICAL: DO NOT USE CUSTOM MODULES IN GENERATED CODE!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your generated Python script will run in a CLEAN environment.
You can ONLY use standard libraries + requests + BeautifulSoup + pandas.

❌ FORBIDDEN: from LLMFunc import anything
❌ FORBIDDEN: LLMScraperHandler, custom scrapers
✅ ALLOWED: requests, BeautifulSoup, pandas, json, re, base64

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 YOUR WORKFLOW (MANDATORY):

STEP 1: 🔍 ANALYZE & EXTRACT THE DATA (Write this out!)
STEP 2: 📊 SHOW THE EXTRACTED DATA (Display what you found)
STEP 3: 💻 GENERATE PYTHON CODE (Only after extraction is complete)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 STEP 1: READ SECTION 1 FIRST - UNDERSTAND THE ACTUAL TASK

⚠️ **CRITICAL**: ALWAYS start by reading "📝 SECTION 1: Page Text Content" below!

**SECTION 1 contains the ACTUAL QUIZ INSTRUCTIONS in plain text.**
This is what the quiz is asking you to do. Everything else is just supporting data.

📖 **How to read SECTION 1:**

1. **Read the entire text in SECTION 1 carefully** - this is the actual question/task
2. **Identify key action words:** "scrape", "download", "calculate", "find", "decode", "extract"
3. **Note any URLs mentioned** - these might be relative URLs like "/data-page"
4. **Look for submission format** - often shown as JSON example: {{"key": "value"}}
5. **Understand what data is needed** - secret code? number? list? JSON object?

⚠️ **IMPORTANT LOGIC:**

- If SECTION 1 says "scrape [URL]" → You MUST scrape that URL (not look in SECTION 6!)
- If SECTION 1 says "decode the message" → Then check SECTION 6 for encoded data
- If SECTION 1 says "download [file]" → Check SECTION 2 for the file link
- If SECTION 1 says "calculate from table" → Check SECTION 3 for table data
- If SECTION 1 is just displaying text → The answer might BE that text

**Content Organization:**
- **SECTION 1 (Text Content)**: 🎯 THE ACTUAL QUESTION - READ THIS FIRST!
- **SECTION 2 (Links)**: URLs mentioned in the task (convert relative URLs to absolute!)
- **SECTION 3 (Tables)**: Pre-extracted tabular data
- **SECTION 6 (Raw HTML)**: Only check if SECTION 1 mentions "hidden data" or "decode"

**YOUR MANDATORY ANALYSIS FORMAT:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 TASK ANALYSIS (Based on SECTION 1):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP A: READ SECTION 1 COMPLETELY
[Copy the entire text from "📝 SECTION 1: Page Text Content" here]

Full text from SECTION 1:
"[paste the actual text]"

STEP B: INTERPRET THE TASK
What is it asking me to do?
- [ ] Scrape an external URL? Which URL? [identify from SECTION 1 text]
- [ ] Download a file? Which file? [look for .csv, .json, .txt mentioned]
- [ ] Decode/decrypt something? What data? [then check SECTION 6]
- [ ] Calculate from data? What calculation? [then check SECTION 3 or scrape]
- [ ] Simply read visible text? What text? [might already be in SECTION 1]

STEP C: IDENTIFY DATA SOURCE
Based on what SECTION 1 is asking:

Primary source: [Where will I get the data?]
- If SECTION 1 says "scrape /some-url" → 
  ✓ Need to scrape: https://[base-domain]/some-url (check SECTION 2 for full URL)
- If SECTION 1 says "the secret is hidden" → 
  ✓ Check SECTION 6 for Base64, JS variables, hidden inputs
- If SECTION 1 says "analyze the table" → 
  ✓ Check SECTION 3 for table data
- If SECTION 1 shows the data directly → 
  ✓ The answer might be visible in SECTION 1 itself!

STEP D: SCRAPING STRATEGY
Do I need to scrape? [YES/NO - based on SECTION 1's instruction]

If YES:
- Target URL (from SECTION 2 or mentioned in SECTION 1): [full URL]
- URL is relative? Convert to absolute: https://[domain][path]
- What to extract from that URL: [specific element, pattern, or data]
- Tools: requests.get() + BeautifulSoup

If NO:
- Data location: [SECTION 3 tables / SECTION 6 hidden / SECTION 1 visible]
- Extraction method: [pandas / regex / base64.decode / direct copy]

STEP E: EXPECTED OUTPUT FORMAT
Based on SECTION 1, what format should the answer be?
[Look for JSON examples in SECTION 1 - copy the structure]

Example from SECTION 1:
{{"email": "...", "answer": "..."}}  ← Use this exact structure!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**NOW PERFORM THE ACTUAL EXTRACTION:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔎 EXTRACTION PROCESS (Follow what SECTION 1 asks!):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXECUTION BASED ON SECTION 1 INSTRUCTION:

[SCENARIO A: If SECTION 1 says "Scrape [URL]" or "Visit [URL]"]

Step 1: Identified target URL from SECTION 1
   - Mentioned URL: /demo-scrape-data?email=...
   - From SECTION 2, full URL: https://example.com/demo-scrape-data?email=...
   - Note: Relative URLs must be converted to absolute!

Step 2: Scraping the target URL
   - Executing: requests.get("https://example.com/demo-scrape-data?email=...")
   - Status: 200 OK
   - Response received

Step 3: Parsing response
   - Content type: [HTML / JSON / Text]
   - Using: BeautifulSoup if HTML, json.loads() if JSON
   - Looking for: [what SECTION 1 asked - "secret code", "data", etc.]

Step 4: Extracting requested data
   - Found element: <div id="secret">ABC123</div>
   - Extracted value: "ABC123"
   - This is what SECTION 1 asked for!

[SCENARIO B: If SECTION 1 says "Decode" or mentions "hidden"]

Step 1: Checking SECTION 6 as directed by SECTION 1
   - Looking for: Base64 patterns, JS variables with encoded data
   - Found: const code = "SGVsbG8..."
   
Step 2: Decoding
   - Method: base64.b64decode()
   - Result: "Hello World"

[SCENARIO C: If SECTION 1 says "Calculate" or "Analyze table"]

Step 1: Checking SECTION 3 for table data
   - Table found: Yes/No
   - Columns: [list columns]
   
Step 2: Processing
   - Calculation: sum/mean/count as requested in SECTION 1
   - Result: 1500

[SCENARIO D: If SECTION 1 displays the answer directly]

Step 1: Reading SECTION 1 text
   - The text in SECTION 1 IS the answer!
   - Answer: [copy from SECTION 1]

✅ FINAL EXTRACTED DATA (answers what SECTION 1 asked):
{{"key": "value"}}  ← This matches what SECTION 1 requested

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 STEP 2: VALIDATE YOUR EXTRACTION

**Confirm the data matches the question requirements:**

```
✅ VALIDATION CHECKLIST:
☐ Does this data answer the question from SECTION 1?
☐ Is the format correct (JSON object, number, string, list)?
☐ Did I scrape the correct URL if external scraping was needed?
☐ Is the data complete and accurate?

FINAL ANSWER TO SUBMIT:
{{"key": "value"}}  ← [Show the exact JSON that will be submitted]
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💻 STEP 3: GENERATE PYTHON CODE

**NOW write the Python script that:**
1. Performs the scraping/extraction you analyzed above
2. Processes the data
3. Formats as JSON
4. Submits to the endpoint

⚠️ **IF SCRAPING EXTERNAL URL IS REQUIRED:**
Your code MUST include requests.get() to scrape the target URL!

Example structure when scraping is needed:
```python
import requests
from bs4 import BeautifulSoup

# Scrape the external URL (identified in analysis)
target_url = "https://example.com/data"
response = requests.get(target_url, headers={{"User-Agent": "Mozilla/5.0"}})
soup = BeautifulSoup(response.text, 'html.parser')

# Extract the data (as identified in extraction process)
data = soup.find('div', {{'id': 'secret'}}).get_text().strip()

# Submit
answer = {{"secret": data}}
# ... submission code
```

Only NOW, after extraction, write the Python code that:
1. Uses the extracted data (hardcode it if already known!)
2. Performs any required computation
3. Formats as JSON
4. Submits to the endpoint

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 QUICK STRATEGY FOR DATA LOCATION:
1. Read SECTION 1 → Understand the task
2. Find data source:
   - Visible answer? → SECTION 1 (Text Content)
   - Hidden data? → SECTION 6 (Raw HTML - JS vars, hidden inputs, Base64)
   - External file/URL? → SECTION 2 (Links)
   - Table data? → SECTION 3 (Tables)
3. Extract EXPLICITLY (write it out!) → Format as JSON → Generate code

⚡ DATA EXTRACTION METHODS:

**Method 1: Extract from Current Page (FASTEST - No external fetch needed)**
```python
from bs4 import BeautifulSoup
import re, json, base64

# ALWAYS check SECTION 1 (Text Content) first - answer might be visible!
# THEN check SECTION 6 (Raw HTML) for hidden data

html = "..."  # Copy from SECTION 6: Raw HTML Source Code
soup = BeautifulSoup(html, 'html.parser')

# Pattern A: Base64 Encoded Data (COMMON!)
# Look for: long alphanumeric strings, often in <pre>, <code>, or script tags
base64_patterns = re.findall(r'[A-Za-z0-9+/]{{40,}}={{{0,2}}}', html)
for encoded in base64_patterns:
    try:
        decoded = base64.b64decode(encoded).decode('utf-8')
        print(f"Base64 decoded: {{decoded[:100]}}")
        # Check if decoded text contains JSON or answer
        if '{{' in decoded:
            data = json.loads(decoded)
    except: pass

# Pattern B: JavaScript Variables (var/const/let)
script_tags = soup.find_all('script')
for script in script_tags:
    if script.string:
        # Extract JSON objects
        json_matches = re.findall(r'(?:var|const|let)\s+\w+\s*=\s*(\{[^;]+\});?', script.string, re.DOTALL)
        for match in json_matches:
            try:
                data = json.loads(match)
                print(f"Found JS data: {{data}}")
            except: pass
        
        # Extract simple values
        var_matches = re.findall(r'(?:var|const|let)\s+(\w+)\s*=\s*["\']([^"\']+)["\']', script.string)
        for var_name, var_value in var_matches:
            print(f"{{var_name}} = {{var_value}}")

# Pattern C: Hidden Form Inputs
hidden_inputs = soup.find_all('input', type='hidden')
for inp in hidden_inputs:
    print(f"Hidden: {{inp.get('name')}} = {{inp.get('value')}}")

# Pattern D: Data Attributes (data-*, id, value)
for elem in soup.find_all(attrs={{"data-secret": True}}):
    print(f"Data attr: {{elem.get('data-secret')}}")

# Pattern E: JSON in <script type="application/json">
json_scripts = soup.find_all('script', type='application/json')
for script in json_scripts:
    data = json.loads(script.string)
    print(f"JSON script: {{data}}")
```

**Method 2: Simple Direct Downloads (CSV/JSON/API endpoints)**
```python
import requests, pandas as pd
from io import StringIO

# For JSON APIs (check SECTION 2: Links for .json URLs)
response = requests.get("url.json", headers={{"User-Agent": "Mozilla/5.0"}})
data = response.json()

# For CSV files (check SECTION 2: Links for .csv URLs)
csv_response = requests.get("url.csv", headers={{"User-Agent": "Mozilla/5.0"}})
df = pd.read_csv(StringIO(csv_response.text))
result = df.to_dict('records')  # or df.sum(), df.mean(), etc.

# For plain text/data files
text_response = requests.get("url.txt", headers={{"User-Agent": "Mozilla/5.0"}})
text_data = text_response.text
```

**Method 3: Scrape External Pages (Use standard scraping - NO LLMScraperHandler!)**

⚠️ CRITICAL: DO NOT use LLMScraperHandler or any custom scrapers!
Use standard Python libraries: requests, BeautifulSoup, selenium (if needed)

```python
import requests
from bs4 import BeautifulSoup
import re
import json

def scrape_url(url: str):
    # Scrape any external URL using standard requests + BeautifulSoup.
    # DO NOT use LLMScraperHandler - it's not available in the generated script!
    print(f"🌐 Scraping: {{url}}")
    
    headers = {{
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        
        print(f"✅ Successfully scraped {{url}}")
        return {{"html": html_content, "soup": soup, "text": soup.get_text()}}
        
    except Exception as e:
        print(f"❌ Scraping failed: {{e}}")
        return None

# EXAMPLE 1: Scrape and extract data
scraped = scrape_url("https://example.com/data")
if scraped:
    soup = scraped['soup']
    
    # Extract specific elements
    secret_code = soup.find('div', {{'id': 'secret'}})
    if secret_code:
        code = secret_code.get_text().strip()
        print(f"Found code: {{code}}")
    
    # Extract from table
    table = soup.find('table')
    if table:
        rows = table.find_all('tr')
        data = []
        for row in rows[1:]:  # Skip header
            cols = [col.get_text().strip() for col in row.find_all('td')]
            data.append(cols)
        print(f"Table data: {{data}}")
    
    # Extract Base64 from scraped page
    base64_pattern = re.findall(r'[A-Za-z0-9+/]{{40,}}={{{0,2}}}', scraped['html'])
    if base64_pattern:
        import base64
        decoded = base64.b64decode(base64_pattern[0]).decode('utf-8')
        print(f"Decoded: {{decoded}}")

# EXAMPLE 2: Scrape JSON/API endpoint
api_response = requests.get("https://example.com/api/data", headers=headers)
data = api_response.json()
print(f"API data: {{data}}")

# EXAMPLE 3: Download and parse CSV
import pandas as pd
from io import StringIO

csv_response = requests.get("https://example.com/data.csv", headers=headers)
df = pd.read_csv(StringIO(csv_response.text))
result = df.to_dict('records')
print(f"CSV data: {{result}}")
```

**For JavaScript-heavy pages (if simple scraping fails):**
```python
# Option 1: Try to extract data from script tags
scripts = soup.find_all('script')
for script in scripts:
    if script.string and 'data' in script.string:
        # Look for JSON data in JavaScript
        json_match = re.search(r'var data = (\{{.*?\}});', script.string, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(1))
            print(f"Found JS data: {{data}}")

# Option 2: Use selenium for dynamic content (only if absolutely necessary)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=chrome_options)
driver.get("https://example.com")
page_source = driver.page_source
driver.quit()

soup = BeautifulSoup(page_source, 'html.parser')
# ... extract data from soup
```

⚠️ CRITICAL DECISION TREE:
1. **Check SECTION 1 (Text Content)** → Answer visible? DONE!
2. **Check SECTION 6 (Raw HTML)** → Look for Base64, JS vars, hidden inputs → DONE!
3. **Check SECTION 2 (Links)** → CSV/JSON file? Download directly → DONE!
4. **Task says "scrape another page"?** → Use Method 3 (AI scraping)
5. **Still stuck?** → Re-read SECTION 1, the answer is probably there!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 COMPLETE EXAMPLES - FOLLOW THESE PATTERNS:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLE 1: SCRAPING WITH RELATIVE URL (Most Common!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**SECTION 1 shows:**
```
Scrape /demo-scrape-data?email=23f2003481@ds.study.iitm.ac.in (relative to this page).
Get the secret code from this page.
POST the secret code back to /submit
{{
  "email": "23f2003481@ds.study.iitm.ac.in",
  "secret": "your secret",
  "answer": "the secret code you scraped"
}}
```

**SECTION 2 shows:** 
- Link: /demo-scrape-data?email=... → https://tds-llm-analysis.s-anand.net/demo-scrape-data?email=...
- Submit endpoint: /submit → https://tds-llm-analysis.s-anand.net/submit

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 TASK ANALYSIS (Based on SECTION 1):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP A: READ SECTION 1 COMPLETELY
Full text from SECTION 1:
"Scrape /demo-scrape-data?email=23f2003481@ds.study.iitm.ac.in (relative to this page).
Get the secret code from this page.
POST the secret code back to /submit
{{
  "email": "23f2003481@ds.study.iitm.ac.in",
  "secret": "your secret",
  "answer": "the secret code you scraped"
}}"

STEP B: INTERPRET THE TASK
What is it asking?
- ✓ "Scrape /demo-scrape-data..." → I need to SCRAPE a URL!
- ✓ "Get the secret code" → Find a secret code on that scraped page
- ✓ "POST... to /submit" → Submit endpoint is /submit

STEP C: IDENTIFY DATA SOURCE
- SECTION 1 says: "Scrape /demo-scrape-data?email=..."
- This is a RELATIVE URL! Need to convert to absolute.
- From URL Parameters: Base domain is https://tds-llm-analysis.s-anand.net
- From SECTION 2: Full URL is https://tds-llm-analysis.s-anand.net/demo-scrape-data?email=...

STEP D: SCRAPING STRATEGY
Scraping required: YES!
- Target URL: https://tds-llm-analysis.s-anand.net/demo-scrape-data?email=23f2003481@ds.study.iitm.ac.in
- What to find: "secret code" (look for text/element containing this)
- Tools: requests.get() + BeautifulSoup

STEP E: EXPECTED OUTPUT FORMAT
From SECTION 1, the JSON structure:
{{
  "email": "23f2003481@ds.study.iitm.ac.in",
  "secret": "your secret",
  "answer": "the secret code you scraped"
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔎 EXTRACTION PROCESS (Following SECTION 1 instruction):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Scraping the URL mentioned in SECTION 1
   - Target: https://tds-llm-analysis.s-anand.net/demo-scrape-data?email=23f2003481@ds.study.iitm.ac.in
   - Using: requests.get() with User-Agent
   - Status: 200 OK

Step 2: Parsing HTML response
   - Using: BeautifulSoup(html, 'html.parser')
   - Looking for: "secret code" in text or specific element
   - Found: <div id="secret-code">ABC123XYZ</div>

Step 3: Extracting the secret code
   - Raw data: "ABC123XYZ"
   - This is what SECTION 1 asked for!

✅ FINAL EXTRACTED DATA:
{{
  "email": "23f2003481@ds.study.iitm.ac.in",
  "secret": "your secret",  # from URL params if needed
  "answer": "ABC123XYZ"  # the scraped secret code
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Python code (implements what SECTION 1 asked):**

```python
import requests
from bs4 import BeautifulSoup
import json

# Step 1: Scrape the URL specified in SECTION 1
# SECTION 1 said: "Scrape /demo-scrape-data?email=..."
# SECTION 2 gives full URL: https://tds-llm-analysis.s-anand.net/demo-scrape-data?email=...
scrape_url = "https://tds-llm-analysis.s-anand.net/demo-scrape-data?email=23f2003481@ds.study.iitm.ac.in"

print(f"🌐 Scraping as instructed by SECTION 1: {{scrape_url}}")
response = requests.get(scrape_url, headers={{"User-Agent": "Mozilla/5.0"}})
print(f"✅ Response status: {{response.status_code}}")

# Step 2: Parse and extract secret code (as SECTION 1 asked for)
soup = BeautifulSoup(response.text, 'html.parser')

# Look for secret code - try multiple patterns
secret_code = None

# Try finding by id/class
if soup.find(id="secret-code"):
    secret_code = soup.find(id="secret-code").get_text().strip()
elif soup.find(class_="secret"):
    secret_code = soup.find(class_="secret").get_text().strip()
else:
    # Look for any element with "secret" in text
    for elem in soup.find_all(['div', 'span', 'p', 'pre']):
        if 'secret' in elem.get_text().lower():
            secret_code = elem.get_text().strip()
            break

print(f"🔑 Found secret code: {{secret_code}}")

# Step 3: Submit in the format shown in SECTION 1
# SECTION 1 showed this format:
# {{
#   "email": "23f2003481@ds.study.iitm.ac.in",
#   "secret": "your secret",
#   "answer": "the secret code you scraped"
# }}

answer = {{
    "email": "23f2003481@ds.study.iitm.ac.in",
    "secret": "your secret",  # Use actual secret if known
    "url": scrape_url,
    "answer": secret_code
}}

# SECTION 1 said: "POST... to /submit"
# SECTION 2 gives full URL: https://tds-llm-analysis.s-anand.net/submit
submit_url = "https://tds-llm-analysis.s-anand.net/submit"

print(f"📤 Submitting to: {{submit_url}}")
print(f"📦 Payload: {{json.dumps(answer, indent=2)}}")

submit_response = requests.post(
    submit_url,
    json=answer,
    headers={{"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}}
)

print(f"📥 Submission response: {{submit_response.json()}}")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLE 2: BASE64 DECODING (NO EXTERNAL SCRAPING)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**SECTION 1 shows:** "Decode the hidden message and submit it"
**SECTION 6 shows:** <pre id="secret">SGVsbG8gV29ybGQ=</pre>

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 TASK ANALYSIS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. QUESTION: "Decode the hidden message"

2. DATA LOCATION STRATEGY:
   ☑ Hidden on current page → Check SECTION 6 for Base64

3. SCRAPING REQUIRED: NO (data is on current page)

4. EXTRACTION METHOD:
   - Find Base64 pattern in SECTION 6: <pre id="secret">
   - Decode using base64.b64decode()

5. EXPECTED ANSWER FORMAT: {{"message": "decoded text"}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔎 EXTRACTION PROCESS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Found in SECTION 6 Raw HTML:
   <pre id="secret">SGVsbG8gV29ybGQ=</pre>

Step 2: Decoding Base64...
   - Input: SGVsbG8gV29ybGQ=
   - Decoded: Hello World

✅ FINAL EXTRACTED DATA: {{"message": "Hello World"}}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Python code:**

```python
import requests
import base64
import json

# The Base64 string (already identified from SECTION 6)
encoded = "SGVsbG8gV29ybGQ="
decoded_message = base64.b64decode(encoded).decode('utf-8')
print(f"Decoded message: {{decoded_message}}")

# Submit
answer = {{"message": decoded_message}}
submit_response = requests.post(
    "https://quiz.example.com/submit",
    json=answer,
    headers={{"User-Agent": "Mozilla/5.0"}}
)

print(f"📥 Submission response: {{submit_response.json()}}")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLE 3: DOWNLOAD CSV AND CALCULATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**SECTION 1 shows:** "Download the sales data and calculate total revenue"
**SECTION 2 shows:** Link to https://example.com/data/sales.csv

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 TASK ANALYSIS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. QUESTION: "Calculate total revenue from sales data"

2. DATA LOCATION STRATEGY:
   ☑ Need to download file → https://example.com/data/sales.csv

3. SCRAPING REQUIRED: YES (downloading CSV file)
   - Target URL: https://example.com/data/sales.csv
   - What to find: Revenue column
   - Method: requests.get() + pandas

4. EXTRACTION METHOD:
   - Download CSV from URL
   - Parse with pandas
   - Sum the 'revenue' column

5. EXPECTED ANSWER FORMAT: {{"total_revenue": 15000}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔎 EXTRACTION PROCESS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Downloading https://example.com/data/sales.csv...
   - Status: Success

Step 2: Parsing with pandas...
   - Columns: date, product, revenue
   - Rows: 50 records

Step 3: Computing total...
   - Sum of 'revenue' column: 15000

✅ FINAL EXTRACTED DATA: {{"total_revenue": 15000}}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Python code:**

```python
import requests
import pandas as pd
from io import StringIO
import json

# Download CSV (as identified)
csv_url = "https://example.com/data/sales.csv"
response = requests.get(csv_url, headers={{"User-Agent": "Mozilla/5.0"}})
df = pd.read_csv(StringIO(response.text))

# Calculate total revenue (as identified)
total_revenue = df['revenue'].sum()
print(f"Total revenue: {{total_revenue}}")

# Submit
answer = {{"total_revenue": int(total_revenue)}}
submit_response = requests.post(
    "https://quiz.example.com/submit",
    json=answer,
    headers={{"User-Agent": "Mozilla/5.0"}}
)

print(f"📥 Submission response: {{submit_response.json()}}")

print(f"📥 Submission response: {{response.json()}}")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎓 COMPLETE SCRAPING EXAMPLES:

**Example 1: Scrape external page and extract specific data**

```
ANALYSIS:
1. Task: Scrape https://example.com/secret and get the hidden code
2. Data Location: External URL in SECTION 2 (Links)
3. Extraction Method: Scrape with requests, parse HTML, find code element
4. Expected Format: String value

EXTRACTION:
Scraping https://example.com/secret...

import requests
from bs4 import BeautifulSoup

url = "https://example.com/secret"
response = requests.get(url, headers={{"User-Agent": "Mozilla/5.0"}})
soup = BeautifulSoup(response.text, 'html.parser')

# Found: <div id="code">ABC123</div>
code_elem = soup.find('div', {{'id': 'code'}})
code = code_elem.get_text().strip()

✅ DATA EXTRACTED:
- Type: String
- Content: "ABC123"
- Validation: Found in div#code element
```

**NOW generate the Python code:**

```python
import requests
from bs4 import BeautifulSoup

# Scrape external URL
url = "https://example.com/secret"
response = requests.get(url, headers={{"User-Agent": "Mozilla/5.0"}})
soup = BeautifulSoup(response.text, 'html.parser')

# Extract the code (already identified above)
code = soup.find('div', {{'id': 'code'}}).get_text().strip()
print(f"Found code: {{code}}")

# Submit
answer = {{"code": code}}
submit_response = requests.post(
    "https://quiz.com/submit",
    json=answer,
    headers={{"User-Agent": "Mozilla/5.0"}}
)

print(f"📥 Submission response: {{submit_response.json()}}")
```

**Example 2: Download CSV and calculate statistics**

```
ANALYSIS:
1. Task: Download data.csv and calculate total sales
2. Data Location: CSV file URL in SECTION 2 (Links): https://example.com/sales.csv
3. Extraction Method: Download CSV with requests, parse with pandas, sum the 'sales' column
4. Expected Format: Integer (total sum)

EXTRACTION:
Downloading https://example.com/sales.csv...

import requests
import pandas as pd
from io import StringIO

response = requests.get("https://example.com/sales.csv")
df = pd.read_csv(StringIO(response.text))

# CSV contains columns: date, product, sales
# Rows:
#   2024-01-01, Product A, 100
#   2024-01-02, Product B, 250
#   2024-01-03, Product A, 150

total_sales = df['sales'].sum()  # = 500

✅ DATA EXTRACTED:
- Type: Integer
- Content: 500
- Validation: Sum of all values in 'sales' column
```

**NOW generate the Python code:**

```python
import requests
import pandas as pd
from io import StringIO

# Download and parse CSV (already analyzed above)
csv_url = "https://example.com/sales.csv"
response = requests.get(csv_url, headers={{"User-Agent": "Mozilla/5.0"}})
df = pd.read_csv(StringIO(response.text))

# Calculate total (identified from analysis)
total_sales = df['sales'].sum()
print(f"Total sales: {{total_sales}}")

# Submit
answer = {{"total": total_sales}}
submit_response = requests.post(
    "https://quiz.com/submit",
    json=answer,
    headers={{"User-Agent": "Mozilla/5.0"}}
)

print(f"📥 Submission response: {{submit_response.json()}}")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**EXTRACTION PATTERNS REFERENCE:**

```python
from bs4 import BeautifulSoup
import re, json, base64

# ALWAYS START HERE: Read the task in SECTION 1 carefully!
# The answer format and location are usually explained clearly

html = "..."  # From SECTION 6: Raw HTML Source Code

# ═══════════════════════════════════════════════════════════
# PATTERN 1: BASE64 ENCODED DATA (Very Common!)
# ═══════════════════════════════════════════════════════════
# Looks like: "SGVsbG8gV29ybGQ=" or longer alphanumeric strings
# Often in: <pre>, <code>, script tags, or as text content

# Find all base64-like strings (40+ chars)
base64_candidates = re.findall(r'[A-Za-z0-9+/]{{40,}}={{{0,2}}}', html)
for encoded_text in base64_candidates:
    try:
        decoded = base64.b64decode(encoded_text).decode('utf-8')
        print(f"Decoded Base64: {{decoded}}")
        
        # Check if decoded text is JSON
        if decoded.strip().startswith('{{'):
            try:
                data = json.loads(decoded)
                print(f"Base64 contained JSON: {{data}}")
            except: pass
            
        # Check for secret/answer keywords
        if 'secret' in decoded.lower() or 'answer' in decoded.lower():
            print(f"Found potential answer in base64: {{decoded}}")
    except: 
        continue

# ═══════════════════════════════════════════════════════════
# PATTERN 2: JAVASCRIPT VARIABLES (var/const/let)
# ═══════════════════════════════════════════════════════════
soup = BeautifulSoup(html, 'html.parser')
scripts = soup.find_all('script')
for script in scripts:
    if not script.string: continue
    
    # Extract JSON objects: var data = {{"key": "value"}};
    json_objects = re.findall(r'(?:var|const|let)\s+\w+\s*=\s*(\{[^;]+\});?', script.string, re.DOTALL)
    for json_str in json_objects:
        try:
            data = json.loads(json_str)
            print(f"JS Object found: {{data}}")
        except: pass
    
    # Extract string values: var secret = "value123";
    string_vars = re.findall(r'(?:var|const|let)\s+(\w+)\s*=\s*["\']([^"\']+)["\']', script.string)
    for var_name, var_value in string_vars:
        print(f"JS String: {{var_name}} = {{var_value}}")
    
    # Extract number values: const answer = 42;
    num_vars = re.findall(r'(?:var|const|let)\s+(\w+)\s*=\s*(\d+\.?\d*)', script.string)
    for var_name, var_value in num_vars:
        print(f"JS Number: {{var_name}} = {{var_value}}")

# ═══════════════════════════════════════════════════════════
# PATTERN 3: HIDDEN FORM INPUTS
# ═══════════════════════════════════════════════════════════
hidden_inputs = soup.find_all('input', type='hidden')
for inp in hidden_inputs:
    name = inp.get('name') or inp.get('id')
    value = inp.get('value')
    print(f"Hidden input: {{name}} = {{value}}")

# ═══════════════════════════════════════════════════════════
# PATTERN 4: DATA ATTRIBUTES (data-*, custom attributes)
# ═══════════════════════════════════════════════════════════
# Look for: <div data-secret="xyz">, <span id="answer">xyz</span>
for elem in soup.find_all(attrs={{lambda x: x and (x.startswith('data-') or x in ['secret', 'answer', 'code'])}}):
    for attr, value in elem.attrs.items():
        if attr.startswith('data-') or attr in ['secret', 'answer', 'code']:
            print(f"Attribute: {{attr}} = {{value}}")

# ═══════════════════════════════════════════════════════════
# PATTERN 5: JSON IN SCRIPT TAGS
# ═══════════════════════════════════════════════════════════
json_scripts = soup.find_all('script', type='application/json')
for script in json_scripts:
    try:
        data = json.loads(script.string)
        print(f"JSON script tag: {{data}}")
    except: pass

# ═══════════════════════════════════════════════════════════
# PATTERN 6: TEXT CONTENT WITH KEYWORDS
# ═══════════════════════════════════════════════════════════
# Sometimes answer is in plain text with markers
for keyword in ['secret:', 'answer:', 'code:', 'result:']:
    if keyword in html.lower():
        # Extract text after keyword
        match = re.search(rf'{keyword}\s*([^\s<]+)', html, re.I)
        if match:
            print(f"Found {{keyword}} {{match.group(1)}}")
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

⚠️⚠️⚠️ CRITICAL INSTRUCTIONS ⚠️⚠️⚠️

**DO NOT use LLMFunc, LLMScraperHandler, or any custom modules!**
**These are NOT available in the generated script environment!**

🎯 **YOUR MISSION:**

Read the QUESTION in SECTION 1 below carefully. It will tell you exactly what to do.
Common patterns:
- "Visit the page at [URL] and find..." → SCRAPE that URL!
- "Download the file from [URL] and calculate..." → DOWNLOAD and process!
- "Decode the hidden message..." → Look in SECTION 6 for Base64/encoded data!
- "Find the secret in the linked page..." → Check SECTION 2 for the link, then SCRAPE it!

Now generate a complete, executable Python script following this workflow:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: 🔍 WRITE YOUR ANALYSIS FIRST (mandatory format shown in examples)
   
   📋 TASK ANALYSIS:
   1. QUESTION: [Copy exact question from SECTION 1]
   2. DATA LOCATION STRATEGY: [Where is the data?]
   3. SCRAPING REQUIRED: [YES/NO - if YES, which URL?]
   4. EXTRACTION METHOD: [Step by step plan]
   5. EXPECTED ANSWER FORMAT: [JSON structure]

   🔎 EXTRACTION PROCESS:
   [Perform the actual extraction - scrape URLs, decode data, etc.]
   [Show what you found]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 2: 📊 VALIDATE YOUR EXTRACTION
   
   ✅ VALIDATION CHECKLIST:
   ☐ Does this data answer the question?
   ☐ Is the format correct?
   ☐ Did I scrape the correct URL if needed?
   
   FINAL ANSWER: {{"key": "value"}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 3: 💻 GENERATE COMPLETE PYTHON CODE

Requirements:
   ✅ Use ONLY: requests, BeautifulSoup, pandas, re, json, base64
   ✅ If scraping needed: Include requests.get() with the target URL
   ✅ Extract data using the method identified in your analysis
   ✅ Format answer as JSON
   ✅ Submit with proper print statements
   ✅ Handle errors gracefully

🚫 **BANNED IMPORTS:**
```python
from LLMFunc import LLMScraperHandler  # ❌ NOT AVAILABLE!
from LLMFunc import anything  # ❌ NOT AVAILABLE!
import asyncio  # ❌ Only if absolutely necessary
```

✅ **ALLOWED IMPORTS:**
```python
import requests  # ✅ For HTTP requests and scraping
from bs4 import BeautifulSoup  # ✅ For HTML parsing
import pandas as pd  # ✅ For CSV/data processing
import re  # ✅ For regex patterns
import json  # ✅ For JSON handling
import base64  # ✅ For Base64 decoding
from io import StringIO  # ✅ For CSV parsing
```

📝 **YOUR CODE STRUCTURE:**
```python
import requests
from bs4 import BeautifulSoup
import json
# ... other standard imports

# If external scraping is needed:
url = "https://example.com/data"
response = requests.get(url, headers={{"User-Agent": "Mozilla/5.0"}})
soup = BeautifulSoup(response.text, 'html.parser')

# Extract data (use examples above as reference)
data = soup.find('div', {{'id': 'secret'}}).get_text()

# Submit
answer = {{"key": data}}
submit_response = requests.post(
    submission_url,
    json=answer,
    headers={{"User-Agent": "Mozilla/5.0"}}
)

print(f"📥 Submission response: {{submit_response.json()}}")
```

Write the COMPLETE code with NO placeholders. Use standard scraping libraries only!"""


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