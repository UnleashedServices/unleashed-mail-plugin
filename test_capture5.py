import sys
sys.path.append('mcp/review-synthesizer')
import capture

text = """Status: COMPLETE
Confidence: high

VERDICT: APPROVE
"""
res = capture.extract_status(text)
print("Result with VERDICT:", res)
