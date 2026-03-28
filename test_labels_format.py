with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

idx = content.find('ax1.set_ylabel("Amplitude (mV)")')
print(content[idx:idx+300])
