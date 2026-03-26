# Enable WhoisGuard (domain privacy) on domains where it is not yet active
#
# Usage:
#   .\namecheap-enable-whoisguard.ps1 -Domains "domain1.com","domain2.com"
#   .\namecheap-enable-whoisguard.ps1 -DomainsFile domains.txt
#   .\namecheap-enable-whoisguard.ps1 -SearchTerm "easystaff"   # all matching domains

param(
    [string[]]$Domains,
    [string]$DomainsFile,
    [string]$SearchTerm,
    [string]$ApiKey = "f3335861b92247779364649ae2beb014",
    [string]$ApiUser = "decaster3",
    [string]$ClientIp = "150.241.224.134",
    [string]$ForwardEmail = "rinat.khatipov@gmail.com"
)

$apiBase = "https://api.namecheap.com/xml.response?ApiUser=$ApiUser&ApiKey=$ApiKey&UserName=$ApiUser&ClientIp=$ClientIp"
$wc = New-Object System.Net.WebClient

if ($DomainsFile) {
    $Domains = Get-Content $DomainsFile | Where-Object { $_.Trim() -ne "" }
} elseif ($SearchTerm) {
    [xml]$r = $wc.DownloadString("$apiBase&Command=namecheap.domains.getList&PageSize=100&SearchTerm=$SearchTerm")
    $Domains = $r.ApiResponse.CommandResponse.DomainGetListResult.Domain |
        Where-Object { $_.WhoisGuard -ne "ENABLED" } |
        ForEach-Object { $_.Name }
    Write-Host "Found domains without active WhoisGuard: $($Domains.Count)"
}

if (-not $Domains) {
    Write-Error "Specify -Domains, -DomainsFile, or -SearchTerm"
    exit 1
}

Write-Host "Loading WhoisGuard subscriptions..."
[xml]$wgList = $wc.DownloadString("$apiBase&Command=namecheap.whoisguard.getList&PageSize=100")
$wgMap = @{}
$wgList.ApiResponse.CommandResponse.WhoisguardGetListResult.Whoisguard | ForEach-Object {
    $wgMap[$_.DomainName.ToLower()] = $_.ID
}

$ok = @(); $fail = @()

foreach ($domain in $Domains) {
    $domain = $domain.Trim()
    $wgId = $wgMap[$domain.ToLower()]

    if (-not $wgId) {
        Write-Host "SKIP: $domain -- no WhoisGuard subscription found"
        $fail += $domain
        continue
    }

    $urlEnable = "$apiBase&Command=namecheap.whoisguard.enable&WhoisguardId=$wgId&ForwardedToEmail=$ForwardEmail"
    try {
        [xml]$r = $wc.DownloadString($urlEnable)
        if ($r.ApiResponse.Status -eq "OK") {
            Write-Host "OK: $domain (WG ID: $wgId)"
            $ok += $domain
        } else {
            $err = $r.ApiResponse.Errors.Error.'#text'
            Write-Host "FAIL: $domain -- $err"
            $fail += $domain
        }
    } catch {
        Write-Host "FAIL: $domain -- $($_.Exception.Message)"
        $fail += $domain
    }

    Start-Sleep -Milliseconds 300
}

Write-Host ""
Write-Host "=== Done: OK=$($ok.Count) FAIL=$($fail.Count) ==="
if ($fail.Count -gt 0) {
    Write-Host "Not activated:"
    $fail | ForEach-Object { Write-Host "  $_" }
}
