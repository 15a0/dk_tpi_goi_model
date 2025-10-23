with open("zscore_config.yaml", "r", encoding="ascii") as f:
    content = f.read()
with open("zscore_config.yaml", "w", encoding="utf-8") as f:
    f.write(content)