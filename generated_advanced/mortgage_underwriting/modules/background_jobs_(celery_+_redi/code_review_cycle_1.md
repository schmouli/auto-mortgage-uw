⚠️ BLOCKED

1. [HIGH] models.py ~L35: Missing index on foreign key column `triggered_by` — add `index=True` to mapped_column
2. [HIGH] routes.py ~L73 & services.py ~L107: Missing pagination on list endpoint `get_scheduled_jobs` — add skip/limit parameters with max 100
3. [MEDIUM] services.py ~L1-8: Unused imports `Decimal` and `selectinload` — remove unused imports
4. [MEDIUM] routes.py ~L1-6: Unused imports `Decimal` and `Query` — remove unused imports
5. [MEDIUM] models.py ~L40: Unused relationship `trigger_user` — remove relationship or add eager loading and include in response schema