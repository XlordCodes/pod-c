# Finance Module Security & Logic Audit Report

**Date:** 2026-02-14  
**Auditor:** Senior Financial Systems Architect  
**Scope:** Finance Module (Models, Schemas, Repository, Service, API)

---

## Executive Summary

The Finance Module demonstrates **good practices** in several areas (Decimal usage, tenant isolation in queries), but has **2 CRITICAL vulnerabilities** that must be addressed immediately:

1. **CRITICAL: Race Condition in Payment Processing** - Multiple concurrent payments can be processed for the same invoice
2. **CRITICAL: Floating Point Arithmetic in Service Layer** - Python's `sum()` uses float arithmetic

---

## 🔴 CRITICAL FINDINGS

### 1. RACE CONDITION: Concurrent Payment Processing (CRITICAL)

**Location:** [`app/services/finance_service.py:83-145`](app/services/finance_service.py:83)

**Issue:**  
The [`process_payment()`](app/services/finance_service.py:83) function does NOT use row-level locking when reading the invoice. This creates a race condition where:

1. User A starts payment processing (reads invoice, sees $100 owed)
2. User B starts payment processing (reads same invoice, sees $100 owed)
3. Both process $100 payments
4. Invoice is marked "paid" but $200 was actually collected (overpayment)

**Current Code (VULNERABLE):**
```python
# Line 90 in finance_service.py
invoice = self.repo.get_invoice(schema.invoice_id, tenant_id)
```

**Impact:**
- Financial loss due to overpayments
- Accounting discrepancies
- Audit trail corruption
- Potential fraud vector

**Fix Required:**

**Step 1:** Update [`finance_repo.py:66`](app/repos/finance_repo.py:66) to add a locking method:

```python
def get_invoice_for_update(self, invoice_id: int, tenant_id: int) -> Optional[Invoice]:
    """
    Fetches an invoice with a pessimistic lock (SELECT FOR UPDATE).
    Prevents concurrent modifications during payment processing.
    
    CRITICAL: This blocks other transactions from reading/writing this row
    until the current transaction commits or rolls back.
    """
    return (
        self.db.query(Invoice)
        .options(joinedload(Invoice.items), joinedload(Invoice.payments))
        .filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
        .with_for_update()  # <-- CRITICAL: Row-level lock
        .first()
    )
```

**Step 2:** Update [`finance_service.py:90`](app/services/finance_service.py:90):

```python
# OLD (VULNERABLE):
invoice = self.repo.get_invoice(schema.invoice_id, tenant_id)

# NEW (SECURE):
invoice = self.repo.get_invoice_for_update(schema.invoice_id, tenant_id)
```

**Testing:**
```python
# Simulate concurrent payments
import threading

def pay_invoice(invoice_id, amount):
    service.process_payment(tenant_id=1, schema=PaymentCreate(
        invoice_id=invoice_id,
        amount=amount,
        method="stripe"
    ))

# These should NOT both succeed if invoice total is $100
t1 = threading.Thread(target=pay_invoice, args=(1, 100))
t2 = threading.Thread(target=pay_invoice, args=(1, 100))
t1.start()
t2.start()
t1.join()
t2.join()

# Expected: One succeeds, one waits then fails (overpayment check)
# Actual (without fix): Both succeed, $200 collected
```

---

### 2. FLOATING POINT ARITHMETIC: Currency Calculation (CRITICAL)

**Location:** [`app/services/finance_service.py:37`](app/services/finance_service.py:37)

**Issue:**  
The `sum()` function in Python uses **floating-point arithmetic** by default, which can introduce rounding errors in financial calculations.

**Current Code (VULNERABLE):**
```python
# Line 37 in finance_service.py
total = sum(item.quantity * item.unit_price for item in schema.items)
```

**Example of the Problem:**
```python
# Pydantic ensures item.unit_price is Decimal
item1 = Decimal("10.10")
item2 = Decimal("20.20")

# But sum() converts to float internally:
result = sum([item1, item2])  # Returns float: 30.299999999999997

# Correct approach:
result = sum([item1, item2], Decimal("0"))  # Returns Decimal: 30.30
```

**Impact:**
- Rounding errors accumulate over multiple line items
- Invoice totals may be off by cents
- Regulatory compliance issues (financial accuracy requirements)
- Audit failures

**Fix Required:**

Update [`finance_service.py:37`](app/services/finance_service.py:37):

```python
# OLD (VULNERABLE):
total = sum(item.quantity * item.unit_price for item in schema.items)

# NEW (SECURE):
from decimal import Decimal

total = sum(
    (Decimal(item.quantity) * item.unit_price for item in schema.items),
    start=Decimal("0")  # <-- CRITICAL: Forces Decimal arithmetic
)
```

**Alternative (More Explicit):**
```python
total = Decimal("0")
for item in schema.items:
    total += Decimal(item.quantity) * item.unit_price
```

---

## 🟡 HIGH PRIORITY FINDINGS

### 3. MISSING VALIDATION: Overpayment Prevention (HIGH)

**Location:** [`app/services/finance_service.py:100-110`](app/services/finance_service.py:100)

**Issue:**  
The service calculates total paid but does NOT prevent overpayments. A user can pay $200 on a $100 invoice.

**Current Code:**
```python
# Lines 100-110
previous_paid = sum(p.amount for p in invoice.payments)
total_paid = previous_paid + schema.amount

# No check here to prevent overpayment!
if total_paid >= invoice.total_amount:
    new_status = "paid"
```

**Impact:**
- Accounting errors
- Refund processing overhead
- Customer confusion

**Fix Required:**

Add validation in [`finance_service.py:100`](app/services/finance_service.py:100):

```python
# After line 102 (total_paid calculation)
previous_paid = sum((Decimal(str(p.amount)) for p in invoice.payments), start=Decimal("0"))
total_paid = previous_paid + schema.amount

# NEW: Overpayment check
remaining_balance = invoice.total_amount - previous_paid
if schema.amount > remaining_balance:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Payment amount ${schema.amount} exceeds remaining balance ${remaining_balance}"
    )

# Existing status logic continues...
```

---

### 4. MISSING VALIDATION: Negative Quantity (HIGH)

**Location:** [`app/schemas/finance.py:19`](app/schemas/finance.py:19)

**Issue:**  
While `quantity` has `gt=0` validation, there's no validation for `unit_price` being negative in the context of invoice items (credit memos should be separate).

**Current Code:**
```python
# Line 19-20
quantity: int = Field(default=1, gt=0, description="Quantity, must be positive")
unit_price: Decimal = Field(..., gt=0, decimal_places=2, description="Price per unit")
```

**Status:** ✅ **GOOD** - Both fields already have `gt=0` validation

**Recommendation:**  
Add explicit validation for negative totals at the invoice level:

```python
# In InvoiceCreate schema (line 33)
@field_validator('items')
def validate_items_total(cls, v):
    """Ensure invoice total is positive."""
    total = sum((item.quantity * item.unit_price for item in v), Decimal("0"))
    if total <= 0:
        raise ValueError('Invoice total must be positive')
    return v
```

---

### 5. AUTHORIZATION: Tenant Isolation (HIGH)

**Location:** Multiple files

**Issue:**  
Need to verify tenant isolation is enforced everywhere.

**Audit Results:**

✅ **GOOD - Repository Layer:**
- [`finance_repo.py:74`](app/repos/finance_repo.py:74): `get_invoice()` filters by `tenant_id`
- [`finance_repo.py:84`](app/repos/finance_repo.py:84): `list_invoices()` filters by `tenant_id`

✅ **GOOD - API Layer:**
- [`finance.py:52-54`](app/api/finance.py:52): `create_invoice()` uses `current_user.tenant_id`
- [`finance.py:70`](app/api/finance.py:70): `list_invoices()` uses `current_user.tenant_id`
- [`finance.py:84`](app/api/finance.py:84): `get_invoice()` uses `current_user.tenant_id`
- [`finance.py:104`](app/api/finance.py:104): `record_payment()` uses `current_user.tenant_id`

⚠️ **POTENTIAL ISSUE - Missing Validation:**

In [`finance_repo.py:107-115`](app/repos/finance_repo.py:107), the `update_status()` method does NOT filter by `tenant_id`:

```python
# Line 111 (VULNERABLE)
invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
```

**Impact:**  
If called directly (bypassing service layer), could update invoices from other tenants.

**Fix Required:**

Update [`finance_repo.py:107`](app/repos/finance_repo.py:107):

```python
def update_status(self, invoice_id: int, tenant_id: int, new_status: str) -> Optional[Invoice]:
    """
    Updates the status of an invoice (e.g., 'draft' -> 'paid').
    Enforces tenant isolation.
    """
    invoice = (
        self.db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)  # <-- ADD tenant_id
        .first()
    )
    if invoice:
        invoice.status = new_status
        self.db.flush()
    return invoice
```

Then update the call in [`finance_service.py:113`](app/services/finance_service.py:113):

```python
# OLD:
self.repo.update_status(invoice.id, new_status)

# NEW:
self.repo.update_status(invoice.id, tenant_id, new_status)
```

---

## 🟢 GOOD PRACTICES OBSERVED

### ✅ Decimal Usage in Models
[`app/models/finance.py:20`](app/models/finance.py:20): Uses `Numeric(10, 2)` for all currency fields
```python
total_amount = Column(Numeric(10, 2), nullable=False)
```

### ✅ Decimal Usage in Schemas
[`app/schemas/finance.py:12`](app/schemas/finance.py:12): Imports and uses `Decimal` type
```python
from decimal import Decimal
unit_price: Decimal = Field(..., gt=0, decimal_places=2)
```

### ✅ Positive Value Validation
[`app/schemas/finance.py:23`](app/schemas/finance.py:23): Prevents zero/negative payments
```python
amount: Decimal = Field(..., gt=0, decimal_places=2)
```

### ✅ Atomic Transactions
[`app/services/finance_service.py:54-56`](app/services/finance_service.py:54): Uses commit/rollback properly
```python
self.db.commit()
# ... with proper rollback in except blocks
```

### ✅ Tenant Filtering in Queries
[`app/repos/finance_repo.py:74`](app/repos/finance_repo.py:74): All read operations filter by tenant_id

---

## 📋 PRIORITY ACTION ITEMS

| Priority | Issue | File | Line | Fix Complexity |
|----------|-------|------|------|----------------|
| 🔴 **P0** | Race condition in payment processing | `finance_service.py` | 90 | Medium |
| 🔴 **P0** | Floating point arithmetic in sum() | `finance_service.py` | 37 | Low |
| 🟡 **P1** | Missing overpayment validation | `finance_service.py` | 100 | Low |
| 🟡 **P1** | Missing tenant_id in update_status | `finance_repo.py` | 111 | Low |
| 🟢 **P2** | Add invoice-level total validation | `schemas/finance.py` | 33 | Low |

---

## 🔧 IMPLEMENTATION CHECKLIST

- [ ] Add `get_invoice_for_update()` method to `FinanceRepo`
- [ ] Update `process_payment()` to use row-level locking
- [ ] Fix `sum()` to use `Decimal("0")` as start value
- [ ] Add overpayment validation in `process_payment()`
- [ ] Add `tenant_id` parameter to `update_status()`
- [ ] Add invoice total validation in `InvoiceCreate` schema
- [ ] Write integration tests for concurrent payment scenarios
- [ ] Update documentation with security considerations

---

## 📚 REFERENCES

- [Python Decimal Documentation](https://docs.python.org/3/library/decimal.html)
- [SQLAlchemy SELECT FOR UPDATE](https://docs.sqlalchemy.org/en/14/orm/query.html#sqlalchemy.orm.Query.with_for_update)
- [OWASP: Race Conditions](https://owasp.org/www-community/vulnerabilities/Race_Conditions)
- [PCI DSS: Financial Data Security](https://www.pcisecuritystandards.org/)

---

**End of Audit Report**
