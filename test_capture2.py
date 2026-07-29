import sys
sys.path.append('mcp/review-synthesizer')
import capture

text = """Status: COMPLETE
Remaining: nothing

```json
{"some": "json"}
```

```json
[]
```
"""
res = capture.extract_status(text)
print(res)
