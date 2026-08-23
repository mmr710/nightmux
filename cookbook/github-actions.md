# GitHub Actions Integration

You can use nightmux's Webhook API to automatically pipe CI/CD test failures directly into your local agent session while you sleep.

**The Workflow:**
1. You push code and go to sleep.
2. GitHub Actions runs your tests and they fail.
3. The Action sends a webhook payload to a service (or directly to your IP/tailscale if exposed).
4. `nightmux` receives it, queues the prompt, and the agent fixes the failure.

```yaml
name: Send Failure to nightmux
on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Tests
        id: test
        run: pytest

      - name: Notify nightmux on failure
        if: failure()
        run: |
          curl -X POST http://<YOUR_TAILSCALE_IP>:9090/topic/api \
               -d "Tests failed on CI. Please review the latest commit and fix the test failures. Run the tests locally to verify."
```
