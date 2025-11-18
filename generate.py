import requests
from bs4 import BeautifulSoup

# Define the headers to mimic a browser request
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# URL to scrape
wiki_url = "https://en.wikipedia.org/wiki/2025_Union_budget_of_India"

# Fetch the Wikipedia page
response = requests.get(wiki_url, headers=headers)
response.raise_for_status()  # Raise an error for bad responses

# Parse the page content
soup = BeautifulSoup(response.content, 'html.parser')

# Find the largest budget/amount mentioned
# This is a hypothetical example; you would need to adjust the selectors based on the actual HTML structure
# For demonstration, let's assume the budget is in a specific tag
# Here, we are looking for any relevant financial data in paragraphs or tables
budgets = []

# Example of searching for budget amounts in paragraphs
for paragraph in soup.find_all('p'):
    if 'budget' in paragraph.text.lower():
        budgets.append(paragraph.text)

# Process the found budgets to extract amounts (this will need to be tailored to the actual content)
# For simplicity, let's assume we found a budget amount in the text
# This is a placeholder; you would need to implement a method to extract the actual amounts
# For example, using regex to find currency amounts
import re

amounts = []
for text in budgets:
    found_amounts = re.findall(r'₹\d+ crore|Rs\. \d+', text)
    amounts.extend(found_amounts)

# Find the maximum budget amount
max_budget = max(amounts, key=lambda x: int(re.sub(r'\D', '', x))) if amounts else None

# Prepare the output in the required JSON format
output = {
    "answer": max_budget,
    "url": wiki_url,
    "reasoning": f"The maximum budget found for the 2025 Union Budget of India is {max_budget}."
}

# Print the output for verification
print(output)

# Submission endpoint
submission_url = "https://Alpha23332-ga2-6d65ad.hf.space/receiver"

# Post the result to the specified endpoint
submission_response = requests.post(submission_url, json=output, headers=headers)
submission_response.raise_for_status()  # Raise an error for bad responses

# Print submission response for confirmation
print("Submission response:", submission_response.json())