# Setting up Anthropic API key

**refren** uses Claude — an AI assistant made by Anthropic — to do its work. To use it, you need a personal API key from Anthropic. Think of this key as a password that lets refren talk to Claude on your behalf.

Don't worry: this is a one-time setup, it takes about 5 minutes, and the cost is **essentially free** for typical use (fractions of a cent per run).

---

## Step 1 — Create an Anthropic account

Go to **[console.anthropic.com](https://console.anthropic.com)** and sign up with your email address.

> ⚠️ **Note:** This is a *developer* account, separate from the Claude chatbot at claude.ai. Even if you already use Claude, you'll need to register here separately.

---

## Step 2 — Add a payment method

After signing in, go to **Settings → Billing** and add a credit card.

You won't be charged anything upfront. Anthropic bills based on usage — for typical use of refren, this comes to **fractions of a cent per run**, so the cost in practice is negligible. Setting a monthly spending limit (e.g. $5) is a good precaution and easy to do on the same page.

---

## Step 3 — Generate your API key

1. In the left sidebar, click **API Keys**
2. Click **Create Key**
3. Give it any name — for example, `refren`
4. Click **Create Key**

> ⚠️ **Important:** Copy the key immediately and store it somewhere safe (a plain text file on your computer is fine). Anthropic only shows the key once — if you lose it, you'll need to generate a new one.

---

## Step 4 — Add the key to refren

Set your key as an environment variable. The exact command depends on your operating system.

**macOS / Linux** — run in your terminal:
```bash
export ANTHROPIC_API_KEY="your-key-here"
```
To make this permanent, add that line to your shell profile (`~/.bashrc` or `~/.zshrc`).

**Windows (Command Prompt):**
```cmd
set ANTHROPIC_API_KEY=your-key-here
```

**Windows (PowerShell):**
```powershell
$env:ANTHROPIC_API_KEY="your-key-here"
```

On Windows, these commands only last for the current session. To set the variable permanently, search for **"Edit the system environment variables"** in the Start menu, click **Environment Variables**, and add `ANTHROPIC_API_KEY` as a new user variable.

---

## That's it

Once your key is set, run refren as described in the [README](README.md).

---

> **Privacy note:** Your API key stays on your machine. When you run refren, your input is sent to Anthropic's servers for processing — the same way it would be if you used the Claude chatbot directly. Anthropic's privacy policy applies: [anthropic.com/privacy](https://www.anthropic.com/privacy).
