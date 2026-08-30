# Billboard Games configuration

Sponsored events reuse the existing MongoDB, Razorpay, public URL, and admin settings.

Required for the first Nebius model:

```env
NEBIUS_API_BASE=https://api.tokenfactory.nebius.com/v1
NEBIUS_API_KEY=replace_me
NEBIUS_MODEL=meta-llama/Llama-3.3-70B-Instruct
MODEL_ENDPOINT_ALLOWLIST=api.tokenfactory.nebius.com
SESSION_SECRET=replace_with_a_long_random_value
COOKIE_SECURE=1
CORS_ORIGINS=https://your-frontend-host.example
```

`MODEL_ENDPOINT_ALLOWLIST` is a comma-separated hostname list. Model catalog records refer to
an environment variable by name through `credential_env`; API keys are never stored in MongoDB.

## Operator sequence

1. A sponsor submits and pays at `/sponsor`.
2. Approve the campaign at `/admin/games`.
3. Share `/campaign/<campaign-slug>` with creators.
4. Approve submissions and queue at least two.
5. Start the show from `/admin/games` and present `/event/<campaign-slug>`.
6. After the final round, record the manual prize state from the games desk.

The AI audience is explicitly synthetic and advisory. Its scores never affect the 70% human
vote / 30% unique-click result.
