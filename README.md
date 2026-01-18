# Agent 1 - Stripe Webhook Ingestion (AWS)

## What this does

This project implements **Agent 1 (Ingestion)** in a fintech reconciliation pipeline:

- Stripe sends webhook events (Sandbox)
- AWS API Gateway receives webhook: `POST /prod/webhook/stripe`
- AWS Lambda validates Stripe signature (**ping valid/invalid**)
- Normalizes event payload into a standard JSON format
- Tokenizes PII (email/customer id) using SHA-256

## Architecture

Stripe Webhook -> API Gateway -> Lambda (Agent1)

## Evidence

✅ CloudWatch Logs show:

- `VALID Stripe webhook`
- `NORMALIZED JSON: {...}`

Screenshot: doc/img.png


## How it works

### Valid ping

Request includes `Stripe-Signature` header. Lambda verifies using `STRIPE_WEBHOOK_SECRET`.

### Invalid ping

Requests without signature return `400 Missing stripe-signature header`.

## AWS Setup (Console)

1. Create API Gateway HTTP API
2. Route: `POST /webhook/stripe`
3. Integration -> Lambda function: `agent1-ingestion-placeholder`
4. Lambda env var:
   - `STRIPE_WEBHOOK_SECRET=whsec_...`
5. Attach Stripe SDK Lambda Layer
6. Test with Stripe Payment Link (Sandbox)
