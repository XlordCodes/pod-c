# Leads Module Logic & Security Audit Report

**Date:** 2026-02-14  
**Auditor:** Senior CRM Architect  
**Scope:** Leads Module (Models, Schemas, Repository, Service, API)

---

## Executive Summary

The Leads module has **3 CRITICAL business logic failures** that must be addressed immediately:

1. **CRITICAL: No State Lock on Converted Leads** - Converted leads can still be edited
2. **HIGH: No Duplicate Detection** - Multiple leads with same email/phone can be created
3. **MEDIUM: No Owner Validation** - Leads can be assigned to non-existent users
4. **LOW: SQL Injection Safe** - Queries use parameterized filters ✓

---

## 🔴 CRITICAL FINDINGS

### 1. State Consistency Failure: Converted Leads Can Be Edited (CRITICAL)

**Location:** [`app/repos/lead_repo.py:59-67`](app/repos/lead_repo.py:59)

**Issue:**  
The `update_status()` method does NOT check if a lead is already converted before allowing updates. There is NO endpoint to update lead details, but if one is added in the future, converted leads could be modified, breaking data integrity.

**Current Code (VULNERABLE):**
```python
def update_status(self, lead: Lead, new_status: str) -> Lead:
    """
    Updates the status of a lead instance.
    Note: The lead object must already be attached to the session.
    """
    lead.status = new_status  # <-- NO CHECK if already converted!
    self.db.commit()
    self.db.refresh(lead)
    return lead
```

**Impact:**
- Converted leads could be reverted to "new" or "contacted"
- Data integrity violation (a lead with a Deal should remain "converted")
- Audit trail corruption

**Fix Required:**

**Step 1:** Add validation to [`lead_repo.py:59`](app/repos/lead_repo.py:59):

```python
def update_status(self, lead: Lead, new_status: str) -> Lead:
    """
    Updates the status of a lead instance.
    
    BUSINESS RULE: Converted leads are immutable.
    Once a lead is converted, its status cannot be changed.
    
    Args:
        lead: The lead instance to update
        new_status: The new status value
        
    Returns:
        Updated lead
        
    Raises:
        ValueError: If attempting to modify a converted lead
    """
    # CRITICAL: Prevent modification of converted leads
    if lead.status == "converted":
        raise ValueError("Cannot modify a converted lead. Converted leads are immutable.")
    
    lead.status = new_status
    self.db.commit()
    self.db.refresh(lead)
    return lead
```

**Step 2:** Add an `update_lead()` method to LeadRepo with state lock:

```python
def update_lead(self, lead_id: int, tenant_id: int, updates: dict) -> Lead:
    """
    Updates a lead's details (name, email).
    
    BUSINESS RULE: Converted leads cannot be edited.
    
    Args:
        lead_id: ID of the lead to update
        tenant_id: Tenant ID for isolation
        updates: Dictionary of fields to update
        
    Returns:
        Updated lead
        
    Raises:
        ValueError: If lead is converted or not found
    """
    lead = self.get(lead_id, tenant_id)
    if not lead:
        raise ValueError("Lead not found")
    
    # CRITICAL: State lock - prevent editing converted leads
    if lead.status == "converted":
        raise ValueError("Cannot edit a converted lead. Converted leads are immutable.")
    
    # Apply updates
    for key, value in updates.items():
        if hasattr(lead, key) and key not in ['id', 'tenant_id', 'owner_id', 'status', 'created_at']:
            setattr(lead, key, value)
    
    self.db.commit()
    self.db.refresh(lead)
    return lead
```

---

### 2. Duplicate Detection Missing (HIGH)

**Location:** [`app/repos/lead_repo.py:21-35`](app/repos/lead_repo.py:21)

**Issue:**  
The `create()` method does NOT check if a lead with the same email or phone already exists for the tenant. This allows duplicate leads to be created, causing:
- Data quality issues
- Confusion in sales pipeline
- Wasted effort contacting the same person multiple times

**Current Code (VULNERABLE):**
```python
def create(self, tenant_id: int, owner_id: int, data: LeadCreate) -> Lead:
    """
    Persists a new lead in the database.
    """
    lead = Lead(
        tenant_id=tenant_id,
        owner_id=owner_id,
        name=data.name,
        email=data.email,  # <-- NO DUPLICATE CHECK!
        status="new"
    )
    self.db.add(lead)
    self.db.commit()
    self.db.refresh(lead)
    return lead
```

**Impact:**
- Multiple leads with same email/phone
- Sales team wastes time on duplicates
- Poor data quality

**Fix Required:**

Update [`lead_repo.py:21`](app/repos/lead_repo.py:21):

```python
def create(self, tenant_id: int, owner_id: int, data: LeadCreate) -> Lead:
    """
    Persists a new lead in the database.
    
    BUSINESS RULE: Duplicate Detection
    - If email is provided, check for existing lead with same email in tenant
    - If phone is provided (future), check for existing lead with same phone in tenant
    
    Args:
        tenant_id: Tenant context
        owner_id: User creating the lead
        data: Validated lead data
        
    Returns:
        Created lead
        
    Raises:
        ValueError: If duplicate lead exists
    """
    # CRITICAL: Duplicate detection by email
    if data.email:
        existing = (
            self.db.query(Lead)
            .filter(
                Lead.tenant_id == tenant_id,
                Lead.email == data.email
            )
            .first()
        )
        
        if existing:
            raise ValueError(
                f"A lead with email '{data.email}' already exists (ID: {existing.id}). "
                f"Please update the existing lead instead of creating a duplicate."
            )
    
    # Create new lead
    lead = Lead(
        tenant_id=tenant_id,
        owner_id=owner_id,
        name=data.name,
        email=data.email,
        status="new"
    )
    self.db.add(lead)
    self.db.commit()
    self.db.refresh(lead)
    return lead
```

**Alternative:** Add a database-level unique constraint:

```python
# In app/models/crm.py, add to Lead class:
__table_args__ = (
    UniqueConstraint('tenant_id', 'email', name='uq_lead_tenant_email'),
)
```

Then handle the `IntegrityError` in the repository:

```python
from sqlalchemy.exc import IntegrityError

try:
    self.db.commit()
except IntegrityError as e:
    self.db.rollback()
    if 'uq_lead_tenant_email' in str(e):
        raise ValueError(f"A lead with email '{data.email}' already exists")
    raise
```

---

### 3. Owner Validation Missing (MEDIUM)

**Location:** [`app/repos/lead_repo.py:21-35`](app/repos/lead_repo.py:21)

**Issue:**  
The `create()` method does NOT validate that `owner_id` refers to an existing user. Due to the foreign key constraint in the model ([`app/models/crm.py:102`](app/models/crm.py:102)), the database will reject invalid owner_ids, but the error message will be cryptic.

**Current Code:**
```python
owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
```

**Impact:**
- Cryptic database errors instead of clear business errors
- Poor user experience

**Fix Required:**

Add validation in [`lead_repo.py:21`](app/repos/lead_repo.py:21):

```python
def create(self, tenant_id: int, owner_id: int, data: LeadCreate) -> Lead:
    """
    Persists a new lead in the database.
    
    VALIDATION: Ensures owner_id refers to an existing user.
    """
    # VALIDATION: Check if owner exists
    from app.models.auth import User
    owner = self.db.query(User).filter(User.id == owner_id).first()
    if not owner:
        raise ValueError(f"Invalid owner_id: User {owner_id} does not exist")
    
    # VALIDATION: Check if owner belongs to the same tenant
    if owner.tenant_id != tenant_id:
        raise ValueError(
            f"Owner {owner_id} belongs to tenant {owner.tenant_id}, "
            f"but lead is being created for tenant {tenant_id}"
        )
    
    # ... rest of duplicate detection and creation logic
```

---

## 🟢 GOOD PRACTICES OBSERVED

### ✅ SQL Injection Safe

**Location:** [`app/repos/lead_repo.py:41-44`](app/repos/lead_repo.py:41), [`app/repos/lead_repo.py:50-56`](app/repos/lead_repo.py:50)

All queries use SQLAlchemy's parameterized filters:

```python
# SAFE: Uses parameterized query
return self.db.query(Lead).filter(
    Lead.id == lead_id,  # <-- Parameterized
    Lead.tenant_id == tenant_id  # <-- Parameterized
).first()
```

**Status:** ✅ **SECURE** - No SQL injection vulnerabilities found

### ✅ Tenant Isolation

All repository methods filter by `tenant_id`:
- [`get()`](app/repos/lead_repo.py:37): Filters by tenant_id
- [`list_all()`](app/repos/lead_repo.py:46): Filters by tenant_id

**Status:** ✅ **SECURE** - Tenant isolation properly enforced

### ✅ Idempotency Check

[`app/services/lead_service.py:107-108`](app/services/lead_service.py:107):
```python
if lead.status == "converted":
    raise ValueError("Lead has already been converted")
```

**Status:** ✅ **GOOD** - Prevents double-conversion

---

## 📋 PRIORITY ACTION ITEMS

| Priority | Issue | File | Line | Fix Complexity |
|----------|-------|------|------|----------------|
| 🔴 **P0** | No state lock on converted leads | `lead_repo.py` | 59 | Low |
| 🟡 **P1** | No duplicate detection | `lead_repo.py` | 21 | Medium |
| 🟡 **P1** | No owner validation | `lead_repo.py` | 21 | Low |
| 🟢 **P2** | Add database unique constraint | `models/crm.py` | 90 | Low |

---

## 🔧 IMPLEMENTATION CHECKLIST

- [ ] Add state lock validation to `update_status()`
- [ ] Add `update_lead()` method with converted check
- [ ] Add duplicate detection by email in `create()`
- [ ] Add owner_id validation in `create()`
- [ ] Add database unique constraint for email
- [ ] Update API to add PATCH `/leads/{id}` endpoint with state lock
- [ ] Write integration tests for:
  - [ ] Editing converted lead (should fail)
  - [ ] Creating duplicate lead (should fail)
  - [ ] Assigning to invalid owner (should fail)
- [ ] Update documentation with business rules

---

**End of Audit Report**
