with open("src/lib/ui.py", "r") as f:
    content = f.read()

content = content.replace('"radioButton_type_PP"', '"radioButton_type_pp"')
content = content.replace('self.radioButton_type_PP', 'self.radioButton_type_pp')

with open("src/lib/ui.py", "w") as f:
    f.write(content)
print("Replaced PP with pp in ui.py")
