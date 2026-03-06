⚠️ BLOCKED

1. [CRITICAL] routes.py ~L18: Bare except clause catches all exceptions without specificity — replace `except Exception:` with specific exceptions like `SQLAlchemyError` for database errors
2. [CRITICAL] routes.py ~L32: Bare except clause catches all exceptions without specificity — replace `except Exception:` with specific exceptions like `SQLAlchemyError` for database errors

📚 LEARNINGS (compressed):
1. [high] All foreign keys must specify ondelete behavior: ForeignKey('table.id', ondelete='CASCADE')
2. [high] Add pagination to list endpoints: Query(skip, limit with max 100)
3. [high] Missing type hints on functions - add to all public functions
4. [high] Bare except clause found - use explicit exception types
5. [high] Missing input validation - validate all user inputs