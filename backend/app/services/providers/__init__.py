"""
External notification provider adapters.

Each module implements one delivery provider and exposes an async
``send(user, body, ...) -> ChannelResult`` used by
``app.services.notification_channels``. Adapters own their configuration
checks (graceful ``skipped`` results when credentials are unset) and the
HTTP call; they never raise for provider-level failures.

PHI note: never log message bodies or phone numbers — identifiers
(user_id, channel, status) only.
"""
