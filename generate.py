import asyncio
import requests
import json
import os
from LLMFunc import LLMScraperHandler

# AI-Powered Scraping Function
async def ai_scrape_and_extract(url_to_scrape: str, extraction_instructions: str):
    print(f"🤖 AI-Powered Scraping: {url_to_scrape}")
    print(f"📝 Task: {extraction_instructions}")
    
    # Step 1: Scrape the URL
    handler = LLMScraperHandler()
    result = await handler.handle_request({"url": url_to_scrape, "force_dynamic": True})
    
    if not result.get('success'):
        print(f"❌ Scraping failed: {result.get('error')}")
        return None
    
    # Step 2: Format as markdown for AI processing
    markdown_content = handler.format_as_markdown(result)
    
    # Step 3: Call AI to extract data
    api_key = os.getenv("AI_PIPE_TOKEN_1")
    ai_prompt = f'''You are a data extraction expert. Extract the requested data from the webpage content below.

EXTRACTION TASK: {extraction_instructions}

WEBPAGE CONTENT:
{markdown_content}

Return ONLY a valid JSON object with the extracted data. No explanations, just the JSON.
'''
    
    ai_url = "https://aipipe.org/openai/v1/chat/completions"
    ai_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    ai_payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a data extraction expert. Return only valid JSON."},
            {"role": "user", "content": ai_prompt}
        ],
        "temperature": 0.3
    }
    
    try:
        ai_response = requests.post(ai_url, headers=ai_headers, json=ai_payload, timeout=60)
        ai_result = ai_response.json()
        extracted_text = ai_result['choices'][0]['message']['content']
        
        # Try to parse as JSON
        if '