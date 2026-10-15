import Init

/-!
A finite classification model for the six supported futures contract types.
Correctness of the Python mapping is checked separately with an executable
Lean-to-Python bridge. Floating point/market source correctness is not proven.
-/

namespace ContractSemantics

inductive ContractType
  | perpetual | perpetualDelivering
  | currentMonth | nextMonth | currentQuarter | nextQuarter
  deriving Repr, BEq, DecidableEq

def label : ContractType → String
  | .perpetual => "PERPETUAL"
  | .perpetualDelivering => "PERPETUAL_DELIVERING"
  | .currentMonth => "CURRENT_MONTH"
  | .nextMonth => "NEXT_MONTH"
  | .currentQuarter => "CURRENT_QUARTER"
  | .nextQuarter => "NEXT_QUARTER"

def isPerpetual : ContractType → Bool
  | .perpetual | .perpetualDelivering => true
  | _ => false

def isDelivery (t : ContractType) : Bool := !isPerpetual t

/-- A delivery basis can be annualized only for a delivery contract
    with strictly positive remaining calendar days. -/
def mayAnnualize (t : ContractType) (daysLeft : Nat) : Bool :=
  isDelivery t && decide (0 < daysLeft)

theorem complete_classification (t : ContractType) :
    (isPerpetual t || isDelivery t) = true := by
  cases t <;> decide

theorem exclusive_classification (t : ContractType) :
    (isPerpetual t && isDelivery t) = false := by
  cases t <;> decide

theorem perpetual_never_delivery_annualized (daysLeft : Nat) :
    mayAnnualize .perpetual daysLeft = false ∧
    mayAnnualize .perpetualDelivering daysLeft = false := by
  simp [mayAnnualize, isPerpetual, isDelivery]

theorem zero_days_never_annualized (t : ContractType) :
    mayAnnualize t 0 = false := by
  simp [mayAnnualize]

end ContractSemantics
