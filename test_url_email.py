#!/usr/bin/env python3

import requests
import hashlib
import pandas as pd
from io import StringIO

# The email appears URL-encoded in the original URL
# Maybe the JavaScript getEmail() returns the URL-encoded version?

EMAIL_FROM_URL = "23f2003481%40ds.study.iitm.ac.in"  # This is what's in the URL
EMAIL_DECODED = "23f2003481@ds.study.iitm.ac.in"    # This is what we've been using

print("🔍 Testing email extraction theory:")
print(f"URL contains: {EMAIL_FROM_URL}")
print(f"We've been using: {EMAIL_DECODED}")

# Test cutoff calculation with both
cutoff_from_url = int(hashlib.sha1(EMAIL_FROM_URL.encode()).hexdigest()[:4], 16)
cutoff_decoded = int(hashlib.sha1(EMAIL_DECODED.encode()).hexdigest()[:4], 16)

print(f"\nCutoff from URL email: {cutoff_from_url}")
print(f"Cutoff from decoded email: {cutoff_decoded}")

# Test with CSV
csv_url = "https://tds-llm-analysis.s-anand.net/demo-audio-data.csv"
response = requests.get(csv_url, timeout=10)
df = pd.read_csv(StringIO(response.text))
first_col = df.iloc[:, 0]

# Calculate answer with URL email cutoff
filtered = first_col[first_col >= cutoff_from_url]
answer = int(filtered.sum())
count = len(filtered)

print(f"\nUsing URL email for cutoff calculation:")
print(f"Cutoff: {cutoff_from_url}")
print(f"Values >= cutoff: {count}")
print(f"Sum: {answer}")

# Test submission
SECRET = "23SHWEBGPT"
SUBMIT_URL = "https://tds-llm-analysis.s-anand.net/submit" 
URL_PARAM = "https://tds-llm-analysis.s-anand.net/demo-audio"

payload = {
    "email": EMAIL_DECODED,  # Use decoded email for submission
    "secret": SECRET,
    "url": URL_PARAM,
    "answer": answer
}

try:
    print(f"\n📤 Testing with URL-based cutoff: {answer}")
    response = requests.post(SUBMIT_URL, json=payload, timeout=15)
    result = response.json()
    print(f"📥 Response: {result}")
    
    if result.get('correct', False):
        print(f"✅ SUCCESS! The URL email method works!")
        print(f"✅ Correct cutoff: {cutoff_from_url}")
        print(f"✅ Correct answer: {answer}")
    else:
        print("❌ Still incorrect. The mystery continues...")
        
        # Maybe try using URL email for submission too?
        payload_url_email = payload.copy()
        payload_url_email["email"] = EMAIL_FROM_URL
        
        print(f"\n📤 Testing with URL email for submission too...")
        response2 = requests.post(SUBMIT_URL, json=payload_url_email, timeout=15)
        result2 = response2.json()
        print(f"📥 Response: {result2}")
        
        if result2.get('correct', False):
            print(f"✅ SUCCESS! Using URL email for both cutoff AND submission!")
        
except Exception as e:
    print(f"❌ Error: {e}")

print(f"\n🎯 Summary:")
print(f"URL email gives cutoff: {cutoff_from_url}")  
print(f"Decoded email gives cutoff: {cutoff_decoded}")
print(f"URL email result: {answer}")
print(f"Decoded email result: {int(first_col[first_col >= cutoff_decoded].sum())}")