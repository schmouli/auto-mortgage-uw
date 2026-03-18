⚠️ BLOCKED  
Issue 1: **Missing `updated_at` field on `UserSession` model**  
The `UserSession` table does not include an `updated_at` column, which violates the mandatory audit field requirement.  
🔧 **Fix**: Add `updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())` to the `UserSession` model.

Issue 2: **Email column missing index**  
The `email` column in the `User` model lacks a database index, causing performance issues for login and user lookup queries.  
🔧 **Fix**: Add `Index('ix_user_email', 'email')` to the `User` model to ensure efficient lookups.

Issue 3: **Foreign key `user_id` in `UserSession` missing `ondelete` policy**  
The `user_id` foreign key in `UserSession` does not define an `ondelete` behavior, risking orphaned records or constraint violations.  
🔧 **Fix**: Update the ForeignKey definition to include `ondelete="CASCADE"` to automatically remove sessions when a user is deleted.

Issue 4: **Lazy-loading relationship detected in `User.sessions`**  
The `User` model defines a `sessions` relationship without specifying eager loading, leading to potential N+1 query issues in services.  
🔧 **Fix**: In `services.py`, ensure queries involving `User` join `UserSession` using `selectinload(User.sessions)` or equivalent.

Issue 5: **No pagination enforced in `get_users` service method**  
The `get_users` function in `services.py` does not implement skip/limit-based pagination, risking memory exhaustion with large datasets.  
🔧 **Fix**: Modify the service method to accept `skip` and `limit` parameters (max limit: 100), and apply them in the SQLAlchemy query.