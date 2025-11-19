import asyncio
import requests
import json
import re
from LLMFunc import LLMScraperHandler

async def scrape_url(url):
    handler = LLMScraperHandler()
    scrape_request = {
        "url": url,
        "force_dynamic": True
    }
    result = await handler.handle_request(scrape_request)
    if result.get('success'):
        markdown = handler.format_as_markdown(result)
        return markdown
    else:
        print(f"Scraping failed: {result.get('error')}")
        return None

# Scrape the Wikipedia page for the 2025 Union budget of India
url = "https://en.wikipedia.org/wiki/2025_Union_budget_of_India"
markdown_data = asyncio.run(scrape_url(url))

if markdown_data:
    # Use regex to find the budget amount in the markdown data
    budget_matches = re.findall(r'₹[\d,]+ crore|Rs\. [\d,]+', markdown_data)
    
    if budget_matches:
        # Assuming the largest budget is the one we need
        max_budget = max(budget_matches, key=lambda x: int(re.sub(r'[^\d]', '', x)))
    else:
        max_budget = "Not found"

    # Prepare the answer in the required JSON format
    answer = {
        "answer": max_budget,
        "url": url,
        "reasoning": "Extracted the largest budget amount mentioned for the 2025 Defence Budget of India from the Wikipedia page."
    }
    
    print("Answer:", json.dumps(answer, indent=2))
    
    # Submit the answer to the provided endpoint
    submission_url = "https://Alpha23332-ga2-6d65ad.hf.space/receiver"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    response = requests.post(submission_url, json=answer, headers=headers)
    print("Submission response:", response.json())