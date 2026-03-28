with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

import re
content = re.sub(
    r'([ \t]*)ppr\[~np\.isfinite\(ppr\)\] = np\.nan\n\n([ \t]*)import numpy as np\n',
    r'\1ppr[~np.isfinite(ppr)] = np.nan\n\n',
    content
)

with open("src/lib/ui_plot.py", "w") as f:
    f.write(content)
