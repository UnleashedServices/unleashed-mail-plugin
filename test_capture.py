import sys
sys.path.append('mcp/review-synthesizer')
import capture

text = """Some human prose.
Status: COMPLETE
Remaining: nothing
Confidence: high

```json
[]
```
"""
res = capture.extract_status(text)
print(res)

text2 = """Status: COMPLETE

```json
[]
```
"""
res2 = capture.extract_status(text2)
print(res2)
