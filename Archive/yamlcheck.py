import chardet

filename = "zscore_config.yaml"

# Detect encoding
with open(filename, "rb") as f:
    raw = f.read()
    result = chardet.detect(raw)
    encoding = result['encoding']

print(f"Detected encoding: {encoding}")

# Print any line containing 'Canad'
with open(filename, "r", encoding=encoding) as f:
    for line in f:
        if "Canad" in line:
            print(repr(line.strip()))

            