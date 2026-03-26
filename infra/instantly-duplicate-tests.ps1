# Дублирует все inbox placement тесты за указанную дату
# Использование: .\instantly-duplicate-tests.ps1 -Date "2026-03-20"

param(
    [string]$Date = "2026-03-20",
    [string]$ApiKey = "OWRlZDdiNDctMjU0Ni00N2VhLTk5NjQtNWM3MWQ1N2I3OGI2OnJoWER1SGpuakVodA=="
)

$headers = @{
    'Authorization' = "Bearer $ApiKey"
    'Content-Type'  = 'application/json'
}

# Получить все тесты
$r = Invoke-RestMethod -Uri 'https://api.instantly.ai/api/v2/inbox-placement-tests?limit=50' -Headers $headers -Method GET
$targets = $r.items | Where-Object { $_.timestamp_created -like "$Date*" }

Write-Host "Найдено тестов за $Date`: $($targets.Count)"

foreach ($test in $targets) {
    $body = @{
        name            = $test.name + ' (Copy)'
        type            = $test.type
        sending_method  = $test.sending_method
        email_subject   = $test.email_subject
        email_body      = $test.email_body
        emails          = $test.emails
        recipients      = $test.recipients
        delivery_mode   = $test.delivery_mode
        description     = $test.description
        tags            = $test.tags
        text_only       = $test.text_only
    } | ConvertTo-Json -Depth 5

    try {
        $result = Invoke-RestMethod -Uri 'https://api.instantly.ai/api/v2/inbox-placement-tests' -Headers $headers -Method POST -Body $body
        Write-Host "OK: $($result.id) | $($result.name)"
    } catch {
        $stream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        Write-Host "FAIL: $($test.name) — $($reader.ReadToEnd())"
    }

    Start-Sleep -Milliseconds 300
}
