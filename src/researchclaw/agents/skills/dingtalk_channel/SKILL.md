# DingTalk Channel Connect

- name: dingtalk_channel_connect
- description: Use a visible browser to automatically set up ResearchClaw's DingTalk channel integration — creating an enterprise app, configuring the bot, and publishing.
- emoji: 🤖
- requires: []

## Overview

This skill automates the process of connecting ResearchClaw to DingTalk by:
1. Opening the DingTalk Developer Portal in a visible browser
2. Creating an enterprise internal application
3. Adding and configuring the bot capability
4. Publishing the application
5. Retrieving credentials for ResearchClaw configuration

## Step-by-Step Flow

### Step 1: Open DingTalk Developer Portal
```json
{"action": "start", "headed": true}
```
```json
{"action": "open", "url": "https://open-dev.dingtalk.com/"}
```

### Step 2: Handle Login
- Take a snapshot to check if login is needed
- If login page appears: **PAUSE** and ask the user to manually log in
- Wait for the user to confirm they've logged in before continuing

### Step 3: Create Application
1. Navigate to "应用开发" (Application Development)
2. Click "创建应用" (Create Application)
3. Fill in:
   - Name: `ResearchClaw` (or user-specified name)
   - Description: `ResearchClaw AI Research Assistant`
   - Type: Enterprise Internal Application (企业内部应用)

### Step 4: Add Bot Capability
1. Go to "添加能力" (Add Capability)
2. Select "机器人" (Bot)
3. Configure bot settings:
   - Bot name: `ResearchClaw`
   - Upload icon (if provided)
   - Set the message receiving mode

### Step 5: Publish
1. Navigate to "版本管理与发布" (Version Management)
2. Create a new version
3. **Publish the version** (必须发布才能生效)

### Step 6: Get Credentials
1. Go to application's basic information page
2. Copy the **Client ID** (AppKey) and **Client Secret** (AppSecret)
3. Present them to the user

### Step 7: Configure ResearchClaw
Guide the user to set environment variables or update config:
```bash
export DINGTALK_CLIENT_ID="your-client-id"
export DINGTALK_CLIENT_SECRET="your-client-secret"
export DINGTALK_CHANNEL_ENABLED="1"
```

Or add to `~/.researchclaw/config.json`.

## Critical Rules

- **Any configuration change requires a new version + publish** — changes don't take effect until published
- **NEVER modify config files without explicit user permission**
- On any login page, PAUSE and let the user handle authentication
- Always snapshot after each navigation to verify the page state
- If the portal UI changes, adapt based on snapshots rather than failing
- Always stop the browser when done
