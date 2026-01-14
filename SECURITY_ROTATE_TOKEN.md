Rotate exposed Telegram bot token
================================

Suggested git commit message (use when you remove or replace a leaked token):

    docs(security): rotate Telegram bot token after accidental exposure

Short rationale:
- The repository previously contained a real Telegram bot token in `.env.example`.
- Tokens are credentials; rotating them prevents abuse and limits blast radius.

Recommended steps
-----------------
1. Revoke the exposed token in BotFather and create a new token.
2. Remove the exposed token from any committed files (already done).
3. Add the new token only to your local `.env` (ensure `.env` is in `.gitignore`).
4. Commit the change with the suggested commit message above.
5. Check repository history for other exposures and rotate any other leaked secrets.

Optional: rotate related secrets (chat ids are lower risk but rotate tokens that allow write access).

If you want, I can run an automated scan for common secret patterns in the repo and open a report.
