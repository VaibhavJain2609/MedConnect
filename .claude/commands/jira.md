---
description: Jira workflow integration - fetch TODO tickets and implement them
---

You are a Jira workflow orchestrator for the MedConnect project.

When the user invokes this command with `/jira`, your task is to:

1. **Fetch TODO tickets** from Jira Cloud using the jira_cli.py utility
2. **Present tickets** to the user in a clear, organized format
3. **Get user selection** on which ticket(s) to work on
4. **For each selected ticket:**
   - Create a git branch named `{ticket-key}-{slugified-summary}`
   - Transition the Jira ticket to "In Progress"
   - Use `/workflow` to implement the ticket
   - After successful implementation, add a comment to the ticket with branch/commit info
   - Optionally transition to "Done" if tests pass

## Available Tools

The Jira CLI utility is located at `.claude/jira_cli.py` and supports:

```bash
# List all TODO tickets
python3 .claude/jira_cli.py list

# Show detailed ticket info
python3 .claude/jira_cli.py show MED-123

# Start work on a ticket (creates branch + moves to In Progress)
python3 .claude/jira_cli.py start MED-123

# Mark ticket complete (adds comment + moves to Done)
python3 .claude/jira_cli.py complete MED-123 -c "Additional notes"

# Get JSON output for programmatic use
python3 .claude/jira_cli.py json
```

## Workflow Steps

### Step 1: Fetch Tickets
Run `python3 .claude/jira_cli.py json` to get all TODO tickets in JSON format.

### Step 2: Present to User
Show tickets in a clear format with priority and type:
```
Found 5 TODO tickets:

1. MED-15 [Story] Implement medicine autocomplete API - Priority: Highest (Epic: MED-7)
2. MED-22 [Story] Add role-based access control middleware - Priority: High (Epic: MED-3)
3. MED-31 [Task] Setup PostgreSQL indexes for medicine search - Priority: Medium
...
```

Ask user: "Which ticket(s) would you like to work on? (Enter number(s) or 'all')"

### Step 3: Implement Each Ticket

For each selected ticket:

```bash
# 1. Start the ticket (creates branch + moves to In Progress)
python3 .claude/jira_cli.py start MED-15

# 2. Show ticket details for context
python3 .claude/jira_cli.py show MED-15

# 3. Run the workflow (this should happen automatically)
# Use the /workflow command with the ticket summary and description as context
```

Then call the `/workflow` skill with a prompt like:
```
Implement MED-15: {summary}

Description:
{description}

Epic context: {epic_name}
```

### Step 4: Complete Ticket

After successful implementation (tests pass, code committed):

```bash
# Mark ticket as complete
python3 .claude/jira_cli.py complete MED-15 -c "Implemented with TDD, all tests passing"
```

## Error Handling

- If Jira credentials are missing, instruct user to set them in `.env`
- If ticket transition fails, continue with implementation but warn user
- If implementation fails, keep ticket in "In Progress" and report error
- If tests fail, do NOT mark ticket as Done

## Integration with /workflow

The `/workflow` command will handle:
- Research (if needed)
- Planning
- Implementation with TDD
- Git commit with co-author attribution

Your job is to:
- Orchestrate the Jira-git-workflow integration
- Manage ticket state transitions
- Link commits back to Jira tickets

## Example Usage

User: `/jira`

You should:
1. Fetch tickets: `python3 .claude/jira_cli.py json`
2. Present formatted list to user
3. Get user selection
4. For each ticket:
   - Start it: `python3 .claude/jira_cli.py start MED-XX`
   - Get details: `python3 .claude/jira_cli.py show MED-XX`
   - Implement it: Use `/workflow` with ticket context
   - Complete it: `python3 .claude/jira_cli.py complete MED-XX`

## Branch Naming Convention

Branches are automatically named: `{ticket-key}-{summary-slug}`

Examples:
- `med-15-implement-medicine-autocomplete-api`
- `med-22-add-role-based-access-control`

## Commit Message Convention

Commits should reference the Jira ticket:

```
[MED-15] Implement medicine autocomplete API

- Added search endpoint with fuzzy matching
- Implemented caching for performance
- Added unit tests with 95% coverage

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Configuration

Required environment variables in `.env`:
```
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token
JIRA_PROJECT_KEY=MED
```

## Notes

- Always verify Jira credentials before starting
- Keep ticket state in sync with actual progress
- Use semantic commit messages
- Link all commits back to Jira tickets
- Run tests before marking tickets as Done
- Handle Epic context when implementing stories
