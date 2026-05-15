# Bob Sessions Directory

## Purpose

This directory contains all exported IBM Bob task session reports for the PHRAXIS hackathon submission. Each session file documents Bob's work during code generation, providing complete transparency and audit trail for judges.

## What's Included

Each Bob session file contains:

1. **Command Executed**: The exact Bob Shell command that was run
2. **Timestamp**: When the session occurred (UTC)
3. **Output**: Complete stdout from Bob (JSON results, generated code, analysis)
4. **Errors**: Any stderr output or error messages
5. **Exit Code**: Process exit status
6. **Execution Time**: How long Bob took to complete the task

## File Naming Convention

Files are named with timestamps and task descriptions:

```
bob_session_YYYYMMDD_HHMMSS_microseconds.json
```

Example:
```
bob_session_20240115_143022_abc123.json
```

## Session Types

### Architect Sessions
Files containing Bob's repository analysis:
- Complete file structure mapping
- Function and class identification
- Pattern recognition results
- Change location identification

### Plan Sessions
Files containing Bob's implementation plans:
- Step-by-step implementation roadmap
- File paths and operations
- Dependency ordering
- Change descriptions

### Code Sessions
Files containing Bob's generated code:
- Complete file contents
- Code that matches existing patterns
- Production-ready implementations
- Test files

### Review Sessions
Files containing Bob's code validation:
- Bug detection results
- Security analysis
- Style consistency checks
- Quality assessment

## Example Session File

```json
{
  "timestamp": "2024-01-15T14:30:22.123456Z",
  "command": "bob --non-interactive \"Switch to Architect mode. Read every file in ../demo_repo...\"",
  "exit_code": 0,
  "stdout": "{\"files_to_modify\": [\"app.py\"], \"new_files_to_create\": [\"middleware/rate_limiter.py\"]...}",
  "stderr": "",
  "execution_time": 45.3
}
```

## For Judges

These session files provide complete transparency into:

1. **How Bob was used**: Every command executed
2. **What Bob analyzed**: Full repository context
3. **What Bob generated**: Complete code output
4. **How Bob validated**: Review results

All sessions are automatically exported by the `BobShellRunner` utility in `backend/services/bob_shell_runner.py`.

## Verification

To verify a session:

1. Open the JSON file
2. Check the `command` field for what was requested
3. Review the `stdout` field for Bob's output
4. Verify `exit_code` is 0 (success)
5. Check `execution_time` for performance

## Session Integrity

Each session file is:
- **Immutable**: Written once, never modified
- **Complete**: Contains all input and output
- **Timestamped**: Precise execution time recorded
- **Traceable**: Links to specific PR and intent

## Demo Session Flow

For the rate limiting demo, you'll find these sessions:

1. **Architect Session**: Bob reads demo_repo and maps structure
2. **Plan Session**: Bob creates implementation plan
3. **Code Session (middleware)**: Bob generates rate_limiter.py
4. **Code Session (app.py)**: Bob modifies Flask routes
5. **Code Session (tests)**: Bob generates test_rate_limiter.py
6. **Review Session**: Bob validates generated code

Total: 6 session files documenting the complete workflow

## Additional Documentation

Each session can be cross-referenced with:
- **GitHub PR**: Links to the pull request created
- **Intent Record**: Stored in IBM Cloudant
- **Frontend Logs**: Real-time progress shown to user

## Questions?

For questions about Bob sessions, see:
- `BOB_USAGE.md` - Detailed Bob integration documentation
- `backend/services/bob_shell_runner.py` - Session export implementation
- `backend/services/bob_orchestrator.py` - Orchestration logic

---

