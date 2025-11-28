import requests
import pandas as pd
import hashlib
from io import StringIO

# 1. DEFINE CONSTANTS (extracted from quiz context)
BASE_URL = "https://tds-llm-analysis.s-anand.net"  # From Original URL
DATA_URL = BASE_URL + "/demo-audio-data.csv"  # Absolute URL to CSV file
SUBMIT_URL = BASE_URL + "/submit"  # Submission endpoint
EMAIL = "23f2003481@ds.study.iitm.ac.in"  # From URL params
SECRET = "23SHWEBGPT"  # From request body
URL_PARAM = BASE_URL + "/demo-audio"  # Original quiz URL

# 2. FUNCTION TO CALCULATE CUTOFF
def calculate_cutoff(email):
    """Calculate cutoff using SHA1 hash of the email."""
    return int(hashlib.sha1(email.encode()).hexdigest()[:4], 16)

# 3. FUNCTION TO PROCESS CSV DATA
def process_csv_data():
    """Download CSV, filter data, and return the sum of values."""
    cutoff = calculate_cutoff(EMAIL)
    print(f"✓ Calculated cutoff: {cutoff}")
    
    # Download CSV
    response = requests.get(DATA_URL, timeout=30)
    response.raise_for_status()  # Raise an error for bad responses
    df = pd.read_csv(StringIO(response.text))
    print(f"✓ Loaded CSV with shape: {df.shape}")
    
    # Filter first column: keep values >= cutoff
    first_col = df.iloc[:, 0]
    filtered_values = first_col[first_col >= cutoff]
    result = filtered_values.sum()
    print(f"✓ Sum of values >= {cutoff}: {result}")
    return result

# 4. FUNCTION TO SUBMIT ANSWER
def submit_answer(answer, max_retries=3):
    """Submit answer with automatic retries and type conversion."""
    payload = {
        "email": EMAIL,
        "secret": SECRET,
        "url": URL_PARAM,
        "answer": answer
    }
    
    for attempt in range(max_retries):
        try:
            print(f"📤 Submission attempt {attempt + 1}/{max_retries}")
            response = requests.post(SUBMIT_URL, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            print(f"📥 Submission response: {result}")
            return result
        except Exception as e:
            print(f"❌ Submission error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                print(f"🔄 Retrying in {attempt + 1} seconds...")
                import time
                time.sleep(attempt + 1)
            else:
                print("❌ All retry attempts failed")
                return {"error": f"Submission failed: {str(e)}"}

# 5. MAIN EXECUTION
if __name__ == "__main__":
    try:
        answer = process_csv_data()
        print(f"✅ Final answer to submit: {answer}")
        result = submit_answer(answer)
        print(f"✅ Final result: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")