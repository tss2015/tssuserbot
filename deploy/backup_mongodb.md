# MongoDB backup

The bot stores encrypted sessions and task metadata in MongoDB.

Recommended production practice:
- Enable MongoDB Atlas backups.
- Restrict database network access.
- Use a dedicated database user.
- Rotate credentials periodically.
- Never export the encrypted session collection into logs or public artifacts.

The bot does not store OTPs or 2FA passwords.
