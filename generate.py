import requests
from bs4 import BeautifulSoup
import re
import json

# Set headers for all requests
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Step 1: Fetch the Wikipedia page
wikipedia_url = "https://en.wikipedia.org/wiki/2025_Union_budget_of_India"
try:
    response = requests.get(wikipedia_url, headers=headers, timeout=30)
    response.raise_for_status()
except Exception as e:
    print(f"Error fetching data: {e}")
    exit(1)

# Step 2: Parse the HTML content
soup = BeautifulSoup(response.content, 'html.parser')

# Step 3: Extract the defence budget information
# Assuming the budget is mentioned in a paragraph or list item
budget_text = ""
for paragraph in soup.find_all(['p', 'li']):
    if 'defence budget' in paragraph.get_text().lower():
        budget_text = paragraph.get_text(strip=True)
        break

# Step 4: Use regex to find the budget amount
budget_amount = re.search(r'₹[\d,]+ crore|Rs\. [\d,]+', budget_text)
if budget_amount:
    budget_value = budget_amount.group()
else:
    budget_value = "Not found"

# Step 5: Format the output
answer = {
    "answer": budget_value,
    "url": wikipedia_url,
    "reasoning": "The defence budget for 2025 was extracted from the Wikipedia page using regex pattern matching."
}

print("Answer:", json.dumps(answer, indent=2))

# Step 6: Submit the answer
submission_url = "https://Alpha23332-ga2-6d65ad.hf.space/receiver"
try:
    submission_response = requests.post(submission_url, json=answer, headers=headers)
    submission_response.raise_for_status()
    print("Submission response:", submission_response.json())
except Exception as e:
    print(f"Error submitting data: {e}")