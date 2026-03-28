with open("src/lib/ui.py", "r") as f:
    content = f.read()

if "has_exactly_two_stims" in content:
    print("Patch applied successfully.")
else:
    print("Failed to apply patch.")
