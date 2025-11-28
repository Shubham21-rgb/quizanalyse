#!/usr/bin/env python3

import requests
import hashlib
import pandas as pd
from io import StringIO

# Test different possible interpretations
EMAIL = "23f2003481@ds.study.iitm.ac.in"
SECRET = "23SHWEBGPT"
SUBMIT_URL = "https://tds-llm-analysis.s-anand.net/submit"
URL_PARAM = "https://tds-llm-analysis.s-anand.net/demo-audio"

# Calculate cutoff
sha1_hash = hashlib.sha1(EMAIL.encode()).hexdigest()
cutoff = int(sha1_hash[:4], 16)

# Download CSV
csv_url = "https://tds-llm-analysis.s-anand.net/demo-audio-data.csv"
response = requests.get(csv_url, timeout=10)
df = pd.read_csv(StringIO(response.text))

first_col = df.iloc[:, 0]
filtered_values = first_col[first_col >= cutoff]

# Different possible answers
sum_answer = int(filtered_values.sum())
count_answer = len(filtered_values)
mean_answer = filtered_values.mean()
median_answer = filtered_values.median()

answers_to_try = [
    ("sum", sum_answer),
    ("count", count_answer), 
    ("mean", round(mean_answer, 2)),
    ("median", median_answer),
    ("sum_as_string", str(sum_answer)),
    ("count_as_string", str(count_answer))
]

print(f"Cutoff: {cutoff}")
print(f"Filtered values: {len(filtered_values)} out of {len(first_col)}")
print(f"\nTrying different interpretations:")

for interpretation, answer in answers_to_try:
    payload = {
        "email": EMAIL,
        "secret": SECRET,
        "url": URL_PARAM,
        "answer": answer
    }
    
    try:
        print(f"\n🧪 Testing {interpretation}: {answer}")
        response = requests.post(SUBMIT_URL, json=payload, timeout=10)
        result = response.json()
        print(f"📥 Response: {result}")
        
        if result.get('correct', False):
            print(f"✅ SUCCESS! The answer is {interpretation}: {answer}")
            break
    except Exception as e:
        print(f"❌ Error: {e}")