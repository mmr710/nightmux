import re

with open("nightmux.py", "r") as f:
    content = f.read()

# Add elements
html_inject = """<span class="meter">5h <span class="bar" id="u5"><i></i></span></span>
<span class="meter">7d <span class="bar" id="u7"><i></i></span></span>
<span class="meter" id="agy_stat" style="display:none" title="">agy <span class="bar" id="agy_b"><i></i></span></span>
<span class="meter" id="oc_stat" style="display:none" title="">opencode <span class="bar" id="oc_b"><i></i></span></span>"""

content = content.replace("""<span class="meter">5h <span class="bar" id="u5"><i></i></span></span>
<span class="meter">7d <span class="bar" id="u7"><i></i></span></span>""", html_inject)

# Update render
js_inject = """  for (const [id, k] of [['u5', 'five_hour'], ['u7', 'seven_day'], ['agy_b', 'agy_limit'], ['oc_b', 'oc_limit']]) {
    const p = data.usage[k], bar = document.getElementById(id);
    if(bar) {
      if(p != null) bar.parentElement.style.display = '';
      bar.querySelector('i').style.width = (p == null ? 0 : Math.min(100, p)) + '%';
      bar.classList.toggle('hot', p >= 80); bar.title = p == null ? 'no figure yet' : Math.round(p) + '%';
    }
  }
  if(data.usage.agy_model && document.getElementById('agy_stat')) document.getElementById('agy_stat').title = 'agy model: ' + data.usage.agy_model;
  if(data.usage.oc_model && document.getElementById('oc_stat')) document.getElementById('oc_stat').title = 'opencode model: ' + data.usage.oc_model;
"""

content = re.sub(r"for \(const \[id, k\] of \[\['u5', 'five_hour'\], \['u7', 'seven_day'\]\]\) \{.*?\}", js_inject, content, flags=re.DOTALL)

with open("nightmux.py", "w") as f:
    f.write(content)
