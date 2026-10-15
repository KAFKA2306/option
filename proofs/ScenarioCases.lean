import ContractSemantics

def bit (value : Bool) : String := if value then "1" else "0"

def main : IO Unit := do
  let types : List ContractSemantics.ContractType := [
    .perpetual, .perpetualDelivering, .currentMonth, .nextMonth,
    .currentQuarter, .nextQuarter]
  for t in types do
    IO.println s!"{ContractSemantics.label t},{bit (ContractSemantics.isPerpetual t)},{bit (ContractSemantics.mayAnnualize t 30)},{bit (ContractSemantics.mayAnnualize t 0)}"
