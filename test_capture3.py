import sys
sys.path.append('mcp/review-synthesizer')
import capture

print(capture._match_field("1. Remaining: B.swift"))
print(capture._match_field("Remaining: B.swift"))
