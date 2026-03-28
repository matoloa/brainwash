with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

import re
content = re.sub(
    r'([ \t]*)import warnings\n([ \t]*)with warnings\.catch_warnings\(\):\n([ \t]*)warnings\.simplefilter\("ignore"\)\n([ \t]*)ppr = \(v2 / v1\) \* 100\n([ \t]*)# replace inf and -inf with nan\n([ \t]*)ppr\[~np\.isfinite\(ppr\)\] = np\.nan\n',
    r'\1import numpy as np\n\1import warnings\n\2with warnings.catch_warnings():\n\3warnings.simplefilter("ignore")\n\4ppr = (v2 / v1) * 100\n\5# replace inf and -inf with nan\n\6ppr[~np.isfinite(ppr)] = np.nan\n',
    content
)

content = re.sub(
    r'([ \t]*)import warnings\n([ \t]*)with warnings\.catch_warnings\(\):\n([ \t]*)warnings\.simplefilter\("ignore"\)\n([ \t]*)ppr = \(v2 / v1\) \* 100\n([ \t]*)ppr\[~np\.isfinite\(ppr\)\] = np\.nan\n',
    r'\1import numpy as np\n\1import warnings\n\2with warnings.catch_warnings():\n\3warnings.simplefilter("ignore")\n\4ppr = (v2 / v1) * 100\n\5ppr[~np.isfinite(ppr)] = np.nan\n',
    content
)

with open("src/lib/ui_plot.py", "w") as f:
    f.write(content)
print("Regex patch applied")
