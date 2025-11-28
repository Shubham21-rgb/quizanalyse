"""
Simple AI Agent Architecture for Quiz Solving
Implements Think → Act → Reflect paradigm with tool usage
No LangChain dependencies - pure Python implementation
"""

import requests
import json
import os
import base64
import re
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
import pandas as pd
from io import StringIO


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
            return {"error": f"LLM call failed: {str(e)}"}
    
    def think(self, task: str, context: str, previous_attempts: List[str] = None) -> Dict[str, Any]:
        """
        Phase 1: THINK - Analyze task and create strategic plan
        """
        print(f"\\n{'='*70}")
        print(f"🧠 PHASE 1: AGENT THINKING")
        print(f"{'='*70}")
        
        error_context = ""
        if previous_attempts:
            error_context = "\\n\\nPREVIOUS FAILED ATTEMPTS:\\n"
            for i, attempt in enumerate(previous_attempts, 1):
                error_context += f"Attempt {i}: {attempt}\\n"
        
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

🎵 **AUDIO TASK SPECIAL ANALYSIS:**
   - If SECTION 5 contains Audio Files & Transcriptions, READ THEM!
   - Audio transcriptions provide CRITICAL task instructions
   - Example: "you need to download the csv file provided pick the first column and add all values greater than or equal to the cutoff value"
   - Combine SECTION 1 text + audio transcriptions for complete task understanding
   - Audio often clarifies the specific calculation or data processing required

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
            if "error" in response:
                return {"error": response["error"]}
            
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Extract JSON from response
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                return {"error": "No JSON plan found in LLM response"}
            
            plan_json = content[json_start:json_end]
            plan = json.loads(plan_json)
            
            print(f"✅ Strategic plan created:")
            print(f"   Task: {plan.get('task_understanding', 'Unknown')}")
            print(f"   Type: {plan.get('task_type', 'Unknown')}")
            print(f"   Complexity: {plan.get('complexity', 'Unknown')}")
            
            return plan
            
        except Exception as e:
            return {"error": f"Failed to parse plan: {str(e)}"}
    
    def act(self, plan: Dict[str, Any], context: str, temperature: float = 0.4) -> str:
        """
        Phase 2: ACT - Execute the plan and generate solution code
        """
        print(f"\\n{'='*70}")
        print(f"🎯 PHASE 2: AGENT ACTION")
        print(f"{'='*70}")
        
        # Create system prompt for code generation
        system_prompt = f"""You are a quiz-solving expert who performs data extraction EXPLICITLY before writing code.

CURRENT PLAN:
{json.dumps(plan, indent=2)}

🔍 STEP 1: READ SECTION 1 + AUDIO TRANSCRIPTIONS - UNDERSTAND THE ACTUAL TASK

⚠️ **CRITICAL**: ALWAYS start by reading "📝 SECTION 1: Page Text Content" below!

🎵 **AUDIO TASKS**: Also check "🎵 SECTION 5: Audio Files & Transcriptions"!
   - Audio transcriptions contain detailed task instructions
   - Example: "you need to download the csv file provided pick the first column and add all values greater than or equal to the cutoff value"
   - Combine SECTION 1 + SECTION 5 for complete understanding

**SECTION 1 contains the ACTUAL QUIZ INSTRUCTIONS in plain text.**
**SECTION 5 contains audio instructions that clarify what to calculate/process.**
This is what the quiz is asking you to do. Everything else is just supporting data.

📋 YOUR WORKFLOW (MANDATORY):

STEP 1: 🔍 ANALYZE & EXTRACT THE DATA (Write this out!)
STEP 2: 📊 SHOW THE EXTRACTED DATA (Display what you found)
STEP 3: 💻 GENERATE PYTHON CODE (Only after extraction is complete)

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

STEP 1: 🔍 WRITE YOUR ANALYSIS FIRST (mandatory format)
   
   📋 TASK ANALYSIS:
   1. QUESTION: [Copy exact question from SECTION 1]
   2. DATA LOCATION STRATEGY: [Where is the data?]
   3. SCRAPING REQUIRED: [YES/NO - if YES, which URL?]
   4. EXTRACTION METHOD: [Step by step plan]
   5. EXPECTED ANSWER FORMAT: [JSON structure]

   🔎 EXTRACTION PROCESS:
   [Perform the actual extraction - scrape URLs, decode data, etc.]
   [Show what you found]

STEP 2: 📊 VALIDATE YOUR EXTRACTION
   
   ✅ VALIDATION CHECKLIST:
   ☐ Does this data answer the question?
   ☐ Is the format correct?
   ☐ Did I scrape the correct URL if needed?
   
   FINAL ANSWER: {{"key": "value"}}

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

Write the COMPLETE code with NO placeholders. Use standard scraping libraries only!"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate Python code to solve this task:\\n\\n{context}"}
        ]
        
        response = self.call_llm(messages, temperature=temperature)
        
        if "error" in response:
            return f"Error in action phase: {response['error']}"
        
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        print(f"✅ Generated solution approach")
        return content
    
    def reflect(self, task_result: str, expected_format: str = None) -> Dict[str, Any]:
        """
        Phase 3: REFLECT - Analyze results and suggest improvements
        """
        print(f"\\n{'='*70}")
        print(f"🔍 PHASE 3: AGENT REFLECTION")
        print(f"{'='*70}")
        
        reflection_prompt = f"""Analyze the following task execution result and provide reflection:

TASK RESULT:
{task_result}

EXPECTED FORMAT: {expected_format or "Not specified"}

Please analyze:
1. Was the task completed successfully?
2. Does the output match the expected format?
3. What went well?
4. What could be improved?
5. Are there any errors or issues?

Respond with a JSON object:
{{
    "success": true/false,
    "confidence": 0.0-1.0,
    "issues": ["list", "of", "issues"],
    "suggestions": ["list", "of", "improvements"],
    "summary": "brief summary"
}}"""
        
        messages = [
            {"role": "system", "content": reflection_prompt},
            {"role": "user", "content": "Please analyze this result."}
        ]
        
        response = self.call_llm(messages, temperature=0.3)
        
        try:
            if "error" in response:
                return {"error": response["error"]}
            
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Extract JSON from response
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                return {"error": "No JSON reflection found in LLM response"}
            
            reflection_json = content[json_start:json_end]
            reflection = json.loads(reflection_json)
            
            print(f"✅ Reflection completed:")
            print(f"   Success: {reflection.get('success', 'Unknown')}")
            print(f"   Confidence: {reflection.get('confidence', 'Unknown')}")
            
            return reflection
            
        except Exception as e:
            return {"error": f"Failed to parse reflection: {str(e)}"}
    
    def solve_task(self, context: str, max_iterations: int = 3) -> str:
        """
        Main method to solve a task using Think → Act → Reflect paradigm
        """
        print(f"\\n🚀 Starting Task Resolution")
        print(f"Max iterations: {max_iterations}")
        
        previous_attempts = []
        
        for iteration in range(max_iterations):
            print(f"\\n{'='*80}")
            print(f"🔄 ITERATION {iteration + 1}/{max_iterations}")
            print(f"{'='*80}")
            
            # Phase 1: Think
            plan = self.think(context, context, previous_attempts)
            
            if "error" in plan:
                error_msg = f"Thinking failed: {plan['error']}"
                print(f"❌ {error_msg}")
                previous_attempts.append(error_msg)
                continue
            
            # Store plan in working memory
            self.working_memory[f"plan_{iteration}"] = plan
            
            # Phase 2: Act
            action_result = self.act(plan, context)
            
            if not action_result or "Error in action phase" in action_result:
                error_msg = f"Action failed: {action_result}"
                print(f"❌ {error_msg}")
                previous_attempts.append(error_msg)
                continue
            
            # Phase 3: Reflect
            reflection = self.reflect(action_result, plan.get("expected_output_format"))
            
            if "error" in reflection:
                print(f"⚠️ Reflection failed: {reflection['error']}")
            else:
                # Store reflection in working memory
                self.working_memory[f"reflection_{iteration}"] = reflection
                
                # Check if task was successful
                if reflection.get("success", False) and reflection.get("confidence", 0) > 0.7:
                    print(f"\\n🎉 Task completed successfully!")
                    print(f"✅ Confidence: {reflection.get('confidence', 0):.1%}")
                    return action_result
            
            # Add this attempt to previous attempts for next iteration
            previous_attempts.append(f"Generated code but reflection showed issues: {reflection.get('issues', [])}")
        
        print(f"\\n⚠️ Max iterations reached. Returning best attempt.")
        return action_result if 'action_result' in locals() else "No solution generated"
    
    def reset(self):
        """Reset the agent state"""
        self.conversation_history = []
        self.working_memory = {}
        self.iteration_count = 0
        print("🔄 Agent state reset")