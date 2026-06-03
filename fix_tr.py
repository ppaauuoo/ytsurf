import sys

with open('C:/Users/1000335461/Documents/ytsurf/ytsurf.sh', 'rb') as f:
    raw = f.read()

# Show what we're working with
print("Total tr -d occurrences:", raw.count(b'tr -d'))

# Find exact pattern
idx = raw.find(b'tr -d')
chunk = raw[idx:idx+15]
print("First occurrence hex:", chunk.hex())

# The broken pattern: tr -d '<anything between single quotes including CR>'
# From hex: 27 0d 27 = ' <CR> '
broken_pattern = bytes([0x27, 0x0d, 0x27])  # '<CR>'
print("Occurrences of '<CR>' between quotes:", raw.count(broken_pattern))

# Fix: replace tr -d '<CR>' with tr -d '\r'
# Where '\r' uses backslash (0x5C) + r (0x72) in single quotes
want = bytes([0x74,0x72,0x20,0x2d,0x64,0x20,0x27,0x0d,0x27])  # tr -d '<CR>'
good = bytes([0x74,0x72,0x20,0x2d,0x64,0x20,0x27,0x5c,0x72,0x27])  # tr -d '\r'

count = raw.count(want)
print(f"Replacing {count} occurrences of tr -d '<CR>' with tr -d '\\r'")

fixed = raw.replace(want, good)

# Verify
print(f"After fix - old pattern remaining: {fixed.count(want)}")
print(f"After fix - new pattern present: {fixed.count(good)}")

# Check one
idx2 = fixed.find(good)
print("Sample after fix hex:", fixed[idx2:idx2+12].hex())

with open('C:/Users/1000335461/Documents/ytsurf/ytsurf.sh', 'wb') as f:
    f.write(fixed)

print("Done.")
