def add(a, b):
    return a + b

# Assertions for positive and negative numbers
assert add(2, 3) == 5
assert add(-1, -1) == -2
assert add(-1, 1) == 0

REPORT_TAG = 'saras-memory-17'

# Print the REPORT_TAG followed by the result of add(2, 3)
print(REPORT_TAG, add(2, 3))
