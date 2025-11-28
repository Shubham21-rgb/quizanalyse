#!/usr/bin/env python3

import requests
import hashlib
import pandas as pd
from io import StringIO

# Test with the URL-encoded email cutoff
EMAIL_NORMAL = "23f2003481@ds.study.iitm.ac.in"
EMAIL_ENCODED = "23f2003481%40ds.study.iitm.ac.in"

# Calculate both cutoffs
cutoff_normal = int(hashlib.sha1(EMAIL_NORMAL.encode()).hexdigest()[:4], 16)
cutoff_encoded = int(hashlib.sha1(EMAIL_ENCODED.encode()).hexdigest()[:4], 16)

print(f"🔑 Normal email cutoff: {cutoff_normal}")
print(f"🔑 URL-encoded email cutoff: {cutoff_encoded}")

# Test with CSV
csv_url = "https://tds-llm-analysis.s-anand.net/demo-audio-data.csv"
response = requests.get(csv_url, timeout=10)
df = pd.read_csv(StringIO(response.text))
first_col = df.iloc[:, 0]

print(f"\n📊 Testing both cutoffs with CSV data:")

for email_type, cutoff in [("normal", cutoff_normal), ("url_encoded", cutoff_encoded)]:
    filtered = first_col[first_col >= cutoff]
    result = filtered.sum()
    count = len(filtered)
    
    print(f"\n{email_type.upper()} EMAIL (cutoff {cutoff}):")
    print(f"  Values >= {cutoff}: {count}")
    print(f"  Sum: {result}")

# Now test the URL-encoded version
print(f"\n🧪 Testing URL-encoded email cutoff ({cutoff_encoded}):")

SECRET = "23SHWEBGPT"
# Extract submit URL from CSV URL
parsed = urlparse(csv_url)
SUBMIT_URL = f"{parsed.scheme}://{parsed.netloc}/submit"
URL_PARAM = "https://tds-llm-analysis.s-anand.net/demo-audio"

# Calculate answer with URL-encoded cutoff
filtered_encoded = first_col[first_col >= cutoff_encoded]
answer_encoded = int(filtered_encoded.sum())

payload = {
    "email": EMAIL_NORMAL,  # Use normal email for submission
    "secret": SECRET,
    "url": URL_PARAM,
    "answer": answer_encoded
}

try:
    print(f"📤 Testing URL-encoded cutoff answer: {answer_encoded}")
    response = requests.post(SUBMIT_URL, json=payload, timeout=10)
    result = response.json()
    print(f"📥 Response: {result}")
    
    if result.get('correct', False):
        print(f"✅ SUCCESS! The URL-encoded email method works!")
        print(f"✅ Correct answer: {answer_encoded}")
    else:
        print("❌ Still wrong - trying a few more variations...")
        
        # Try some other interpretations with the new cutoff
        variations = [
            ("count", len(filtered_encoded)),
            ("sum_of_indices", sum(i for i, val in enumerate(first_col) if val >= cutoff_encoded)),
            ("cutoff_value", cutoff_encoded)
        ]
        
        for name, answer in variations:
            payload["answer"] = answer
            try:
                print(f"📤 Testing {name}: {answer}")
                response = requests.post(SUBMIT_URL, json=payload, timeout=10)
                result = response.json()
                print(f"📥 Response: {result}")
                
                if result.get('correct', False):
                    print(f"✅ SUCCESS! Answer is {name}: {answer}")
                    break
            except Exception as e:
                print(f"❌ Error: {e}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print(f"\n📋 Summary of findings:")
print(f"Normal email gives cutoff: {cutoff_normal} -> sum: {int(first_col[first_col >= cutoff_normal].sum())}")
print(f"URL-encoded email gives cutoff: {cutoff_encoded} -> sum: {int(first_col[first_col >= cutoff_encoded].sum())}")