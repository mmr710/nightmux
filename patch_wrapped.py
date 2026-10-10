import re

with open("nightmux.py", "r") as f:
    content = f.read()

def repl(m):
    css = m.group(1)
    css = css.replace("background-image:radial-gradient(circle at 85% 10%,#2a1d4a 0,#07090f 50%)",
                      "background-image:radial-gradient(circle at 85% 10%,#2a1d4a 0,#07090f 50%),radial-gradient(circle at 10% 90%,#1b2a4a 0,#07090f 50%)")
    css = css.replace(".n{font-size:56px;font-weight:700;color:#9ece6a}",
                      ".n{font-size:62px;font-weight:700;color:#9ece6a;text-shadow:0 0 15px rgba(158,206,106,0.5)}")
    css = css.replace("h1{margin:0;font-size:40px;color:#e0af68;letter-spacing:2px}",
                      "h1{margin:0;font-size:48px;color:#e0af68;letter-spacing:2px;text-shadow:0 0 15px rgba(224,175,104,0.4)}")
    return 'WRAPPED_HTML = """' + css + '"""'

content = re.sub(r'WRAPPED_HTML = """(.*?)"""', repl, content, flags=re.DOTALL)
with open("nightmux.py", "w") as f:
    f.write(content)
