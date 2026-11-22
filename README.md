# PawPreview

Early-trial landing page for a planned Shopify app that shows shoppers a realistic preview of their pet photo printed on custom / POD products.

This repository is for demand validation only. The product is not in the Shopify App Store yet.

## Local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ADMIN_PASSWORD='...'
export SECRET_KEY='...'
export DATABASE_URL='sqlite:///local.db'
export PORT=8000
python app.py
```

## Deploy

Render free web service + free Postgres. Admin is at `/admin` and is password-protected. Credentials are stored outside this repo.
