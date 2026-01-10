# Railway Deployment Setup for Night Watchman

To enable the advanced Gemini AI spam scanning on Railway, you need to add your API key as an environment variable.

## Step Using Railway Dashboard:

1. Go to your **Railway Project**.
2. Select the **Night Watchman** service.
3. Go to the **Variables** tab.
4. Click **New Variable**.
5. Add the following variable:
   - **Variable Name:** `GEMINI_API_KEY`
   - **Value:** Paste your API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

## Optional Configuration

You can also adjust these variables if needed:

- `GEMINI_ENABLED`: Set to `true` (default) or `false`.
- `GEMINI_RPM_LIMIT`: Set limit per minute (Default: `10`). The free tier is strict, so keeping this low prevents errors.
- `GEMINI_MODEL`: Default is `gemini-pro`.

## Build Verification

The bot will automatically detect the key. If the key is missing or invalid, the bot will start but will log a warning and fallback to standard detection mode without Gemini.
