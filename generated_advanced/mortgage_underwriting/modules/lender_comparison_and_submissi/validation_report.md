```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/lender/models.py, line 72
  Issue: Field `term_years` uses `Numeric(3, 1)` which may cause precision loss for financial values exceeding 99 years
  Fix: Change to `Numeric(5, 2)` or higher to support full range of possible terms

- File: mortgage_underwriting/modules/lender/models.py, line 74
  Issue: Field `rate` uses `Numeric(5, 3)` which truncates rates above 99.999%
  Fix: Change to `Numeric(6, 3)` to allow rates up to 999.999%

- File: mortgage_underwriting/modules/lender/services.py, line 44
  Issue: GDS/TDS calculation does not apply OSFI B-20 stress test
  Fix: Must calculate using qualifying_rate = max(contract_rate + 2%, 5.25%) as per regulatory requirement

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/lender/services.py, line 109
  Issue: Logs contain calculated financial ratios that could expose sensitive data
  Fix: Remove detailed ratio logging or anonymize values in logs

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/lender/services.py, line 40
  Issue: No docstring for `match_lenders` method explaining business logic
  Fix: Add comprehensive docstring detailing matching algorithm and compliance requirements
```