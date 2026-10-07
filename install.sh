#!/usr/bin/env bash
# nightmux: get (or update) the current version from GitHub and run setup.
# Joining another nightmux as a second server? Use the command from its
# dashboard (servers -> + add server) instead: it does this and --join.
set -e

echo "🌙 Installing nightmux..."
for b in git python3 tmux; do
  command -v "$b" >/dev/null || { echo "needs $b — e.g. sudo apt install -y git python3 tmux"; exit 1; }
done

if [ -d ~/nightmux/.git ]; then
  git -C ~/nightmux pull -q
else
  git clone -q https://github.com/mmr710/nightmux ~/nightmux
fi

python3 ~/nightmux/nightmux.py --setup
echo "✅ Done. Open Telegram to start using nightmux."
