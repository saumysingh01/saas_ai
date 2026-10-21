# AI Market Analysis SaaS - Backend

## Setup (5 minutes)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
# Open .env and fill in your keys (Groq key from console.groq.com)
python -m app.main
```

API docs: http://localhost:8000/docs

## One-time Supabase setup

1. Create a project at https://supabase.com
2. Open SQL Editor and run the contents of `supabase_schema.sql`
3. Copy your Project URL and service-role key into `.env`

## Authenticating requests

The API verifies Supabase JWTs. When creating a user (Supabase Auth dashboard
or `auth.signUp`), set `client_id` in their user_metadata. Send requests with:

```
Authorization: Bearer <supabase_access_token>
```
