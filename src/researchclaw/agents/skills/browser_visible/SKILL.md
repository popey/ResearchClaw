# Browser Visible

- name: browser_visible
- description: Launch a visible (headed) Chromium browser for interactive research tasks, demos, or debugging — when the user explicitly asks to see a real browser window.
- emoji: 🖥️

## When to Use

- User explicitly asks to see a browser window
- Tasks require visual interaction or human verification
- Demonstrating web research workflows
- Debugging browser automation issues

## How to Use

1. Start browser in headed (visible) mode:
   ```json
   {"action": "start", "headed": true}
   ```

2. Navigate to a URL:
   ```json
   {"action": "open", "url": "https://scholar.google.com"}
   ```

3. Take a snapshot to see the current page:
   ```json
   {"action": "snapshot"}
   ```

4. Interact with elements (click, type, scroll):
   ```json
   {"action": "click", "selector": "#search-button"}
   ```
   ```json
   {"action": "type", "selector": "#search-input", "text": "machine learning survey"}
   ```

5. Always stop when done:
   ```json
   {"action": "stop"}
   ```

## Rules

- Always snapshot after navigation to verify page loaded correctly
- Always stop the browser when the task is complete
- Do NOT leave the browser running indefinitely
- If a page requires login, pause and ask the user to complete authentication manually
- Prefer headless mode for routine tasks; only use headed mode when visibility is required
