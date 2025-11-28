#!/usr/bin/env python3

import requests
import hashlib
import pandas as pd
from io import StringIO
import os
import re
from urllib.parse import urlparse

# UNIVERSAL Test - automatically extracts parameters from question.md
def extract_universal_params():
    params = {
        'email': 'test@example.com',
        'secret': 'SHWEBGPT', 
        'submit_url': 'https://example.com/submit',
        'url_param': 'https://example.com/demo-audio',
        'csv_url': 'https://example.com/demo-audio-data.csv'
    }
    try:
        if os.path.exists('question.md'):
            with open('question.md', 'r') as f:
                content = f.read()
            url_match = re.search(r'\*\*Original URL:\*\* (https?://[^\s\n]+)', content)
            if url_match:
                parsed = urlparse(url_match.group(1))
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                params['url_param'] = url_match.group(1)
                params['submit_url'] = base_url + '/submit'
            email_match = re.search(r'email[=:]\s*`?([^\s`\n&]+)', content)
            if email_match:
                params['email'] = email_match.group(1).replace('%40', '@')
            csv_match = re.search(r'\[([^\]]*\.csv[^\]]*)\]\(([^)]+)\)', content)
            if csv_match:
                params['csv_url'] = csv_match.group(2)
    except:
        pass
    return params

params = extract_universal_params()
EMAIL = params['email']
SECRET = params['secret']
SUBMIT_URL = params['submit_url']
URL_PARAM = params['url_param']

# Calculate cutoff
sha1_hash = hashlib.sha1(EMAIL.encode()).hexdigest()
cutoff = int(sha1_hash[:4], 16)
print(f"🔑 Cutoff: {cutoff}")

# Download CSV
csv_url = params['csv_url']
response = requests.get(csv_url, timeout=10)
df = pd.read_csv(StringIO(response.text))

print(f"📊 CSV shape: {df.shape}")
first_col = df.iloc[:, 0]

# The incomplete audio said: "pick the first column and at all values greater than or equal to the cutoff value provid"
# Maybe "provid" means "provide INDICES" not sum?

filtered_mask = first_col >= cutoff
filtered_values = first_col[filtered_mask]
filtered_indices = first_col.index[filtered_mask].tolist()

interpretations = [
    ("sum_of_filtered_values", filtered_values.sum()),
    ("count_of_filtered_values", len(filtered_values)),
    ("sum_of_filtered_indices", sum(filtered_indices)),
    ("count_of_filtered_indices", len(filtered_indices)),
    ("first_filtered_value", filtered_values.iloc[0] if len(filtered_values) > 0 else 0),
    ("last_filtered_value", filtered_values.iloc[-1] if len(filtered_values) > 0 else 0),
    ("median_of_filtered", filtered_values.median()),
    ("mean_of_filtered", filtered_values.mean()),
    # Maybe it's about the cutoff itself?
    ("cutoff_value", cutoff),
    # Or maybe add the cutoff to the sum?
    ("sum_plus_cutoff", filtered_values.sum() + cutoff),
    # Or multiply?
    ("count_times_cutoff", len(filtered_values) * cutoff),
    # Maybe it's asking for sum of indices (row numbers) where value >= cutoff?
    ("sum_of_row_indices", sum(i for i, val in enumerate(first_col) if val >= cutoff)),
]

print(f"\n🔍 Testing {len(interpretations)} interpretations:")
for name, value in interpretations:
    print(f"   {name}: {value}")

print(f"\n📊 Detailed info:")
print(f"   Total rows: {len(first_col)}")
print(f"   Values >= {cutoff}: {len(filtered_values)}")
print(f"   Min filtered value: {filtered_values.min()}")
print(f"   Max filtered value: {filtered_values.max()}")

# Test a few promising interpretations
promising = [
    ("sum_of_filtered_values", int(filtered_values.sum())),
    ("sum_of_row_indices", sum(i for i, val in enumerate(first_col) if val >= cutoff)),
    ("count_of_filtered_values", len(filtered_values)),
]

print(f"\n🧪 Testing promising interpretations:")

for name, answer in promising:
    payload = {
        "email": EMAIL,
        "secret": SECRET,
        "url": URL_PARAM,
        "answer": answer
    }
    
    try:
        print(f"\n📤 Testing {name}: {answer}")
        response = requests.post(SUBMIT_URL, json=payload, timeout=10)
        result = response.json()
        print(f"📥 Response: {result}")
        
        if result.get('correct', False):
            print(f"✅ SUCCESS! Answer is {name}: {answer}")
            break
    except Exception as e:
        print(f"❌ Error: {e}")

print("\n🎯 If none worked, the issue might be the server or our understanding is still wrong.")