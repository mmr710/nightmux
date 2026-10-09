import re

with open("nightmux.py", "r") as f:
    content = f.read()

def repl(m):
    css = m.group(1)
    # Background and font
    css = re.sub(r"body\{.*?\}", "body{margin:0;background:radial-gradient(circle at 50% 0%, #151a2a, #07090f 70%);color:#cdd6f4;font:14px/1.5 system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif}\npre, canvas, .nav a, .meter, h1 {font-family: ui-monospace, Menlo, Consolas, monospace}", css)
    # Header
    css = re.sub(r"header\{.*?\}", "header{display:flex;gap:14px;align-items:center;flex-wrap:wrap;padding:16px 24px;border-bottom:1px solid rgba(255,255,255,0.05);position:sticky;top:0;background:rgba(7,9,15,0.85);backdrop-filter:blur(16px);z-index:2;box-shadow:0 4px 30px rgba(0,0,0,0.4)}", css)
    css = re.sub(r"h1\{.*?\}", "h1{font-size:16px;margin:0;letter-spacing:1px;font-weight:600;text-shadow:0 0 10px rgba(255,255,255,0.1)}", css)
    # Nav buttons
    css = re.sub(r"\.nav a\{.*?\}", ".nav a{font-size:13px;color:#cdd6f4;text-decoration:none;border:1px solid #2d3346;border-radius:8px;padding:6px 12px;background:linear-gradient(180deg, #1b2133, #131722);transition:all 0.2s;box-shadow:0 2px 5px rgba(0,0,0,0.2)}\n.nav a:hover{background:linear-gradient(180deg, #2d3346, #1b2133);border-color:#565f89;transform:translateY(-1px)}", css)
    # Main and Room
    css = re.sub(r"main\{.*?\}", "main{display:grid;gap:24px;padding:24px;min-height:100vh;grid-template-columns:repeat(auto-fill,minmax(380px,1fr))}", css)
    css = re.sub(r"\.room\{.*?\}", ".room{background:linear-gradient(145deg, #101423 0%, #0d1120 100%);border:1px solid #232b42;border-radius:12px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.4);position:relative;transition:transform 0.2s}\n.room:hover{transform:translateY(-2px);box-shadow:0 12px 40px rgba(0,0,0,0.6)}", css)
    css = re.sub(r"\.room h2\{.*?\}", ".room h2{font-size:14px;margin:0;padding:12px 14px;background:rgba(20,26,46,0.7);backdrop-filter:blur(8px);display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid #232b42}", css)
    # Canvas
    css = re.sub(r"canvas\{.*?\}", "canvas{display:block;width:100%;image-rendering:pixelated;image-rendering:crisp-edges;cursor:pointer;border-bottom:1px solid #232b42}", css)
    # Chips
    css = re.sub(r"\.chips\{.*?\}", ".chips{display:flex;flex-wrap:wrap;gap:8px;padding:12px;background:rgba(0,0,0,0.2)}", css)
    css = css.replace("button{font:inherit;background:#1b2133;color:#cdd6f4;border:2px solid #2b3452;padding:5px 9px;cursor:pointer}", "button.chip{font:inherit;background:linear-gradient(180deg, #1b2133, #151a28);color:#cdd6f4;border:1px solid #2b3452;border-radius:16px;padding:6px 12px;cursor:pointer;font-size:12px;box-shadow:0 2px 5px rgba(0,0,0,0.2);transition:all 0.2s}\nbutton.chip:hover{background:linear-gradient(180deg, #2b3452, #1b2133);border-color:#3a4466}\nbutton:not(.chip){font:inherit;background:#1b2133;color:#cdd6f4;border:2px solid #2b3452;padding:5px 9px;cursor:pointer;border-radius:6px}")
    css = re.sub(r"\.chip\.alert\{.*?\}", ".chip.alert{border-color:#e0af68;animation:glow 1.5s infinite alternate}", css)
    css = re.sub(r"@keyframes blink\{.*?\}", "@keyframes glow { 0%{box-shadow:0 0 5px rgba(224,175,104,0.2);} 100%{box-shadow:0 0 15px rgba(224,175,104,0.6);border-color:#ffc777;} }", css)
    # Fix the bar gradient/color
    css = re.sub(r"\.bar i\{.*?\}", ".bar i{display:block;height:100%;width:0;background:linear-gradient(90deg, #3d59a1, #7aa2f7);border-radius:4px;box-shadow:0 0 8px rgba(122,162,247,0.5)}", css)
    css = re.sub(r"\.bar\{.*?\}", ".bar{display:inline-block;width:72px;height:8px;background:#1b2133;border-radius:4px;overflow:hidden}", css)

    return "<style>\n" + css + "\n</style>"

content = re.sub(r"<style>\n(.*?)\n</style>", repl, content, flags=re.DOTALL)

with open("nightmux.py", "w") as f:
    f.write(content)
