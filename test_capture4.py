import sys
sys.path.append('mcp/review-synthesizer')
import capture

text = """Status: BLOCKED
Blocker Description: the API is down

I cannot proceed until this is fixed.
"""
res = capture.extract_status(text)
print(res)
