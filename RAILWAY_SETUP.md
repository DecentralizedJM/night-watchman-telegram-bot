# Railway Deployment Setup for Night Watchman

## Required: Redis

Redis is **required** for immunity storage, GPT API rate limiting, and state. Add Redis to your Railway project:

1. In your Railway project, click **New** → **Database** → **Redis**
2. After Redis is provisioned, go to the Redis service → **Variables**
3. Copy the `REDIS_URL` (e.g. `redis://default:xxx@host:port`)
4. In your **Night Watchman** service → **Variables**, add:
   - **Variable Name:** `REDIS_URL`
   - **Value:** `${{Redis.REDIS_URL}}` (Railway reference) or paste the full URL

Without Redis, GPT rate limiting is per-instance only and immunity does not persist across restarts.

## GPT AI Spam Scanning

1. Go to your **Railway Project** → **Night Watchman** service → **Variables**
2. Add:
   - **Variable Name:** `OPENAI_API_KEY`
   - **Value:** Your API key from [OpenAI Platform](https://platform.openai.com/api-keys)

## Optional Configuration

- `GPT_ENABLED`: Set to `true` (default) or `false`
- `GPT_RPM_LIMIT`: API calls per minute (Default: `10`, lower = fewer calls, lower cost)
- `GPT_MODEL`: Default is `gpt-4o-mini` (vision + cost-effective)

## Note on OpenAI

OpenAI API is paid. Add a payment method at [platform.openai.com](https://platform.openai.com) to use GPT.

## Build Verification

The bot will log `GPT AI scanner initialized (Model: gpt-4o-mini, Redis rate limit: on)` when Redis is connected. If the API key is missing, the bot starts without GPT.
