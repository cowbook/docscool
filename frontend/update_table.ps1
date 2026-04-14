(Get-Content 'c:\Users\taozh\docscool\frontend\src\views\ContractView.vue' -Raw).Replace(
':data="aiMatchCandidates"`n            stripe`n            size="small"',
':data="aiMatchCandidates"`n            stripe`n            border`n            resizable`n            size="small"'
) | Set-Content 'c:\Users\taozh\docscool\frontend\src\views\ContractView.vue' -NoNewline
