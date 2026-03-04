# Himalaya – Email Management

- name: himalaya
- description: Read, search, and organize emails via the himalaya CLI (IMAP/SMTP). Useful for managing research correspondence, collaboration, and paper submission communications.
- emoji: 📧
- requires:
  bins: ["himalaya"]

## Installation

```bash
# macOS
brew install himalaya

# Linux
curl -sSL https://raw.githubusercontent.com/pimalaya/himalaya/master/install.sh | bash

# Or via cargo
cargo install himalaya
```

## Configuration

Create `~/.config/himalaya/config.toml`:

```toml
[accounts.default]
email = "you@example.com"
display-name = "Your Name"
default = true

backend.type = "imap"
backend.host = "imap.example.com"
backend.port = 993
backend.login = "you@example.com"
backend.auth.type = "password"
backend.auth.raw = "your-app-password"

message.send.backend.type = "smtp"
message.send.backend.host = "smtp.example.com"
message.send.backend.port = 465
message.send.backend.login = "you@example.com"
message.send.backend.auth.type = "password"
message.send.backend.auth.raw = "your-app-password"
```

For Gmail, use an App Password (not your regular password) and:
- IMAP host: `imap.gmail.com`, port: `993`
- SMTP host: `smtp.gmail.com`, port: `465`

## Core Operations

### List folders
```bash
himalaya folder list
```

### List emails
```bash
himalaya envelope list                    # default inbox
himalaya envelope list -f "Sent"          # sent folder
himalaya envelope list -s 20              # page size 20
himalaya envelope list -p 2               # page 2
```

### Search emails
```bash
himalaya envelope list -f INBOX "subject:paper review"
himalaya envelope list -f INBOX "from:colleague@university.edu"
himalaya envelope list -f INBOX "subject:ICML AND unseen"
```

### Read an email
```bash
himalaya message read <id>                # plain text
himalaya message read <id> -h             # with headers
```

### Move / Copy / Delete
```bash
himalaya message move <id> -f INBOX "Archive"
himalaya message copy <id> -f INBOX "Important"
himalaya message delete <id>
```

### Flag management
```bash
himalaya flag add <id> seen               # mark as read
himalaya flag remove <id> seen            # mark as unread
himalaya flag add <id> flagged            # star
```

### Download attachments
```bash
himalaya attachment download <id>         # save to current dir
himalaya attachment download <id> -o ~/Downloads/
```

### Multi-account
```bash
himalaya envelope list --account work
himalaya message read 42 --account personal
```

## DISABLED Operations (Security)

The following operations are **disabled** for safety:
- ❌ Sending new emails
- ❌ Replying to emails
- ❌ Forwarding emails

These require explicit user action. If the user asks to send an email, explain that sending is disabled for security and suggest they do it manually.

## Research Use Cases

- Check for paper review notifications
- Search for conference deadline emails
- Find collaboration discussion threads
- Download paper drafts sent as attachments
- Monitor journal submission status emails
- Organize research correspondence into folders

## Rules

- NEVER send, reply to, or forward emails (disabled for security)
- Always check if himalaya is installed before using: `which himalaya`
- If not configured, guide the user through the config.toml setup
- Respect the user's privacy — don't read emails without being asked
- When listing emails, show a reasonable page size (10-20)
- For search, use IMAP search syntax
