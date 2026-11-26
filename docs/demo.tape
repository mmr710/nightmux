# VHS Tape (https://github.com/charmbracelet/vhs): a real, unscripted run.
# Needs: a demo repo with one failing test, claude logged in, nightmux on PATH.
# Render: vhs docs/demo.tape
Output docs/demo.gif
Set Shell bash
Set FontSize 18
Set Width 1200
Set Height 640
Set Theme "Dracula"
Set TypingSpeed 40ms
Set Padding 20

Hide
Type "export GIT_PAGER=cat PATH=/tmp/claude-1001/demo/bin:$PATH PS1='\[\e[1;35m\]shop\[\e[0m\] $ ' && cd /tmp/claude-1001/demo/shop && clear"
Enter
Sleep 1s
Show

Type "pytest -q"
Enter
Wait /shop \$\s*$/
Sleep 1s

Type `nightmux run "fix the failing test" --until "pytest -q" --agents claude`
Sleep 500ms
Enter
Wait+Screen@240s /passed after/
Wait /shop \$\s*$/
Sleep 1s

Type "git diff cart.py"
Enter
Wait /shop \$\s*$/
Sleep 1500ms
Type "pytest -q"
Enter
Wait /shop \$\s*$/
Sleep 4s
