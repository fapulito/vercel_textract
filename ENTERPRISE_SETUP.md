# Enterprise Tier Setup Guide

## Overview
Task 9 has been completed. The application now supports Enterprise tier subscriptions with API key generation.

## What Was Implemented

### 1. Stripe Integration Updates (Task 9.1)
- Added `STRIPE_ENTERPRISE_PRICE_ID` environment variable
- Updated checkout session creation to support Pro and Enterprise tiers
- Enhanced webhook handler to process Enterprise subscriptions
- Added subscription cancellation handling

### 2. API Key Management (Task 9.2)
- Created `/api/generate-key` endpoint for Enterprise users
- Created `/api/revoke-key` endpoint to revoke API keys
- Added UI in index.html for API key management
- Keys are cryptographically secure (64 characters with `cvocr_` prefix)

## Required Setup Steps

### Step 1: Create Enterprise Price in Stripe Dashboard

1. Go to your Stripe Dashboard: https://dashboard.stripe.com/
2. Navigate to **Products** → **Add Product**
3. Create a new product:
   - **Name**: California Vision OCR - Enterprise Plan
   - **Description**: 1000 documents/month, 500 AI analyses, 100 pages max, 50MB files, API access
   - **Pricing**: $99.00 USD / month (recurring)
   - **Billing period**: Monthly
4. After creating, copy the **Price ID** (starts with `price_`)
5. Add it to your `.env` file:
   ```
   STRIPE_ENTERPRISE_PRICE_ID="price_YOUR_ENTERPRISE_PRICE_ID_HERE"
   ```

### Step 2: Update Vercel Environment Variables

Add the new environment variable to your Vercel deployment:
```bash
vercel env add STRIPE_ENTERPRISE_PRICE_ID
```
Or add it through the Vercel dashboard under Settings → Environment Variables.

### Step 3: Test the Implementation

1. **Test Checkout Flow**:
   - Visit your app as a free user
   - Click "Enterprise - $99/month" button
   - Complete test checkout (use Stripe test card: 4242 4242 4242 4242)

2. **Test Webhook**:
   - Ensure webhook receives `checkout.session.completed` event
   - Verify user tier is updated to `enterprise` in database
   - Check that metadata includes `tier: enterprise`

3. **Test API Key Generation**:
   - Log in as an Enterprise user
   - Click "Generate API Key" button
   - Verify key is displayed and stored in database
   - Test "Revoke API Key" functionality

## New Routes Added

- `GET /create-checkout-session/subscription/enterprise` - Enterprise checkout
- `GET /create-checkout-session/subscription/pro` - Pro checkout (explicit)
- `POST /api/generate-key` - Generate API key (Enterprise only)
- `POST /api/revoke-key` - Revoke API key (Enterprise only)

## Database Schema

The existing `User` model already has the required fields:
- `api_key` (String, 64 chars, unique, nullable)
- `api_key_created` (DateTime, nullable)
- `tier` (String, supports 'free', 'pro', 'enterprise')

## UI Updates

### For Free Users:
- Shows 3-column plan comparison (Free, Pro, Enterprise)
- Two upgrade buttons: "Pro - $10/month" and "Enterprise - $99/month"

### For Pro Users:
- Shows Pro badge
- No API key section (Pro doesn't have API access)

### For Enterprise Users:
- Shows Enterprise badge with building icon
- API Key Management section with:
  - Generate API Key button (if no key exists)
  - Active key status (if key exists)
  - Revoke API Key button (if key exists)
  - Copy to clipboard functionality

## Security Features

1. **API Key Generation**:
   - Uses `secrets.token_urlsafe(48)` for cryptographic security
   - Prefixed with `cvocr_` for easy identification
   - Stored in database (consider hashing in production)
   - Only shown once to user

2. **Access Control**:
   - API key endpoints require Enterprise tier
   - Returns 403 Forbidden for non-Enterprise users
   - Login required for all endpoints

3. **Webhook Security**:
   - Signature verification using `STRIPE_WEBHOOK_SECRET`
   - Validates event type before processing
   - Handles subscription cancellations

## Next Steps

After completing this setup:
1. Test the complete flow end-to-end
2. Consider implementing tasks 10-11 for API endpoints and cost tracking
3. Update README-2.md with Enterprise tier documentation (Task 12)

## Troubleshooting

**Issue**: Checkout redirects but tier doesn't update
- **Solution**: Check webhook is configured and receiving events
- Verify `STRIPE_WEBHOOK_SECRET` is correct
- Check Vercel logs for webhook errors

**Issue**: API key generation fails
- **Solution**: Verify user tier is exactly 'enterprise' (lowercase)
- Check database connection
- Ensure `api_key` column exists in users table

**Issue**: Enterprise price not found
- **Solution**: Verify `STRIPE_ENTERPRISE_PRICE_ID` is set correctly
- Check the price ID exists in your Stripe account
- Ensure you're using the correct Stripe account (test vs live)
