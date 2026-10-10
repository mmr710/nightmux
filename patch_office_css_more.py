import re

with open("nightmux.py", "r") as f:
    content = f.read()

def repl(m):
    css = m.group(1)
    
    # Add float animation to room, and gradient to canvas
    css = css.replace(".room{background:linear-gradient(145deg, #101423 0%, #0d1120 100%);border:1px solid #232b42;border-radius:12px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.4);position:relative;transition:transform 0.2s}",
                      ".room{background:linear-gradient(145deg, #101423 0%, #0d1120 100%);border:1px solid rgba(122,162,247,0.15);border-radius:16px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05);position:relative;transition:all 0.3s cubic-bezier(0.25,0.8,0.25,1);animation:float 6s ease-in-out infinite}\n@keyframes float { 0% { transform:translateY(0px); } 50% { transform:translateY(-6px);box-shadow:0 15px 50px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05); } 100% { transform:translateY(0px); } }")
    css = css.replace("canvas{display:block;width:100%;image-rendering:pixelated;image-rendering:crisp-edges;cursor:pointer;border-bottom:1px solid #232b42}",
                      "canvas{display:block;width:100%;image-rendering:pixelated;image-rendering:crisp-edges;cursor:pointer;border-bottom:none;border-radius:0 0 16px 16px;background:radial-gradient(circle at center, #0d1120, #05070f)}")
    css = css.replace(".room h2{font-size:14px;margin:0;padding:12px 14px;background:rgba(20,26,46,0.7);backdrop-filter:blur(8px);display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid #232b42}",
                      ".room h2{font-size:15px;font-weight:600;margin:0;padding:14px 18px;background:linear-gradient(90deg, rgba(20,26,46,0.8), rgba(27,33,51,0.9));backdrop-filter:blur(12px);display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid rgba(122,162,247,0.1);color:#7aa2f7;text-shadow:0 0 10px rgba(122,162,247,0.3)}")
    css = css.replace(".chips{display:flex;flex-wrap:wrap;gap:8px;padding:12px;background:rgba(0,0,0,0.2)}",
                      ".chips{display:flex;flex-wrap:wrap;gap:8px;padding:16px;background:rgba(0,0,0,0.25)}")
    
    return "<style>\n" + css + "\n</style>"

content = re.sub(r"<style>\n(.*?)\n</style>", repl, content, flags=re.DOTALL)

with open("nightmux.py", "w") as f:
    f.write(content)
