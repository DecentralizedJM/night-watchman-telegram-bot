# Railway Deployment Setup for Night Watchman

## Required: Redis

Redis is **required** for VIP immunity and GPT rate limiting. Add Redis to your Railway project:

1. In your Railway project, click **New** → **Database** → **Redis**
2. After Redis is provisioned, go to the Redis service → **Variables**
3. Copy the `REDIS_URL` (e.g. `redis://default:xxx@host:port`)
4. In your **Night Watchman** service → **Variables**, add:
   - **Variable Name:** `REDIS_URL`
   - **Value:** `${{Redis.REDIS_URL}}` (Railway reference) or paste the full URL

Without Redis, GPT rate limiting is per-instance only and **VIP immunity does not persist across restarts**.

---

## How Redis Works Here

| What | How |
|------|-----|
| **Connection** | Bot reads `REDIS_URL` from env. If set, it connects at startup. Log: `✅ RedisManager initialized via URL`. |
| **VIP / Enhanced users** | When an admin uses **/enhance** on a user or reacts with ⭐ on their message, the user ID is stored in Redis set `nightwatchman:immune_users`. |
| **On bot start** | Bot loads all IDs from that set into memory. Log: `🛡️ Immunity: loaded N enhanced users from Redis`. |
| **On each message** | If the sender is in that set (or in-memory cache), the bot skips all moderation for them (total freedom). |
| **GPT rate limit** | Redis key `gpt:rpm` (or `gemini:rpm` on main) is used so API calls per minute are limited even across restarts. |

**What you need to do on Railway:**

1. Add a **Redis** service (New → Database → Redis).
2. In your **Night Watchman** service variables, set `REDIS_URL` to the Redis URL (e.g. `${{Redis.REDIS_URL}}`).
3. Redeploy. At startup you should see `✅ RedisManager initialized via URL` and `🛡️ Immunity: loaded N enhanced users from Redis` (N may be 0 until you enhance users).
4. To give someone VIP: in the group, have an admin use **/enhance** (reply to the user’s message) or react with ⭐ on their message. That user is then stored in Redis and will keep immunity after restarts.

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
