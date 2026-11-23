"""
Run this once to find which Gemini model works with your paid API key.
Usage: py find_gemini_model.py
It will print the working model name and update .env automatically.
"""
import os, re

# Load key directly from .env
env_text = open('.env').read()
m = re.search(r'GEMINI_API_KEY=(\S+)', env_text)
if not m:
    print("ERROR: GEMINI_API_KEY not found in .env")
    exit(1)

api_key = m.group(1)
print(f"Testing API key: {api_key[:12]}...")

from google import genai

client = genai.Client(api_key=api_key)

# Priority order: cheapest/fastest first
candidates = [
    'gemini-2.5-flash-lite',
    'gemini-flash-latest',
    'gemini-2.5-flash',
    'gemini-3-flash-preview',
    'gemini-2.5-pro',
]

working = None
for model in candidates:
    print(f"  Testing {model}...", end=' ', flush=True)
    try:
        r = client.models.generate_content(
            model=model,
            contents='Reply with exactly the word: WORKING'
        )
        if r.text:
            print(f"OK → {r.text.strip()[:30]}")
            working = model
            break
    except Exception as e:
        print(f"FAIL: {str(e)[:60]}")

if working:
    print(f"\n✅ Working model: {working}")
    # Update or add GEMINI_MODEL in .env
    if 'GEMINI_MODEL=' in env_text:
        new_env = re.sub(r'GEMINI_MODEL=\S+', f'GEMINI_MODEL={working}', env_text)
    else:
        new_env = env_text.rstrip() + f'\nGEMINI_MODEL={working}\n'
    open('.env', 'w').write(new_env)
    print(f"✅ GEMINI_MODEL={working} written to .env")
else:
    print("\n❌ No model worked. Check your API key or billing status.")
