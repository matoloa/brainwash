with open("src/lib/ui.py", "r") as f:
    content = f.read()

if "valid_pp_ids" in content:
    print("Patch applied successfully.")
else:
    print("Failed to apply patch.")
