import re

with open("nightmux.py", "r") as f:
    content = f.read()

content = content.replace("try:\n        import json, os", "try:\n        import os")
with open("nightmux.py", "w") as f:
    f.write(content)
