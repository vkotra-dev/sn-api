# API Error Handling

# Standard Error Format

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```

---

# Error Codes

| Code | HTTP | Meaning |
|---|---|---|
| `UNAUTHORIZED` | 401 | Login required |
| `FORBIDDEN` | 403 | Access denied |
| `LAYOUT_NOT_FOUND` | 404 | Layout does not exist |
| `PLOT_NOT_FOUND` | 404 | Plot does not exist |
| `LAYOUT_PROCESSING` | 409 | Layout is still being processed — not yet available |
| `LAYOUT_FAILED` | 422 | Layout processing failed — re-upload required |
| `INVALID_STATUS` | 400 | Status value not recognised |
| `INVALID_STATUS_TRANSITION` | 400 | Status transition not permitted by rules |
| `INVALID_UPLOAD` | 400 | File missing, wrong type, empty, or too large |
| `DUPLICATE_LAYOUT_NAME` | 409 | A layout with this name already exists |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

# Rules

Never expose stack traces to users.

Always return `application/json` even for error responses.

For `INVALID_STATUS_TRANSITION`, include the attempted transition in the message:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_STATUS_TRANSITION",
    "message": "Cannot transition from sold to available"
  }
}
```
