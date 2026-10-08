#!/bin/sh
# nightmux: get (or update) the current version from GitHub and run setup.
#   curl -fsSL https://raw.githubusercontent.com/mmr710/nightmux/main/install.sh | sh
# Joining another nightmux as a second server? Use the command from its
# dashboard (servers -> + add server) instead: it does this and --join.
set -e

echo "🌙 Installing nightmux..."
missing=""
for b in git python3 tmux; do
  command -v "$b" >/dev/null 2>&1 || missing="$missing $b"
done
if [ -n "$missing" ]; then
  if command -v brew >/dev/null 2>&1; then hint="brew install$missing"
  elif command -v apt-get >/dev/null 2>&1; then hint="sudo apt-get install -y$missing"
  elif command -v dnf >/dev/null 2>&1; then hint="sudo dnf install -y$missing"
  else hint="install:$missing"; fi
  echo "needs$missing — run: $hint"
  exit 1
fi

if [ -d "$HOME/nightmux/.git" ]; then
  git -C "$HOME/nightmux" pull -q
else
  git clone -q https://github.com/mmr710/nightmux "$HOME/nightmux"
fi

# Piped from curl, stdin is the script itself: setup asks questions, so it
# reads the terminal instead.
if [ -r /dev/tty ]; then
  python3 "$HOME/nightmux/nightmux.py" --setup < /dev/tty
else
  echo "no terminal to ask setup questions on — run: python3 ~/nightmux/nightmux.py --setup"
  exit 1
fi
echo "✅ Done. Just looking? python3 ~/nightmux/nightmux.py --demo"
