# Railway Deployment Setup for Night Watchman

To enable the GPT AI spam scanning on Railway, add your OpenAI API key as an environment variable.

## Step Using Railway Dashboard:

1. Go to your **Railway Project**.
2. Select the **Night Watchman** service.
3. Go to the **Variables** tab.
4. Click **New Variable**.
5. Add the following variable:
   - **Variable Name:** `OPENAI_API_KEY`
   - **Value:** Paste your API key from [OpenAI Platform](https://platform.openai.com/api-keys)

## Optional Configuration

You can also adjust these variables if needed:

- `GPT_ENABLED`: Set to `true` (default) or `false`.
- `GPT_RPM_LIMIT`: Set limit per minute (Default: `30`).
- `GPT_MODEL`: Default is `gpt-4o-mini` (supports vision, cost-effective).

## Note on OpenAI

OpenAI API is paid. You must add a payment method at [platform.openai.com](https://platform.openai.com) to use GPT for spam detection. There is no free tier like Gemini.

## Build Verification

The bot will automatically detect the key. If the key is missing or invalid, the bot will start but will log a warning and fallback to standard detection mode without GPT.
