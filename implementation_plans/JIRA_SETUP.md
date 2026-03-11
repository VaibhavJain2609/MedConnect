# Jira Cloud Integration Setup Guide

This guide will help you set up the Jira Cloud integration for MedConnect.

## Prerequisites

- Jira Cloud account with access to your MedConnect project
- Admin access to generate API tokens
- Python 3.7+ (already installed)

## Step 1: Create Jira API Token

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **"Create API token"**
3. Give it a name like "MedConnect Claude Integration"
4. Click **"Create"**
5. **Copy the token immediately** (you won't be able to see it again)

## Step 2: Find Your Jira Information

You need to find:

1. **Jira Base URL**:
   - Look at your Jira URL when logged in
   - Format: `https://your-domain.atlassian.net`
   - Example: `https://medconnect-team.atlassian.net`

2. **Your Email**:
   - The email you use to log into Jira
   - Example: `vaibhav@example.com`

3. **Project Key**:
   - Look at your ticket numbers
   - If your tickets are like "MED-15", the key is "MED"
   - Or go to Project Settings → Details

## Step 3: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your Jira credentials:
   ```bash
   # Add these lines to .env (update with your actual values)
   JIRA_BASE_URL=https://your-domain.atlassian.net
   JIRA_EMAIL=your-email@example.com
   JIRA_API_TOKEN=your-token-from-step-1
   JIRA_PROJECT_KEY=MED
   ```

3. **Important**: Never commit `.env` to git! It's already in `.gitignore`.

## Step 4: Install Python Dependencies

The Jira CLI uses the `requests` library:

```bash
cd backend
source .venv/bin/activate  # or: source venv/bin/activate
pip install requests
```

Or add to `backend/requirements.txt`:
```
requests==2.31.0
```

## Step 5: Test the Integration

Test if everything works:

```bash
# From project root
python3 .claude/jira_cli.py list
```

You should see your TODO tickets listed. If you get errors:

- **"Missing Jira credentials"**: Check your `.env` file
- **"Authentication failed"**: Verify your email and API token
- **"Project not found"**: Check your project key
- **"Connection refused"**: Check your base URL

## Step 6: Verify Jira Workflow States

Your Jira project should have these workflow states:
- **To Do** (or "TODO")
- **In Progress**
- **Done**

If your project uses different names, update the transitions in `.claude/jira_cli.py`:
- Line ~66: Change `"To Do"` to your TODO status name
- Line ~99-100: Change `"In Progress"` and `"Done"` to match your workflow

To check your workflow:
1. Go to Jira → Project Settings → Workflows
2. Note the exact names of your statuses

## Usage

Once set up, use the `/jira` command in Claude Code:

```bash
/jira
```

This will:
1. ✅ Fetch all TODO tickets from Jira
2. ✅ Show them in a prioritized list
3. ✅ Let you select which to work on
4. ✅ Create a git branch for each ticket
5. ✅ Move ticket to "In Progress"
6. ✅ Implement the feature using `/workflow`
7. ✅ Add commit info back to Jira
8. ✅ Move ticket to "Done" when tests pass

## Manual CLI Usage

You can also use the Jira CLI directly:

```bash
# List all TODO tickets
python3 .claude/jira_cli.py list

# Show detailed info for a specific ticket
python3 .claude/jira_cli.py show MED-15

# Start working on a ticket (creates branch + moves to In Progress)
python3 .claude/jira_cli.py start MED-15

# Mark ticket as complete (adds comment + moves to Done)
python3 .claude/jira_cli.py complete MED-15

# Get JSON output for scripting
python3 .claude/jira_cli.py json
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'requests'"

Install the requests library:
```bash
cd backend
source .venv/bin/activate
pip install requests
```

### "401 Unauthorized"

- Verify your email is correct
- Verify your API token is correct (no extra spaces)
- Make sure you're using an API token, not your password
- Try generating a new API token

### "Transition 'In Progress' not found"

Your Jira workflow uses different state names. Update the CLI:
1. Open `.claude/jira_cli.py`
2. Find the `transition_ticket` method
3. Update the transition names to match your workflow

### No tickets showing up

- Check your JQL query in the CLI (line ~66)
- Verify your project key is correct
- Make sure you have tickets in "To Do" status
- Try running in Jira: `project = MED AND status = "To Do"`

## Security Notes

- ✅ `.env` is in `.gitignore` - never commit it
- ✅ API tokens are safer than passwords
- ✅ You can revoke tokens anytime in Atlassian account settings
- ✅ Use a separate token for each integration

## Next Steps

1. ✅ Complete this setup
2. Run `/jira` to test the integration
3. Select a small ticket to test the workflow
4. Verify the ticket moves through states correctly
5. Check that commits are linked back to Jira

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify all environment variables are set correctly
3. Test Jira API access directly: https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/
4. Check Jira API token permissions

---

**Ready to use?** Run `/jira` and start implementing your tickets!
