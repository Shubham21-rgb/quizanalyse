import requests
import pandas as pd
import json

# Define the URL for the CSV file
csv_url = "https://tds-llm-analysis.s-anand.net/demo-audio-data.csv"

# Define headers for the request
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Read the CSV file into a pandas DataFrame
df = pd.read_csv(csv_url)

# Extract the cutoff value from the markdown report
cutoff_value = 24111

# Filter the DataFrame based on the cutoff value
filtered_df = df[df['value'] > cutoff_value]

# Process the filtered data to compute the required answer
# For example, let's assume we need to sum a column named 'amount'
total_amount = filtered_df['amount'].sum()

# Prepare the answer in the required JSON format
answer = {
    "email": "your email",
    "secret": "your secret",
    "url": "https://tds-llm-analysis.s-anand.net/demo-audio",
    "answer": total_amount
}

# Print the answer for verification
print("Answer:", json.dumps(answer, indent=2))

# Define the submission endpoint URL
submission_url = "https://tds-llm-analysis.s-anand.net/submit"

# Submit the answer to the endpoint
response = requests.post(submission_url, json=answer, headers=headers)
response.raise_for_status()

# Print the submission response
print("Submission response:", json.dumps(response.json()))
print("Status code:", response.status_code)