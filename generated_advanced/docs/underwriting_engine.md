# Underwriting Engine
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: OnLendHub - Canadian Mortgage Underwriting

# OnLendHub Underwriting Engine Architecture Design

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        API Gateway (Kong/Nginx)                     │
│                    OAuth 2.0 + mTLS Termination                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                    FastAPI Underwriting Service                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐ │
│  │ Calculation │  │   Workflow   │  │   Override   │  │  Audit  │ │
│  │   Engine    │  │   Manager    │  │   Manager    │  │ Logger  │ │
│  └─────────────┘  └──────────────┘  └──────────────┘  └─────────┘ │
│        │                 │                  │             │        │
│  ┌─────▼─────────────────▼──────────────────▼─────────────▼────┐   │
│  │              Underwriting Domain Service                   │   │
│  │  - GDS/TDS Calculator   - LTV Analyzer   - CMHC Engine     │   │
│  └─────┬───────────────────┬───────────────────┬───────────────┘   │
│        │                   │                   │                    │
│  ┌─────▼──────┐      ┌────▼──────┐      ┌─────▼──────┐            │
│  │   Rules    │      │  External │      │   Cache    │            │
│  │   Engine   │      │ Services  │      │ (Redis)    │            │
│  └─────┬──────┘      └────┬──────┘      └─────┬──────┘            │
└────────┼──────────────────┼───────────────────┼─────────────────────┘
         │                  │                   │
┌────────▼──────────────────▼───────────────────▼─────────────────────┐
│   PostgreSQL 15.2          Credit Bureau API    Property Valuation  │
│  ┌──────────────┐         ┌──────────────┐      ┌──────────────┐   │
│  │   Main DB    │         │  (Equifax)   │      │  (GeoWarehouse)│  │
│  │              │         └──────────────┘      └──────────────┘   │
│  │ - Applications                                                              │
│  │ - Borrowers                                                                 │
│  │ - UW Results                                                                │
│  │ - Audit Logs                                                                │
│  └──────────────┘                                                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Domain Models (SQLAlchemy 2.0+)

### 2.1 Database Schema Design

```python
# models/base.py
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass

class Base(DeclarativeBase, MappedAsDataclass):
    """Base class for all ORM models"""
    pass

# models/enums.py
import enum
from sqlalchemy import Enum as SQLEnum

class ApplicationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    EVALUATING = "EVALUATING"
    APPROVED = "APPROVED"
    CONDITIONAL = "CONDITIONAL"
    DECLINED = "DECLINED"
    OVERRIDDEN = "OVERRIDDEN"

class DecisionType(str, enum.Enum):
    APPROVED = "APPROVED"
    CONDITIONAL = "CONDITIONAL"
    DECLINED = "DECLINED"

class IncomeType(str, enum.Enum):
    SALARIED = "SALARIED"
    HOURLY = "HOURLY"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    RENTAL = "RENTAL"
    INVESTMENT = "INVESTMENT"

class DeclineReason(str, enum.Enum):
    GDS_EXCEEDED = "GDS_EXCEEDED"
    TDS_EXCEEDED = "TDS_EXCEEDED"
    LTV_EXCEEDED = "LTV_EXCEEDED"
    INSUFFICIENT_DOWN_PAYMENT = "INSUFFICIENT_DOWN_PAYMENT"
    STRESS_TEST_FAILED = "STRESS_TEST_FAILED"
    CREDIT_SCORE_TOO_LOW = "CREDIT_SCORE_TOO_LOW"
    INCUFFICIENT_INCOME_DOCUMENTATION = "INSUFFICIENT_INCOME_DOCUMENTATION"

# models/application.py
from decimal import Decimal
from sqlalchemy import UUID, Numeric, String, DateTime, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import uuid

from .base import Base
from .enums import ApplicationStatus

class Application(Base):
    __tablename__ = "applications"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    status: Mapped[ApplicationStatus] = mapped_column(SQLEnum(ApplicationStatus), nullable=False)
    
    # Property Details
    property_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    property_type: Mapped[str] = mapped_column(String(50), nullable=False)  # CONDO, HOUSE, etc.
    condo_fee_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal('0.00'))
    
    # Mortgage Details
    requested_mortgage_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    contract_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    amortization_years: Mapped[int] = mapped_column(nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    borrowers: Mapped[list["Borrower"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    underwriting_result: Mapped["UnderwritingResult"] = relationship(back_populates="application", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_application_status', 'status'),
        Index('idx_application_created', 'created_at'),
    )

# models/borrower.py
class Borrower(Base):
    __tablename__ = "borrowers"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), nullable=False)
    
    is_primary: Mapped[bool] = mapped_column(default=False)
    gross_monthly_income: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    credit_score: Mapped[int] = mapped_column(nullable=True)
    
    # Income Details (denormalized for calculation performance)
    income_sources: Mapped[list["IncomeSource"]] = relationship(back_populates="borrower", cascade="all, delete-orphan")
    debts: Mapped[list["Debt"]] = relationship(back_populates="borrower", cascade="all, delete-orphan")
    
    application: Mapped["Application"] = relationship(back_populates="borrowers")

# models/income.py
class IncomeSource(Base):
    __tablename__ = "income_sources"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    borrower_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("borrowers.id"), nullable=False)
    
    income_type: Mapped[IncomeType] = mapped_column(SQLEnum(IncomeType), nullable=False)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    
    # Self-employed specific
    two_year_average: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    most_recent_year: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Rental property specific
    gross_rental_income: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    property_tax_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    insurance_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    
    borrower: Mapped["Borrower"] = relationship(back_populates="income_sources")

# models/debt.py
class Debt(Base):
    __tablename__ = "debts"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    borrower_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("borrowers.id"), nullable=False)
    
    debt_type: Mapped[str] = mapped_column(String(100), nullable=False)  # CREDIT_CARD, CAR_LOAN, etc.
    monthly_payment: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    outstanding_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=True)
    
    # For multi-property mortgages
    is_rental_property: Mapped[bool] = mapped_column(default=False)
    associated_property_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=True)
    
    borrower: Mapped["Borrower"] = relationship(back_populates="debts")

# models/underwriting_result.py
class UnderwritingResult(Base):
    __tablename__ = "underwriting_results"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), nullable=False, unique=True)
    
    decision: Mapped[DecisionType] = mapped_column(SQLEnum(DecisionType), nullable=False)
    qualifies: Mapped[bool] = mapped_column(nullable=False)
    
    # Ratios
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    
    # Stress Test
    stress_test_passed: Mapped[bool] = mapped_column(nullable=False)
    qualifying_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    max_mortgage_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    # CMHC
    cmhc_required: Mapped[bool] = mapped_column(nullable=False)
    cmhc_premium_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=True)
    cmhc_premium_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=True)
    
    # Decision Details
    decline_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=True)
    conditions: Mapped[list[str]] = mapped_column(JSON, nullable=True)
    
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    evaluated_by: Mapped[str] = mapped_column(String(255), nullable=False)  # User ID from JWT
    
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")  # UW model version
    
    application: Mapped["Application"] = relationship(back_populates="underwriting_result")
```

---

## 3. Core Calculation Engine

### 3.1 OSFI B-20 Stress Test Implementation

```python
# services/stress_test_calculator.py
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field

class StressTestParams(BaseModel):
    contract_rate: Decimal = Field(..., ge=Decimal('0'), le=Decimal('1'))
    posted_rate: Decimal = Field(..., ge=Decimal('0'), le=Decimal('1'))
    osfi_floor_rate: Decimal = Field(default=Decimal('0.0525'), ge=Decimal('0'), le=Decimal('1'))

class StressTestResult(BaseModel):
    qualifying_rate: Decimal
    stress_test_passed: bool
    max_affordable_payment: Decimal

class StressTestCalculator:
    """OSFI B-20 Guideline Implementation"""
    
    @staticmethod
    def calculate_qualifying_rate(contract_rate: Decimal, 
                                  posted_rate: Decimal,
                                  osfi_floor_rate: Decimal = Decimal('0.0525')) -> Decimal:
        """
        qualifying_rate = max(contract_rate + 2%, 5.25%)
        Per OSFI B-20 guidelines effective June 2021
        """
        stress_test_rate = contract_rate + Decimal('0.02')
        qualifying_rate = max(stress_test_rate, osfi_floor_rate)
        return qualifying_rate.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def calculate_max_mortgage(
        gross_monthly_income: Decimal,
        gds_limit: Decimal,
        qualifying_rate: Decimal,
        amortization_years: int,
        condo_fee: Decimal = Decimal('0'),
        property_tax_monthly: Decimal = Decimal('0'),
        heating_cost_monthly: Decimal = Decimal('150')  # OSFI standard
    ) -> Decimal:
        """
        Calculate maximum mortgage amount based on GDS constraint
        Uses Canadian mortgage formula: P = L[c(1+c)^n]/[(1+c)^n-1]
        """
        # Total housing costs allowed
        max_housing_cost = gross_monthly_income * gds_limit
        
        # Subtract fixed costs
        available_for_mortgage = max_housing_cost - condo_fee - property_tax_monthly - heating_cost_monthly
        
        if available_for_mortgage <= 0:
            return Decimal('0')
        
        # Monthly rate
        n = amortization_years * 12
        c = qualifying_rate / 12
        
        # Handle edge case of zero rate
        if c == 0:
            return available_for_mortgage * Decimal(n)
        
        # Maximum loan calculation
        numerator = c * (1 + c) ** n
        denominator = (1 + c) ** n - 1
        
        max_loan = available_for_mortgage * (denominator / numerator)
        
        return max_loan.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

### 3.2 GDS/TDS Calculator with Multi-Property Aggregation

```python
# services/dsr_calculator.py
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Tuple
from pydantic import BaseModel

class DebtServiceRatios(BaseModel):
    gds_ratio: Decimal
    tds_ratio: Decimal
    total_monthly_housing: Decimal
    total_monthly_debts: Decimal

class DSRCalculator:
    """
    GDS/TDS Calculator with multi-property debt aggregation
    Implements CMHC and OSFI guidelines
    """
    
    # OSFI Guidelines
    GDS_LIMIT: Decimal = Decimal('0.39')
    TDS_LIMIT: Decimal = Decimal('0.44')
    
    # Heating cost standard (OSFI guideline)
    HEATING_COST_MONTHLY: Decimal = Decimal('150.00')
    
    @classmethod
    def calculate_ratios(
        cls,
        gross_monthly_income: Decimal,
        mortgage_payment: Decimal,
        property_tax_monthly: Decimal,
        condo_fee_monthly: Decimal,
        other_debts: List[Decimal],
        is_condo: bool = False
    ) -> DebtServiceRatios:
        """
        GDS = (PITH + 50% condo fee) / Gross Monthly Income
        TDS = (PITH + all debts + 50% condo fee) / Gross Monthly Income
        """
        # Condo fee treatment: 50% included in housing costs
        condo_fee_for_gds = condo_fee_monthly * Decimal('0.5') if is_condo else Decimal('0')
        
        # Total monthly housing costs (PITH + 50% condo fee)
        total_monthly_housing = (
            mortgage_payment + 
            property_tax_monthly + 
            cls.HEATING_COST_MONTHLY +
            condo_fee_for_gds
        )
        
        # Total monthly debt obligations
        total_other_debts = sum(other_debts) if other_debts else Decimal('0')
        total_monthly_debts = total_monthly_housing + total_other_debts
        
        # Calculate ratios
        gds_ratio = (total_monthly_housing / gross_monthly_income).quantize(
            Decimal('0.0001'), rounding=ROUND_HALF_UP
        )
        tds_ratio = (total_monthly_debts / gross_monthly_income).quantize(
            Decimal('0.0001'), rounding=ROUND_HALF_UP
        )
        
        return DebtServiceRatios(
            gds_ratio=gds_ratio,
            tds_ratio=tds_ratio,
            total_monthly_housing=total_monthly_housing,
            total_monthly_debts=total_monthly_debts
        )
    
    @classmethod
    def aggregate_property_debts(cls, debts: List['Debt']) -> Tuple[Decimal, Decimal]:
        """
        Multi-property debt aggregation strategy:
        - Rental property debts are offset by rental income
        - Primary residence debts fully counted
        """
        total_debt_payments = Decimal('0')
        total_rental_income = Decimal('0')
        
        for debt in debts:
            if debt.is_rental_property:
                # Rental property debt - subject to rental offset rules
                # 50% of rental income can offset the debt payment
                rental_offset = debt.associated_rental_income * Decimal('0.5') if hasattr(debt, 'associated_rental_income') else Decimal('0')
                net_rental_debt = max(Decimal('0'), debt.monthly_payment - rental_offset)
                total_debt_payments += net_rental_debt
                total_rental_income += debt.associated_rental_income or Decimal('0')
            else:
                # Primary residence or consumer debt - fully counted
                total_debt_payments += debt.monthly_payment
        
        return total_debt_payments, total_rental_income
```

### 3.3 LTV & CMHC Insurance Engine

```python
# services/cmhc_calculator.py
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple
from pydantic import BaseModel

class LTVResult(BaseModel):
    ltv_ratio: Decimal
    min_down_payment: Decimal
    cmhc_required: bool
    cmhc_premium_rate: Optional[Decimal]
    cmhc_premium_amount: Optional[Decimal]

class CMHCCalculator:
    """
    CMHC Insurance Premium Calculator
    Implements Canadian mortgage insurance rules
    """
    
    # CMHC Premium Rates (as of 2024)
    PREMIUM_RATES = {
        (Decimal('0.8001'), Decimal('0.85')): Decimal('0.0280'),  # 80.01-85% LTV
        (Decimal('0.8501'), Decimal('0.90')): Decimal('0.0310'),  # 85.01-90% LTV
        (Decimal('0.9001'), Decimal('0.95')): Decimal('0.0400'),  # 90.01-95% LTV
    }
    
    # Minimum down payment rules
    @staticmethod
    def calculate_min_down_payment(property_value: Decimal) -> Decimal:
        """
        - 5% on first $500k
        - 10% on portion between $500k-$1.5M
        - 20% on portion above $1.5M
        """
        if property_value <= Decimal('500000'):
            return property_value * Decimal('0.05')
        elif property_value <= Decimal('1500000'):
            first_portion = Decimal('500000') * Decimal('0.05')
            second_portion = (property_value - Decimal('500000')) * Decimal('0.10')
            return first_portion + second_portion
        else:
            return property_value * Decimal('0.20')
    
    @classmethod
    def calculate_ltv_and_insurance(
        cls,
        property_value: Decimal,
        mortgage_amount: Decimal,
        down_payment: Decimal
    ) -> LTVResult:
        """
        Calculate LTV ratio and determine CMHC requirements
        """
        # Validate down payment meets minimums
        min_down = cls.calculate_min_down_payment(property_value)
        if down_payment < min_down:
            raise ValueError(f"Down payment ${down_payment} is less than minimum ${min_down}")
        
        # Calculate LTV
        ltv_ratio = (mortgage_amount / property_value).quantize(
            Decimal('0.0001'), rounding=ROUND_HALF_UP
        )
        
        # CMHC required if LTV > 80%
        cmhc_required = ltv_ratio > Decimal('0.80')
        
        if not cmhc_required:
            return LTVResult(
                ltv_ratio=ltv_ratio,
                min_down_payment=min_down,
                cmhc_required=False,
                cmhc_premium_rate=None,
                cmhc_premium_amount=None
            )
        
        # Find premium rate
        premium_rate = None
        for (ltv_min, ltv_max), rate in cls.PREMIUM_RATES.items():
            if ltv_min <= ltv_ratio <= ltv_max:
                premium_rate = rate
                break
        
        if premium_rate is None:
            raise ValueError(f"LTV ratio {ltv_ratio} is not insurable")
        
        # Calculate premium amount (added to mortgage)
        premium_amount = (mortgage_amount * premium_rate).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        return LTVResult(
            ltv_ratio=ltv_ratio,
            min_down_payment=min_down,
            cmhc_required=True,
            cmhc_premium_rate=premium_rate,
            cmhc_premium_amount=premium_amount
        )
```

---

## 4. Underwriting Orchestration Service

```python
# services/underwriting_orchestrator.py
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid

from .stress_test_calculator import StressTestCalculator, StressTestResult
from .dsr_calculator import DSRCalculator, DebtServiceRatios
from .cmhc_calculator import CMHCCalculator, LTVResult
from .self_employed_calculator import SelfEmployedIncomeCalculator
from .rental_income_calculator import RentalIncomeCalculator

class UnderwritingInput(BaseModel):
    application_id: uuid.UUID
    property_value: Decimal
    property_type: str
    condo_fee_monthly: Decimal
    mortgage_amount: Decimal
    contract_rate: Decimal
    amortization_years: int
    down_payment: Decimal
    borrowers: List['BorrowerInput']
    validate_income_docs: bool = True

class BorrowerInput(BaseModel):
    gross_monthly_income: Decimal
    credit_score: Optional[int]
    income_sources: List['IncomeSourceInput']
    debts: List['DebtInput']

class UnderwritingDecision(BaseModel):
    qualifies: bool
    decision: str  # APPROVED, CONDITIONAL, DECLINED
    gds_ratio: Decimal
    tds_ratio: Decimal
    ltv_ratio: Decimal
    cmhc_required: bool
    cmhc_premium_amount: Optional[Decimal]
    qualifying_rate: Decimal
    max_mortgage: Decimal
    decline_reasons: List[str]
    conditions: List[str]
    stress_test_passed: bool

class UnderwritingOrchestrator:
    """
    Main underwriting decision engine
    Implements business rules and coordinates all calculators
    """
    
    # Conditional approval thresholds
    CONDITIONAL_GDS_THRESHOLD = Decimal('0.42')  # Up to 42% GDS for conditional
    CONDITIONAL_TDS_THRESHOLD = Decimal('0.47')  # Up to 47% TDS for conditional
    MIN_CREDIT_SCORE = 680  # For standard approval
    
    def __init__(self):
        self.stress_test_calc = StressTestCalculator()
        self.dsr_calc = DSRCalculator()
        self.cmhc_calc = CMHCCalculator()
        self.self_employed_calc = SelfEmployedIncomeCalculator()
        self.rental_calc = RentalIncomeCalculator()
    
    async def evaluate(self, input_data: UnderwritingInput, evaluator_id: str) -> UnderwritingDecision:
        """
        Complete underwriting evaluation with decision logic
        """
        decline_reasons = []
        conditions = []
        
        # Step 1: Calculate validated income (handle self-employed)
        total_gross_income = await self._calculate_validated_income(
            input_data.borrowers, 
            input_data.validate_income_docs
        )
        
        # Step 2: LTV and CMHC calculation
        ltv_result = self.cmhc_calc.calculate_ltv_and_insurance(
            input_data.property_value,
            input_data.mortgage_amount,
            input_data.down_payment
        )
        
        # Step 3: Stress Test
        qualifying_rate = StressTestCalculator.calculate_qualifying_rate(
            input_data.contract_rate,
            Decimal('0.0525')  # Use posted rate or floor
        )
        
        # Calculate max mortgage under stress test
        max_mortgage = StressTestCalculator.calculate_max_mortgage(
            total_gross_income,
            self.dsr_calc.GDS_LIMIT,
            qualifying_rate,
            input_data.amortization_years,
            input_data.condo_fee_monthly,
            self._estimate_property_tax(input_data.property_value),
            self.dsr_calc.HEATING_COST_MONTHLY
        )
        
        stress_test_passed = input_data.mortgage_amount <= max_mortgage
        
        # Step 4: GDS/TDS Calculation
        # Use actual contract rate for payment calculation
        actual_payment = self._calculate_mortgage_payment(
            input_data.mortgage_amount,
            input_data.contract_rate,
            input_data.amortization_years
        )
        
        # Aggregate debts across all borrowers and properties
        all_debts = []
        for borrower in input_data.borrowers:
            debts, _ = self.dsr_calc.aggregate_property_debts(borrower.debts)
            all_debts.append(debts)
        
        total_other_debts = sum(all_debts)
        
        dsr_result = self.dsr_calc.calculate_ratios(
            total_gross_income,
            actual_payment,
            self._estimate_property_tax(input_data.property_value),
            input_data.condo_fee_monthly,
            [total_other_debts],
            is_condo=input_data.property_type.upper() == 'CONDO'
        )
        
        # Step 5: Credit Score Evaluation
        min_credit_score = min([b.credit_score or 0 for b in input_data.borrowers])
        
        # Step 6: Decision Matrix
        qualifies, decision = self._make_decision(
            dsr_result,
            stress_test_passed,
            ltv_result,
            min_credit_score,
            decline_reasons,
            conditions
        )
        
        return UnderwritingDecision(
            qualifies=qualifies,
            decision=decision,
            gds_ratio=dsr_result.gds_ratio,
            tds_ratio=dsr_result.tds_ratio,
            ltv_ratio=ltv_result.ltv_ratio,
            cmhc_required=ltv_result.cmhc_required,
            cmhc_premium_amount=ltv_result.cmhc_premium_amount,
            qualifying_rate=qualifying_rate,
            max_mortgage=max_mortgage,
            decline_reasons=decline_reasons,
            conditions=conditions,
            stress_test_passed=stress_test_passed
        )
    
    async def _calculate_validated_income(self, borrowers: List[BorrowerInput], validate_docs: bool) -> Decimal:
        """
        Calculate validated income with special handling for:
        - Self-employed (2-year average with add-backs)
        - Rental income (offset rules)
        """
        total_income = Decimal('0')
        
        for borrower in borrowers:
            borrower_income = Decimal('0')
            
            for income_source in borrower.income_sources:
                if income_source.income_type == IncomeType.SELF_EMPLOYED:
                    validated = self.self_employed_calc.calculate_qualifying_income(
                        income_source.two_year_average,
                        income_source.most_recent_year,
                        validate_docs
                    )
                    borrower_income += validated
                elif income_source.income_type == IncomeType.RENTAL:
                    # Rental income treatment: 50% gross offset or 80% with strong borrower
                    net_rental = self.rental_calc.calculate_net_rental_income(
                        income_source.gross_rental_income,
                        income_source.property_tax_monthly,
                        income_source.insurance_monthly,
                        borrower.credit_score or 0
                    )
                    borrower_income += net_rental
                else:
                    # Salaried/hourly - use gross monthly
                    borrower_income += income_source.monthly_amount
            
            total_income += borrower_income
        
        return total_income
    
    def _make_decision(
        self,
        dsr: DebtServiceRatios,
        stress_test_passed: bool,
        ltv: LTVResult,
        min_credit_score: int,
        decline_reasons: List[str],
        conditions: List[str]
    ) -> Tuple[bool, str]:
        """
        Decision matrix with conditional logic
        """
        # Hard declines first
        if not stress_test_passed:
            decline_reasons.append(DeclineReason.STRESS_TEST_FAILED)
        
        if dsr.gds_ratio > self.CONDITIONAL_GDS_THRESHOLD:
            decline_reasons.append(DeclineReason.GDS_EXCEEDED)
        
        if dsr.tds_ratio > self.CONDITIONAL_TDS_THRESHOLD:
            decline_reasons.append(DeclineReason.TDS_EXCEEDED)
        
        if min_credit_score < 600:  # Hard floor
            decline_reasons.append(DeclineReason.CREDIT_SCORE_TOO_LOW)
        
        # If any hard declines, return DECLINED
        if decline_reasons:
            return False, DecisionType.DECLINED
        
        # Conditional approval criteria
        is_conditional = False
        
        if dsr.gds_ratio > self.dsr_calc.GDS_LIMIT:
            conditions.append(f"GDS ratio {dsr.gds_ratio:.2%} exceeds standard limit. Requires management approval.")
            is_conditional = True
        
        if dsr.tds_ratio > self.dsr_calc.TDS_LIMIT:
            conditions.append(f"TDS ratio {dsr.tds_ratio:.2%} exceeds standard limit. Requires co-signer or debt restructuring.")
            is_conditional = True
        
        if min_credit_score < self.MIN_CREDIT_SCORE:
            conditions.append(f"Credit score {min_credit_score} below standard {self.MIN_CREDIT_SCORE}. May require higher down payment.")
            is_conditional = True
        
        if ltv.ltv_ratio > Decimal('0.90'):
            conditions.append("High LTV ratio requires additional documentation and may need co-signer.")
            is_conditional = True
        
        # Final decision
        if is_conditional:
            return True, DecisionType.CONDITIONAL
        
        return True, DecisionType.APPROVED
    
    def _calculate_mortgage_payment(self, principal: Decimal, annual_rate: Decimal, years: int) -> Decimal:
        """Standard Canadian mortgage payment calculation"""
        n = years * 12
        monthly_rate = annual_rate / 12
        
        if monthly_rate == 0:
            return principal / Decimal(n)
        
        numerator = monthly_rate * (1 + monthly_rate) ** n
        denominator = (1 + monthly_rate) ** n - 1
        
        payment = principal * (numerator / denominator)
        return payment.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def _estimate_property_tax(self, property_value: Decimal) -> Decimal:
        """Estimate property tax as 1% of property value annually"""
        annual_tax = property_value * Decimal('0.01')
        return (annual_tax / Decimal('12')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

---

## 5. API Endpoints (FastAPI 0.109.0)

### 5.1 Main API Router

```python
# api/v1/underwriting.py
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from decimal import Decimal
import uuid

from models import Application, UnderwritingResult
from services.underwriting_orchestrator import UnderwritingOrchestrator, UnderwritingInput
from database import get_db_session
from security import get_current_user, require_admin_role
from audit import AuditLogger

router = APIRouter(prefix="/underwriting", tags=["underwriting"])

@router.post(
    "/calculate",
    response_model=UnderwritingDecision,
    status_code=status.HTTP_200_OK
)
async def calculate_qualification(
    input_data: UnderwritingInput,
    x_correlation_id: str = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user)
):
    """
    **Stateless calculation endpoint** - Run qualification without saving
    
    - Performs full underwriting calculation
    - Does NOT persist results to database
    - Used for pre-qualification scenarios
    - Audit logged for compliance
    """
    orchestrator = UnderwritingOrchestrator()
    
    try:
        # Perform calculation
        decision = await orchestrator.evaluate(
            input_data, 
            evaluator_id=current_user["sub"]
        )
        
        # Audit log (required even for stateless operations)
        await AuditLogger.log_calculation(
            db=db,
            user_id=current_user["sub"],
            correlation_id=x_correlation_id,
            input_data=input_data.dict(),
            decision=decision.dict(),
            ip_address=current_user.get("ip_address")
        )
        
        return decision
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Calculation error: {str(e)}"
        )

@router.post(
    "/applications/{application_id}/evaluate",
    response_model=UnderwritingDecision,
    status_code=status.HTTP_201_CREATED
)
async def evaluate_and_save(
    application_id: uuid.UUID,
    x_correlation_id: str = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user)
):
    """
    **Stateful evaluation endpoint** - Evaluate and persist results
    
    - Fetches application data
    - Runs full underwriting evaluation
    - Persists result to database
    - Updates application status
    - Triggers workflow events
    """
    # Fetch application with relationships
    stmt = (
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.borrowers)
            .selectinload(Borrower.income_sources),
            selectinload(Application.borrowers)
            .selectinload(Borrower.debts)
        )
    )
    
    result = await db.execute(stmt)
    application = result.scalar_one_or_none()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found"
        )
    
    # Convert to underwriting input
    input_data = await _build_underwriting_input(application)
    
    orchestrator = UnderwritingOrchestrator()
    
    try:
        # Perform evaluation
        decision = await orchestrator.evaluate(
            input_data,
            evaluator_id=current_user["sub"]
        )
        
        # Persist result
        uw_result = UnderwritingResult(
            application_id=application_id,
            decision=decision.decision,
            qualifies=decision.qualifies,
            gds_ratio=decision.gds_ratio,
            tds_ratio=decision.tds_ratio,
            ltv_ratio=decision.ltv_ratio,
            cmhc_required=decision.cmhc_required,
            cmhc_premium_amount=decision.cmhc_premium_amount,
            qualifying_rate=decision.qualifying_rate,
            max_mortgage=decision.max_mortgage,
            decline_reasons=decision.decline_reasons,
            conditions=decision.conditions,
            stress_test_passed=decision.stress_test_passed,
            evaluated_by=current_user["sub"],
            version="1.0.0"
        )
        
        db.add(uw_result)
        
        # Update application status
        application.status = {
            "APPROVED": ApplicationStatus.APPROVED,
            "CONDITIONAL": ApplicationStatus.CONDITIONAL,
            "DECLINED": ApplicationStatus.DECLINED
        }[decision.decision]
        
        await db.commit()
        await db.refresh(uw_result)
        
        # Audit log
        await AuditLogger.log_evaluation(
            db=db,
            application_id=application_id,
            user_id=current_user["sub"],
            correlation_id=x_correlation_id,
            decision=decision.dict(),
            status=application.status
        )
        
        return decision
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Evaluation error: {str(e)}"
        )

@router.get(
    "/applications/{application_id}/result",
    response_model=UnderwritingDecision,
    status_code=status.HTTP_200_OK
)
async def get_underwriting_result(
    application_id: uuid.UUID,
    version: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user)
):
    """
    **Retrieve saved underwriting result**
    
    - Returns persisted underwriting decision
    - Optional version parameter for historical results
    - Used for application review and reporting
    """
    stmt = select(UnderwritingResult).where(
        UnderwritingResult.application_id == application_id
    )
    
    if version:
        stmt = stmt.where(UnderwritingResult.version == version)
    else:
        stmt = stmt.order_by(UnderwritingResult.evaluated_at.desc())
    
    result = await db.execute(stmt)
    uw_result = result.scalar_one_or_none()
    
    if not uw_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No underwriting result found for this application"
        )
    
    # Audit log access
    await AuditLogger.log_access(
        db=db,
        application_id=application_id,
        user_id=current_user["sub"],
        resource="underwriting_result"
    )
    
    return UnderwritingDecision(
        qualifies=uw_result.qualifies,
        decision=uw_result.decision,
        gds_ratio=uw_result.gds_ratio,
        tds_ratio=uw_result.tds_ratio,
        ltv_ratio=uw_result.ltv_ratio,
        cmhc_required=uw_result.cmhc_required,
        cmhc_premium_amount=uw_result.cmhc_premium_amount,
        qualifying_rate=uw_result.qualifying_rate,
        max_mortgage=uw_result.max_mortgage,
        decline_reasons=uw_result.decline_reasons or [],
        conditions=uw_result.conditions or [],
        stress_test_passed=uw_result.stress_test_passed
    )

@router.post(
    "/applications/{application_id}/override",
    response_model=UnderwritingDecision,
    status_code=status.HTTP_200_OK
)
async def admin_override(
    application_id: uuid.UUID,
    override_data: OverrideRequest,
    x_correlation_id: str = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(require_admin_role)
):
    """
    **Admin override endpoint** - Override underwriting decision
    
    - Requires ADMIN role
    - Must provide justification
    - Creates immutable audit trail
    - Updates application to OVERRIDDEN status
    """
    # Verify previous result exists
    stmt = select(UnderwritingResult).where(
        UnderwritingResult.application_id == application_id
    )
    result = await db.execute(stmt)
    uw_result = result.scalar_one_or_none()
    
    if not uw_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No underwriting result to override"
        )
    
    # Apply override
    uw_result.decision = override_data.new_decision
    uw_result.qualifies = override_data.new_decision in ["APPROVED", "CONDITIONAL"]
    uw_result.conditions.append(f"OVERRIDE: {override_data.justification}")
    uw_result.evaluated_by = f"{current_user['sub']} (OVERRIDE)"
    
    # Update application status
    application = await db.get(Application, application_id)
    application.status = ApplicationStatus.OVERRIDDEN
    
    # Create override audit record
    override_record = Override(
        application_id=application_id,
        previous_decision=uw_result.decision,
        new_decision=override_data.new_decision,
        justification=override_data.justification,
        overridden_by=current_user["sub"],
        risk_approval_id=override_data.risk_approval_id
    )
    
    db.add(override_record)
    
    try:
        await db.commit()
        
        # Audit log override (critical for compliance)
        await AuditLogger.log_override(
            db=db,
            application_id=application_id,
            user_id=current_user["sub"],
            correlation_id=x_correlation_id,
            override_data=override_data.dict(),
            previous_decision=uw_result.decision
        )
        
        return await get_underwriting_result(application_id, db=db, current_user=current_user)
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Override failed: {str(e)}"
        )

class OverrideRequest(BaseModel):
    new_decision: str = Field(..., regex="^(APPROVED|CONDITIONAL)$")
    justification: str = Field(..., min_length=20, max_length=1000)
    risk_approval_id: Optional[str] = None  # Reference to risk management ticket
```

---

## 6. Missing Details Resolution

### 6.1 Conditional Approval Criteria Definition

```python
# config/conditional_criteria.py
"""
Conditional approval rules hierarchy:
1. GDS 39.01-42% or TDS 44.01-47% → Conditional with debt restructuring
2. Credit score 600-679 → Conditional with higher down payment
3. LTV > 90% → Conditional with co-signer requirement
4. Self-employed with < 2 years → Conditional with additional docs
5. Rental income > 50% of total income → Conditional with property cash flow analysis
"""

CONDITIONAL_RULES = {
    "gds_threshold": Decimal('0.42'),
    "tds_threshold": Decimal('0.47'),
    "min_credit_score_standard": 680,
    "min_credit_score_conditional": 600,
    "max_ltv_conditional": Decimal('0.95'),
    "self_employed_min_years": 2,
}
```

### 6.2 Decline Reason Templates & Priority

```python
# config/decline_reasons.py
from enum import IntEnum

class DeclinePriority(IntEnum):
    """Priority order for decline reasons (higher = more critical)"""
    STRESS_TEST_FAILED = 100
    LTV_EXCEEDED = 90
    INSUFFICIENT_DOWN_PAYMENT = 85
    GDS_EXCEEDED = 80
    TDS_EXCEEDED = 75
    CREDIT_SCORE_TOO_LOW = 70
    INSUFFICIENT_INCOME_DOCUMENTATION = 60
    UNSTABLE_EMPLOYMENT = 50

DECLINE_TEMPLATES = {
    DeclineReason.STRESS_TEST_FAILED: {
        "message": "Application fails OSFI B-20 stress test. Maximum affordable mortgage: ${max_mortgage:,.2f}",
        "priority": DeclinePriority.STRESS_TEST_FAILED,
        "regulatory": True,
        "appealable": False
    },
    DeclineReason.GDS_EXCEEDED: {
        "message": "Gross Debt Service ratio {gds_ratio:.2%} exceeds maximum allowable {limit:.2%}",
        "priority": DeclinePriority.GDS_EXCEEDED,
        "regulatory": True,
        "appealable": True
    },
    DeclineReason.TDS_EXCEEDED: {
        "message": "Total Debt Service ratio {tds_ratio:.2%} exceeds maximum allowable {limit:.2%}",
        "priority": DeclinePriority.TDS_EXCEEDED,
        "regulatory": True,
        "appealable": True
    },
    DeclineReason.CREDIT_SCORE_TOO_LOW: {
        "message": "Credit score {score} below minimum requirement of {min_score}",
        "priority": DeclinePriority.CREDIT_SCORE_TOO_LOW,
        "regulatory": False,
        "appealable": True
    },
}
```

### 6.3 Self-Employed Income Calculation Rules

```python
# services/self_employed_calculator.py
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel

class SelfEmployedIncomeCalculator:
    """
    Self-employed income calculation per CMHC guidelines:
    - 2-year average of net income
    - Add-back: depreciation, business taxes, interest
    - If declining year-over-year, use most recent year
    - Minimum 2 years in same business (exceptions for related field)
    """
    
    @staticmethod
    def calculate_qualifying_income(
        two_year_average: Decimal,
        most_recent_year: Decimal,
        validate_docs: bool = True
    ) -> Decimal:
        """
        Calculate qualifying income for self-employed borrowers
        """
        # Check for declining income trend
        if most_recent_year < (two_year_average * Decimal('0.85')):
            # Use most recent year if declining > 15%
            qualifying_income = most_recent_year
        else:
            # Use 2-year average
            qualifying_income = two_year_average
        
        # Add-back typical non-cash expenses (if documentation validated)
        if validate_docs:
            # Approximate add-backs: 15% of net income
            add_backs = qualifying_income * Decimal('0.15')
            qualifying_income += add_backs
        
        return qualifying_income.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

### 6.4 Rental Income Treatment Rules

```python
# services/rental_income_calculator.py
from decimal import Decimal, ROUND_HALF_UP

class RentalIncomeCalculator:
    """
    Rental income treatment options:
    1. Standard: 50% of gross rental income offset against PITH
    2. Enhanced: 80% offset if strong borrower (credit > 720, LTV < 80%)
    3. Full offset: 100% if cash flow positive for 2+ years
    """
    
    STANDARD_OFFSET_RATE = Decimal('0.50')
    ENHANCED_OFFSET_RATE = Decimal('0.80')
    ENHANCED_CREDIT_THRESHOLD = 720
    ENHANCED_LTV_THRESHOLD = Decimal('0.80')
    
    def calculate_net_rental_income(
        self,
        gross_rental_income: Decimal,
        property_tax_monthly: Decimal,
        insurance_monthly: Decimal,
        credit_score: int,
        ltv_ratio: Decimal = Decimal('0.75')
    ) -> Decimal:
        """
        Calculate net rental income for debt service calculations
        """
        # Determine offset rate based on borrower strength
        if credit_score >= self.ENHANCED_CREDIT_THRESHOLD and ltv_ratio <= self.ENHANCED_LTV_THRESHOLD:
            offset_rate = self.ENHANCED_OFFSET_RATE
        else:
            offset_rate = self.STANDARD_OFFSET_RATE
        
        # Net rental income = Gross rental × offset rate - property costs
        net_rental = (gross_rental_income * offset_rate) - property_tax_monthly - insurance_monthly
        
        return max(Decimal('0'), net_rental).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

### 6.5 Multi-Property Debt Aggregation Strategy

```python
# services/multi_property_aggregator.py
from decimal import Decimal
from typing import List, NamedTuple

class PropertyDebt(NamedTuple):
    """Represents debt tied to a specific property"""
    monthly_payment: Decimal
    is_rental: bool
    rental_income: Decimal
    property_value: Decimal

class MultiPropertyAggregator:
    """
    Aggregate debt service across multiple properties owned by borrower(s)
    
    Strategy:
    1. Primary residence: Full PITH counted
    2. Rental properties: 
       - 50% of rental income offsets carrying costs
       - Net loss added to TDS
       - Net profit added to income
    3. Consumer debt: Full payment counted
    """
    
    def aggregate(
        self,
        primary_property_pith: Decimal,
        rental_properties: List[PropertyDebt],
        consumer_debts: List[Decimal]
    ) -> tuple[Decimal, Decimal]:
        """
        Returns: (total_monthly_housing, total_monthly_debts)
        """
        # Primary residence housing costs
        total_housing = primary_property_pith
        
        # Aggregate rental properties
        total_rental_debt = Decimal('0')
        total_rental_income = Decimal('0')
        
        for prop in rental_properties:
            net_carrying_cost = prop.monthly_payment - (prop.rental_income * Decimal('0.5'))
            
            if net_carrying_cost > 0:
                # Net loss adds to debt obligations
                total_rental_debt += net_carrying_cost
            else:
                # Net profit adds to income (handled in income calculation)
                pass
            
            total_rental_income += prop.rental_income
        
        # Total debt obligations
        total_debts = total_housing + total_rental_debt + sum(consumer_debts)
        
        return total_housing, total_debts
```

---

## 7. Security & Compliance

### 7.1 Authentication & Authorization

```python
# security/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Validate JWT token and extract user claims
    """
    try:
        token = credentials.credentials
        # Verify with Auth0/Keycloak
        payload = jwt.decode(
            token,
            key="https://your-auth-server/.well-known/jwks.json",
            algorithms=["RS256"],
            audience="onlendhub-api",
            issuer="https://your-auth-server/"
        )
        
        return {
            "sub": payload["sub"],
            "roles": payload.get("roles", []),
            "ip_address": payload.get("ip_address")
        }
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )

def require_admin_role(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Require ADMIN role for sensitive operations
    """
    if "ADMIN" not in current_user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user
```

### 7.2 Audit Logging for Regulatory Compliance

```python
# audit/logger.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
from datetime import datetime
import json

class AuditLogger:
    """
    Immutable audit trail for all underwriting actions
    Meets OSFI Guideline E-13 (Data and Transaction Logging)
    """
    
    @staticmethod
    async def log_calculation(
        db: AsyncSession,
        user_id: str,
        correlation_id: str,
        input_data: dict,
        decision: dict,
        ip_address: str = None
    ):
        """Log stateless calculation for compliance"""
        audit_record = {
            "event_type": "UNDERWRITING_CALCULATION",
            "user_id": user_id,
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow(),
            "ip_address": ip_address,
            "input_data": input_data,
            "output_data": decision,
            "system_version": "1.0.0"
        }
        
        # Insert into immutable audit table
        await db.execute(
            insert(AuditLog.__table__).values(audit_record)
        )
        await db.commit()
    
    @staticmethod
    async def log_override(
        db: AsyncSession,
        application_id: uuid.UUID,
        user_id: str,
        correlation_id: str,
        override_data: dict,
        previous_decision: str
    ):
        """Log admin override with justification"""
        audit_record = {
            "event_type": "UNDERWRITING_OVERRIDE",
            "user_id": user_id,
            "application_id": application_id,
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow(),
            "previous_decision": previous_decision,
            "override_data": override_data,
            "requires_risk_approval": True,
            "system_version": "1.0.0"
        }
        
        await db.execute(insert(AuditLog.__table__).values(audit_record))
        await db.commit()

# models/audit.py
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeIGNKey("applications.id"), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    
    # Immutable data stored as JSONB
    event_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    __table_args__ = (
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_correlation', 'correlation_id'),
        {'postgresql_partition_by': 'RANGE (timestamp)'}  # Partition by month
    )
```

---

## 8. Workflow & State Management

```python
# workflow/manager.py
from enum import Enum
from typing import Optional

class WorkflowState(str, Enum):
    INITIAL = "INITIAL"
    DOCUMENT_VERIFICATION = "DOCUMENT_VERIFICATION"
    INCOME_VALIDATION = "INCOME_VALIDATION"
    CREDIT_CHECK = "CREDIT_CHECK"
    PROPERTY_APPRAISAL = "PROPERTY_APPRAISAL"
    UNDERWRITING_EVALUATION = "UNDERWRITING_EVALUATION"
    RISK_REVIEW = "RISK_REVIEW"
    FINAL_APPROVAL = "FINAL_APPROVAL"
    COMPLETED = "COMPLETED"

class WorkflowManager:
    """
    Multi-state workflow with versioning
    Supports both automated and manual underwriting paths
    """
    
    def __init__(self, application_id: uuid.UUID):
        self.application_id = application_id
    
    async def transition_to(
        self,
        new_state: WorkflowState,
        user_id: str,
        comments: Optional[str] = None
    ):
        """
        State transition with audit trail and validation
        """
        # Validate transition
        if not self._is_valid_transition(self.current_state, new_state):
            raise ValueError(f"Invalid transition: {self.current_state} → {new_state}")
        
        # Create state record
        transition = WorkflowTransition(
            application_id=self.application_id,
            from_state=self.current_state,
            to_state=new_state,
            transitioned_by=user_id,
            comments=comments
        )
        
        # Update application
        await self._update_application_status(new_state)
        
        # Log transition
        await AuditLogger.log_workflow_transition(
            application_id=self.application_id,
            transition=transition
        )
```

---

## 9. Deployment & Infrastructure

### 9.1 Docker Configuration

```dockerfile
# Dockerfile
FROM python:3.11.8-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN groupadd -r uwengine && useradd -r -g uwengine uwengine
USER uwengine

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 9.2 PostgreSQL Configuration

```sql
-- migrations/001_create_underwriting_schema.sql
CREATE SCHEMA IF NOT EXISTS underwriting;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create partitioned audit table
CREATE TABLE audit_logs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    application_id UUID,
    correlation_id VARCHAR(255),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ip_address INET,
    event_data JSONB NOT NULL
) PARTITION BY RANGE (timestamp);

-- Create monthly partitions
CREATE TABLE audit_logs_y2024m01 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### 9.3 Kubernetes Deployment

```yaml
# k8s/underwriting-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: underwriting-engine
  namespace: onlendhub
spec:
  replicas: 3
  selector:
    matchLabels:
      app: underwriting-engine
  template:
    metadata:
      labels:
        app: underwriting-engine
    spec:
      containers:
      - name: uw-engine
        image: onlendhub/uw-engine:1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: connection-string
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: jwt-secret
              key: secret
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

---

## 10. Testing Strategy

```python
# tests/test_stress_test_calculator.py
import pytest
from decimal import Decimal

class TestStressTestCalculator:
    def test_osfi_floor_rate(self):
        """Test that 5.25% floor is applied when contract rate is low"""
        calculator = StressTestCalculator()
        qualifying_rate = calculator.calculate_qualifying_rate(
            contract_rate=Decimal('0.03'),
            posted_rate=Decimal('0.0525')
        )
        assert qualifying_rate == Decimal('0.0525')
    
    def test_contract_plus_two_percent(self):
        """Test contract rate + 2% when higher than floor"""
        qualifying_rate = StressTestCalculator.calculate_qualifying_rate(
            contract_rate=Decimal('0.04'),
            posted_rate=Decimal('0.0525')
        )
        assert qualifying_rate == Decimal('0.06')

# tests/test_integration_underwriting.py
@pytest.mark.asyncio
async def test_conditional_approval_scenario(db_session):
    """
    Integration test: GDS 40.5% should result in CONDITIONAL approval
    """
    input_data = UnderwritingInput(
        application_id=uuid.uuid4(),
        property_value=Decimal('750000'),
        property_type='CONDO',
        condo_fee_monthly=Decimal('500'),
        mortgage_amount=Decimal('600000'),
        contract_rate=Decimal('0.0499'),
        amortization_years=25,
        down_payment=Decimal('150000'),
        borrowers=[...]  # Setup with GDS at 40.5%
    )
    
    orchestrator = UnderwritingOrchestrator()
    decision = await orchestrator.evaluate(input_data, evaluator_id="test_user")
    
    assert decision.decision == "CONDITIONAL"
    assert "GDS ratio 40.50% exceeds standard limit" in decision.conditions[0]
```

---

## 11. Performance & Scalability

- **Caching**: Redis for rate tables and rule sets (TTL: 24 hours)
- **Async DB**: SQLAlchemy 2.0 async engine with connection pooling
- **Rate Limiting**: 100 requests/minute per user, 1000/minute per service
- **Circuit Breakers**: For external credit bureau calls (5 failures → 30s open)
- **Horizontal Scaling**: Kubernetes HPA based on CPU (50%) and queue depth

---

## 12. Monitoring & Observability

```python
# monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Business metrics
underwriting_decisions = Counter(
    'underwriting_decisions_total',
    'Total underwriting decisions by type',
    ['decision_type', 'product_type']
)

gds_ratio_distribution = Histogram(
    'underwriting_gds_ratio',
    'Distribution of GDS ratios',
    buckets=[0.30, 0.35, 0.39, 0.42, 0.45, 0.50]
)

# System metrics
calculation_duration = Histogram(
    'underwriting_calculation_seconds',
    'Time spent in underwriting calculation',
    ['calculation_type']
)

audit_log_lag = Gauge(
    'underwriting_audit_log_lag_seconds',
    'Lag between event and audit log persistence'
)
```

This architecture provides a production-ready, regulatorily compliant underwriting engine with clear separation of concerns, immutable audit trails, and support for complex Canadian mortgage rules.