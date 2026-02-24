#!/usr/bin/env python3
"""
Jira Cloud CLI for MedConnect
Integrates Jira tickets with git workflow
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Optional
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth

# Load .env file from project root
try:
    from dotenv import load_dotenv
    # Find project root (where .env should be)
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    load_dotenv(env_path)
except ImportError:
    # If python-dotenv is not installed, try to load .env manually
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()


class JiraClient:
    def __init__(self):
        self.base_url = os.getenv('JIRA_BASE_URL', '').rstrip('/')
        self.email = os.getenv('JIRA_EMAIL')
        self.api_token = os.getenv('JIRA_API_TOKEN')
        self.project_key = os.getenv('JIRA_PROJECT_KEY', 'MED')

        if not all([self.base_url, self.email, self.api_token]):
            print("ERROR: Missing Jira credentials. Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN", file=sys.stderr)
            sys.exit(1)

        self.auth = HTTPBasicAuth(self.email, self.api_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def _verify_connection(self):
        """Verify Jira connection and permissions"""
        try:
            # Test basic connectivity
            url = f"{self.base_url}/rest/api/2/myself"
            response = requests.get(url, auth=self.auth, headers=self.headers)
            if response.status_code == 200:
                user_data = response.json()
                print(f"✅ Connected as: {user_data.get('displayName', 'Unknown')}", file=sys.stderr)
            else:
                print(f"❌ Authentication failed: {response.status_code}", file=sys.stderr)
                return

            # List accessible projects
            url = f"{self.base_url}/rest/api/2/project"
            response = requests.get(url, auth=self.auth, headers=self.headers)
            if response.status_code == 200:
                projects = response.json()
                print(f"\n📋 Accessible projects:", file=sys.stderr)
                for proj in projects[:5]:
                    print(f"  - {proj['key']}: {proj['name']}", file=sys.stderr)

                # Check if our project key is valid
                valid_keys = [p['key'] for p in projects]
                if self.project_key not in valid_keys:
                    print(f"\n❌ Project '{self.project_key}' not found!", file=sys.stderr)
                    print(f"   Available keys: {', '.join(valid_keys)}", file=sys.stderr)

        except Exception as e:
            print(f"Connection verification failed: {e}", file=sys.stderr)

    def get_todo_tickets(self, limit: int = 50) -> List[Dict]:
        """Fetch all tickets in TODO status"""
        # Try different status names - Jira can use "To Do", "TODO", or "Backlog"
        jql = f'project = {self.project_key} AND status in ("To Do", "TODO", "Backlog") ORDER BY priority DESC, created ASC'

        # Use new API v3 JQL endpoint
        url = f"{self.base_url}/rest/api/3/search/jql"
        params = {
            'jql': jql,
            'maxResults': limit,
            'fields': ['summary', 'description', 'issuetype', 'priority', 'status', 'assignee', 'labels', 'parent']
        }

        try:
            response = requests.post(url, auth=self.auth, headers=self.headers, json=params)
            response.raise_for_status()

            data = response.json()
            return data.get('issues', [])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [400, 410]:
                print(f"\nERROR: API request failed.", file=sys.stderr)
                print(f"Base URL: {self.base_url}", file=sys.stderr)
                print(f"Project Key: {self.project_key}", file=sys.stderr)
                print(f"Response: {e.response.text}", file=sys.stderr)
                print(f"\nTrying to verify connection...", file=sys.stderr)
                self._verify_connection()
            raise

    def get_ticket(self, issue_key: str) -> Dict:
        """Fetch a specific ticket"""
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        params = {'fields': 'summary,description,issuetype,priority,status,assignee,labels,parent'}

        response = requests.get(url, auth=self.auth, headers=self.headers, params=params)
        response.raise_for_status()

        return response.json()

    def transition_ticket(self, issue_key: str, transition_name: str) -> bool:
        """Move ticket to a different status (In Progress, Done, etc.)"""
        # First, get available transitions
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/transitions"
        response = requests.get(url, auth=self.auth, headers=self.headers)
        response.raise_for_status()

        transitions = response.json().get('transitions', [])
        transition_id = None

        for t in transitions:
            if t['name'].lower() == transition_name.lower():
                transition_id = t['id']
                break

        if not transition_id:
            print(f"Warning: Transition '{transition_name}' not found for {issue_key}", file=sys.stderr)
            return False

        # Execute transition
        payload = {"transition": {"id": transition_id}}
        response = requests.post(url, auth=self.auth, headers=self.headers, json=payload)
        response.raise_for_status()

        return True

    def add_comment(self, issue_key: str, comment: str) -> bool:
        """Add a comment to a ticket"""
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/comment"
        payload = {
            "body": comment
        }

        response = requests.post(url, auth=self.auth, headers=self.headers, json=payload)
        response.raise_for_status()

        return True

    def format_ticket(self, issue: Dict) -> str:
        """Format ticket for display"""
        fields = issue['fields']
        key = issue['key']
        summary = fields['summary']
        issue_type = fields['issuetype']['name']
        priority = fields.get('priority', {}).get('name', 'None')

        # Get parent epic if exists
        parent = fields.get('parent', {})
        parent_info = f" (Epic: {parent.get('key', '')})" if parent else ""

        return f"{key} [{issue_type}] {summary} - Priority: {priority}{parent_info}"


def cmd_list(client: JiraClient, args):
    """List all TODO tickets"""
    tickets = client.get_todo_tickets(limit=args.limit)

    if not tickets:
        print("No TODO tickets found.")
        return

    print(f"Found {len(tickets)} TODO tickets:\n")
    for ticket in tickets:
        print(client.format_ticket(ticket))


def cmd_show(client: JiraClient, args):
    """Show detailed ticket information"""
    ticket = client.get_ticket(args.ticket_key)
    fields = ticket['fields']

    print(f"Key: {ticket['key']}")
    print(f"Type: {fields['issuetype']['name']}")
    print(f"Summary: {fields['summary']}")
    print(f"Priority: {fields.get('priority', {}).get('name', 'None')}")
    print(f"Status: {fields['status']['name']}")
    print(f"\nDescription:")

    # Handle description (can be in ADF format or plain text)
    description = fields.get('description')
    if description:
        if isinstance(description, dict):
            # ADF format - extract text content
            print(_extract_adf_text(description))
        else:
            print(description)
    else:
        print("No description")


def cmd_start(client: JiraClient, args):
    """Start work on a ticket - transition to In Progress"""
    ticket = client.get_ticket(args.ticket_key)

    # Create git branch
    branch_name = f"{args.ticket_key.lower()}-{_slugify(ticket['fields']['summary'])}"

    print(f"Creating branch: {branch_name}")
    os.system(f'git checkout -b {branch_name}')

    # Transition ticket to In Progress
    print(f"Moving {args.ticket_key} to In Progress...")
    client.transition_ticket(args.ticket_key, "In Progress")

    print(f"\n✅ Ready to work on {args.ticket_key}")
    print(f"Branch: {branch_name}")


def cmd_complete(client: JiraClient, args):
    """Mark ticket as complete and add commit info"""
    # Get current branch
    branch = os.popen('git rev-parse --abbrev-ref HEAD').read().strip()
    commit_hash = os.popen('git rev-parse HEAD').read().strip()[:8]

    comment = f"Implemented in branch {branch} (commit {commit_hash})"
    if args.comment:
        comment = f"{args.comment}\n\n{comment}"

    print(f"Adding comment to {args.ticket_key}...")
    client.add_comment(args.ticket_key, comment)

    if not args.no_transition:
        print(f"Moving {args.ticket_key} to Done...")
        client.transition_ticket(args.ticket_key, "Done")

    print(f"✅ {args.ticket_key} marked as complete")


def cmd_json(client: JiraClient, args):
    """Output TODO tickets as JSON for programmatic use"""
    tickets = client.get_todo_tickets(limit=args.limit)

    output = []
    for ticket in tickets:
        fields = ticket['fields']
        output.append({
            'key': ticket['key'],
            'summary': fields['summary'],
            'description': _extract_description(fields.get('description')),
            'type': fields['issuetype']['name'],
            'priority': fields.get('priority', {}).get('name', 'None'),
            'parent': fields.get('parent', {}).get('key', None),
            'labels': fields.get('labels', [])
        })

    print(json.dumps(output, indent=2))


def _extract_adf_text(adf_doc: Dict) -> str:
    """Extract plain text from Atlassian Document Format"""
    if not adf_doc:
        return ""

    text = []

    def extract_content(node):
        if isinstance(node, dict):
            if node.get('type') == 'text':
                text.append(node.get('text', ''))
            if 'content' in node:
                for child in node['content']:
                    extract_content(child)
        elif isinstance(node, list):
            for item in node:
                extract_content(item)

    extract_content(adf_doc)
    return ''.join(text)


def _extract_description(description) -> str:
    """Extract description text regardless of format"""
    if not description:
        return ""
    if isinstance(description, dict):
        return _extract_adf_text(description)
    return str(description)


def _slugify(text: str) -> str:
    """Convert text to git-safe branch name"""
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:50]  # Limit length


def main():
    parser = argparse.ArgumentParser(description='Jira Cloud CLI for MedConnect')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # List command
    list_parser = subparsers.add_parser('list', help='List all TODO tickets')
    list_parser.add_argument('-l', '--limit', type=int, default=50, help='Maximum tickets to fetch')

    # Show command
    show_parser = subparsers.add_parser('show', help='Show ticket details')
    show_parser.add_argument('ticket_key', help='Ticket key (e.g., MED-123)')

    # Start command
    start_parser = subparsers.add_parser('start', help='Start work on a ticket')
    start_parser.add_argument('ticket_key', help='Ticket key to start')

    # Complete command
    complete_parser = subparsers.add_parser('complete', help='Mark ticket as complete')
    complete_parser.add_argument('ticket_key', help='Ticket key to complete')
    complete_parser.add_argument('-c', '--comment', help='Additional comment')
    complete_parser.add_argument('--no-transition', action='store_true', help='Do not move to Done')

    # JSON output command
    json_parser = subparsers.add_parser('json', help='Output tickets as JSON')
    json_parser.add_argument('-l', '--limit', type=int, default=50, help='Maximum tickets to fetch')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = JiraClient()

    commands = {
        'list': cmd_list,
        'show': cmd_show,
        'start': cmd_start,
        'complete': cmd_complete,
        'json': cmd_json
    }

    commands[args.command](client, args)


if __name__ == '__main__':
    main()
