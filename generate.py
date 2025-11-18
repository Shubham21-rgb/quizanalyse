import requests
from bs4 import BeautifulSoup

# URL to fetch the data from
url = "https://en.wikipedia.org/wiki/2025_Union_budget_of_India"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Fetch the Wikipedia page
response = requests.get(url ,headers=headers)
response.raise_for_status()  # Raise an error for bad responses

# Parse the HTML content
soup = BeautifulSoup(response.text, 'html.parser')

# Initialize variables to find the maximum budget
max_budget = None

# Find all relevant sections that might contain budget information
for paragraph in soup.find_all('p'):
    text = paragraph.get_text()
    # Look for budget amounts in the text
    if 'budget' in text.lower():
        words = text.split()
        for word in words:
            if '₹' in word or 'Rs.' in word:
                # Clean the word to extract the numeric value
                cleaned_word = ''.join(filter(str.isalnum, word.replace('₹', '').replace('Rs.', '').strip()))
                if cleaned_word.isdigit():
                    amount = int(cleaned_word)
                    if max_budget is None or amount > max_budget:
                        max_budget = amount

# Prepare the answer JSON
answer = {
    "answer": f"₹{max_budget} crore" if max_budget else "No budget found",
    "url": url,
    "reasoning": "The maximum budget was determined by scanning the paragraphs for budget amounts and selecting the highest value."
}

# Submission URL
submission_url = "https://Alpha23332-ga2-6d65ad.hf.space/receiver"

# Post the answer to the submission endpoint
submission_response = requests.post(submission_url, json=answer)
submission_response.raise_for_status()

print("Submission successful:", submission_response.json())
