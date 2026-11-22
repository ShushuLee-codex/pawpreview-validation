# PawPreview

Early-trial landing page for a planned Shopify app that shows shoppers a realistic preview of their pet photo printed on custom / POD products.

The public landing page is a Render static site. Form submissions go to a Render free web service and are stored in a Render free Postgres database.

This is demand validation only. The product is not in the Shopify App Store yet.

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

The static landing files live in `site/`.
