---
description: Check that the live dashboard server is connected and running queries as you
---

Call the `whoami` tool on the semantic-explorer-dashboards server and report the Snowflake user, role and secondary roles it returns. Say whether the user matches the person you are talking to (ask them if unsure). Then call `render_dashboard` on a small semantic view the user names, or, if they name none, list the views you can see and offer one. If any call fails, show the exact error and tell the user it is safe to keep using the core plugin without live dashboards.
