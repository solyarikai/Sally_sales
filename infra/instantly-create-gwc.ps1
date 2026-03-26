# Создаёт тест GWC с 14 ящиками Hugo
# Использование: .\instantly-create-gwc.ps1

param(
    [string]$ApiKey = "OWRlZDdiNDctMjU0Ni00N2VhLTk5NjQtNWM3MWQ1N2I3OGI2OnJoWER1SGpuakVodA=="
)

$headers = @{
    'Authorization' = "Bearer $ApiKey"
    'Content-Type'  = 'application/json'
}

$hugoEmails = @(
    'hugo.k@gatewaycryptosolutions.com',
    'hugo@gatewaycryptosolution.com',
    'hugo@gatewaycryptosolutions.com',
    'hugo.k@gatewaycrypto-processor.com',
    'hugo.k@gatewaycryptotools.com',
    'hugo@gatewaycrypto-solution.com',
    'hugo.k@gatewaycrypto-solutions.com',
    'hugo.k@gatewaycrypto-solution.com',
    'hugo@gatewaycrypto-processor.com',
    'hugo@gatewaycrypto-solutions.com',
    'hugo@gatewaycryptotools.com',
    'hugo.k@gatewaycryptoprocessor.com',
    'hugo@gatewaycryptoprocessor.com',
    'hugo.k@gatewaycryptosolution.com'
)

# Берём recipients и структуру из первого существующего теста
$r = Invoke-RestMethod -Uri 'https://api.instantly.ai/api/v2/inbox-placement-tests?limit=1' -Headers $headers -Method GET
$template = $r.items[0]

$body = @{
    name           = 'GWC'
    type           = $template.type
    sending_method = $template.sending_method
    email_subject  = $template.email_subject
    email_body     = $template.email_body
    emails         = $hugoEmails
    recipients     = $template.recipients
    delivery_mode  = $template.delivery_mode
    description    = ''
    tags           = @()
    text_only      = $false
} | ConvertTo-Json -Depth 5

try {
    $result = Invoke-RestMethod -Uri 'https://api.instantly.ai/api/v2/inbox-placement-tests' -Headers $headers -Method POST -Body $body
    Write-Host "Создан: $($result.id) | $($result.name) | ящиков: $($result.emails.Count)"
} catch {
    $stream = $_.Exception.Response.GetResponseStream()
    $reader = New-Object System.IO.StreamReader($stream)
    Write-Host "Ошибка: $($_.Exception.Response.StatusCode.Value__)"
    Write-Host $reader.ReadToEnd()
}
