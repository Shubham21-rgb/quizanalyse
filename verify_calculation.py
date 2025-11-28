#!/usr/bin/env python3

import requests
import hashlib
import pandas as pd
from io import StringIO

# Verify our calculation step by step
EMAIL = "23f2003481@ds.study.iitm.ac.in"

# Calculate cutoff exactly like utils.js
sha1_hash = hashlib.sha1(EMAIL.encode()).hexdigest()
cutoff = int(sha1_hash[:4], 16)
print(f"🔑 Email: {EMAIL}")
print(f"🔑 SHA1 hash: {sha1_hash}")
print(f"🔑 First 4 chars: {sha1_hash[:4]}")
print(f"🔑 Cutoff: {cutoff}")

# Download and analyze CSV
csv_url = "https://tds-llm-analysis.s-anand.net/demo-audio-data.csv"
response = requests.get(csv_url, timeout=10)
df = pd.read_csv(StringIO(response.text))

print(f"\n📊 CSV Analysis:")
print(f"Shape: {df.shape}")
print(f"Column name: {df.columns[0]}")
print(f"Data type: {df.iloc[:, 0].dtype}")
print(f"Min value: {df.iloc[:, 0].min()}")
print(f"Max value: {df.iloc[:, 0].max()}")

# Show sample values around the cutoff
first_col = df.iloc[:, 0]
print(f"\n🔍 Sample values around cutoff {cutoff}:")
sample_data = df[(first_col >= cutoff - 5) & (first_col <= cutoff + 5)]
print(sample_data)

# Calculate filtered sum
filtered_values = first_col[first_col >= cutoff]
print(f"\n📈 Calculation:")
print(f"Values >= {cutoff}: {len(filtered_values)} out of {len(first_col)}")
print(f"Sum of filtered values: {filtered_values.sum()}")

# Double check with different calculation methods
sum_method1 = filtered_values.sum()
sum_method2 = sum(val for val in first_col if val >= cutoff)
sum_method3 = first_col[first_col >= cutoff].sum()

print(f"\n✅ Verification (should all be same):")
print(f"Method 1 (pandas .sum()): {sum_method1}")
print(f"Method 2 (Python sum()): {sum_method2}")
print(f"Method 3 (pandas filter): {sum_method3}")

# Check data types
print(f"\n🏷️ Data types:")
print(f"sum_method1 type: {type(sum_method1)}")
print(f"sum_method1 value: {sum_method1}")
if hasattr(sum_method1, 'item'):
    print(f"sum_method1.item(): {sum_method1.item()}")

print(f"\n🎯 Final answer: {int(sum_method1)}")