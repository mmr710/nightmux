# Editor Integration (VS Code / Vim)

You can send tasks to nightmux directly from your editor using the local Webhook API (`127.0.0.1:9090`).

## VS Code Tasks
Add this to your `.vscode/tasks.json` to send the current file to nightmux with a keyboard shortcut.

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Send to nightmux",
            "type": "shell",
            "command": "curl -X POST http://127.0.0.1:9090/topic/api -d \"Review ${file} and fix any syntax errors.\"",
            "problemMatcher": [],
            "presentation": {
                "reveal": "never"
            }
        }
    ]
}
```

## Vim / Neovim
Add this to your `.vimrc` to send the current line or selection to nightmux.

```vim
" Send the current file path to nightmux
nnoremap <leader>nm :!curl -s -X POST http://127.0.0.1:9090/topic/api -d "Refactor %"<CR>
```
