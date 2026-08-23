# VHS Tape (https://github.com/charmbracelet/vhs)
# Run `vhs docs/demo.tape` to generate the demo.gif

Output docs/demo.gif
Set FontSize 18
Set Width 1200
Set Height 800
Set Theme "Dracula"

# Simulate the user sending a message on Telegram and the agent typing
Type "tmux new-session -s api"
Enter
Sleep 1s

Type "claude"
Enter
Sleep 2s

Type "Review the auth logic and add rate limiting"
Enter
Sleep 1s

# Simulate Claude Code doing work
Type "..."
Sleep 2s
Enter
Type "I will modify auth.py to add rate limiting."
Sleep 1s
Enter
Type "Done."
Sleep 2s

# Show the limits feature
Type "# Oh no, you hit a limit!"
Enter
Type "usage limit reached. resets in 1m"
Enter
Sleep 3s

# Show nightmux taking over
Type "# nightmux queued the prompt..."
Enter
Sleep 2s
Type "# 1 minute later..."
Enter
Type "# nightmux auto-resumed!"
Enter
Sleep 3s
