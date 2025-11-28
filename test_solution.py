import hashlib
import requests
import json

# Calculate secret code from email using SHA1 hash
email = "23f2003481@ds.study.iitm.ac.in"
sha1_hash = hashlib.sha1(email.encode()).hexdigest()
first_4_chars = sha1_hash[:4]
secret_code = int(first_4_chars, 16)

print(f"📧 Email: {email}")
print(f"🔐 SHA1 hash: {sha1_hash[:10]}...")
print(f"🔢 Calculated secret code: {secret_code}")

# Prepare submission
answer_data = {
    "email": email,
    "secret": "23SHWEBGPT",
    "url": "https://tds-llm-analysis.s-anand.net/demo-scrape-data?email=23f2003481@ds.study.iitm.ac.in",
    "answer": secret_code
}

print(f"📤 Submitting to: https://tds-llm-analysis.s-anand.net/submit")
print(f"📦 Payload: {json.dumps(answer_data, indent=2)}")

# Submit the answer
try:
    response = requests.post(
        "https://tds-llm-analysis.s-anand.net/submit",
        json=answer_data,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json"
        },
        timeout=30
    )
    
    print(f"📥 Response status: {response.status_code}")
    print(f"📥 Response headers: {dict(response.headers)}")
    
    if response.headers.get('content-type', '').startswith('application/json'):
        result = response.json()
        print(f"📥 Submission response: {result}")
    else:
        print(f"📥 Submission response (text): {response.text}")
        
except Exception as e:
    print(f"❌ Submission failed: {e}")