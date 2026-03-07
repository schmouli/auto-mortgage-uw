⚠️ BLOCKED

1. [CRITICAL] services.py ~L52: Async ORM error when accessing unloaded relationship `user.client_portal_user.last_login_at` — add `.options(selectinload(User.client_portal_user))` to the query on line ~45
2. [HIGH] services.py ~L57: `UserResponse.role` is always `None` because it's not populated from `user.client_portal_user.role` — manually construct user data dict including role before validation

---

**Exact fixes needed:**

**Issue 1:** Update the query in `authenticate_user` to eagerly load the relationship:
```python
# Line ~45
stmt = select(User).where(User.username == credentials.username).options(selectinload(User.client_portal_user))
```

**Issue 2:** Populate the role field before validation:
```python
# Line ~57
user_data = {
    "id": user.id,
    "username": user.username,
    "email": user.email,
    "first_name": user.first_name,
    "last_name": user.last_name,
    "role": user.client_portal_user.role if user.client_portal_user else None
}
user_response = UserResponse.model_validate(user_data)
```

**Note:** All 5 LEARNINGS issues have been addressed (indexes, updated_at fields, foreign key ondelete, pagination, and type hints), but the critical runtime errors above must be fixed before approval.