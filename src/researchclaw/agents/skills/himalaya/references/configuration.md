# Himalaya Configuration Reference

## Full Configuration Example

```toml
[accounts.default]
email = "you@example.com"
display-name = "Your Name"
default = true
folder.alias.inbox = "INBOX"
folder.alias.sent = "Sent"
folder.alias.drafts = "Drafts"
folder.alias.trash = "Trash"

# IMAP backend
backend.type = "imap"
backend.host = "imap.example.com"
backend.port = 993
backend.encryption = "tls"        # tls | start-tls | none
backend.login = "you@example.com"
backend.auth.type = "password"
backend.auth.raw = "your-password"

# SMTP for sending
message.send.backend.type = "smtp"
message.send.backend.host = "smtp.example.com"
message.send.backend.port = 465
message.send.backend.encryption = "tls"
message.send.backend.login = "you@example.com"
message.send.backend.auth.type = "password"
message.send.backend.auth.raw = "your-password"
```

## Common Provider Settings

### Gmail
```toml
backend.host = "imap.gmail.com"
backend.port = 993
message.send.backend.host = "smtp.gmail.com"
message.send.backend.port = 465
```
**Note**: Use App Password from Google Account → Security → 2-Step Verification → App passwords

### Outlook / Microsoft 365
```toml
backend.host = "outlook.office365.com"
backend.port = 993
message.send.backend.host = "smtp.office365.com"
message.send.backend.port = 587
message.send.backend.encryption = "start-tls"
```

### Yahoo Mail
```toml
backend.host = "imap.mail.yahoo.com"
backend.port = 993
message.send.backend.host = "smtp.mail.yahoo.com"
message.send.backend.port = 465
```

## OAuth2 Authentication

```toml
backend.auth.type = "oauth2"
backend.auth.method = "xoauth2"
backend.auth.client-id = "your-client-id"
backend.auth.client-secret = "your-client-secret"
backend.auth.auth-url = "https://accounts.google.com/o/oauth2/auth"
backend.auth.token-url = "https://oauth2.googleapis.com/token"
backend.auth.scopes = ["https://mail.google.com/"]
```

## Search Syntax (IMAP)

| Query | Description |
|-------|-------------|
| `subject:keyword` | Search in subject |
| `from:email@example.com` | Search by sender |
| `to:email@example.com` | Search by recipient |
| `body:keyword` | Search in body |
| `seen` / `unseen` | Read / unread |
| `flagged` / `unflagged` | Starred / not starred |
| `before:2024-01-01` | Before date |
| `since:2024-01-01` | Since date |
| `AND` / `OR` / `NOT` | Logical operators |

## Troubleshooting

- **Connection refused**: Check host/port/encryption settings
- **Authentication failed**: Verify credentials, use App Password for Gmail
- **Folder not found**: Use `himalaya folder list` to see available folder names
- **Timeout**: Check network connectivity and firewall settings
