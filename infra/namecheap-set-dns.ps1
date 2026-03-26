# Set standard email infrastructure DNS records on Namecheap domains
# Records: MX, SPF, DMARC, emailtracking CNAME, URL redirect (www)
#
# Note: Namecheap does not allow MX and URL redirect on @ simultaneously.
# URL redirect is set on www host instead, @ is reserved for email (MX).
#
# Usage:
#   .\namecheap-set-dns.ps1 -Domains "d1.com","d2.com" -RedirectUrl "https://example.com/"
#   .\namecheap-set-dns.ps1 -DomainsFile domains.txt -RedirectUrl "https://example.com/"

param(
    [string[]]$Domains,
    [string]$DomainsFile,
    [Parameter(Mandatory=$true)]
    [string]$RedirectUrl,
    [string]$ApiKey = "f3335861b92247779364649ae2beb014",
    [string]$ApiUser = "decaster3",
    [string]$ClientIp = "150.241.224.134"
)

if ($DomainsFile) {
    $Domains = Get-Content $DomainsFile | Where-Object { $_.Trim() -ne "" }
}

if (-not $Domains) {
    Write-Error "Specify -Domains or -DomainsFile"
    exit 1
}

$apiBase = "https://api.namecheap.com/xml.response?ApiUser=$ApiUser&ApiKey=$ApiKey&UserName=$ApiUser&ClientIp=$ClientIp"
$wc = New-Object System.Net.WebClient

$ok = @(); $fail = @()

foreach ($domain in $Domains) {
    $domain = $domain.Trim()

    $lastDot = $domain.LastIndexOf('.')
    $sld = $domain.Substring(0, $lastDot)
    $tld = $domain.Substring($lastDot + 1)

    $spf   = [uri]::EscapeDataString("v=spf1 include:_spf.google.com ~all")
    $dmarc = [uri]::EscapeDataString("v=DMARC1; p=reject; rua=mailto:dmarc-reports@$domain; ruf=mailto:dmarc-reports@$domain; sp=reject; adkim=s; fo=1;")
    $redir = [uri]::EscapeDataString($RedirectUrl)

    $url = "$apiBase&Command=namecheap.domains.dns.setHosts&SLD=$sld&TLD=$tld" +
        "&HostName1=@&RecordType1=MX&Address1=SMTP.GOOGLE.COM&MXPref1=1&TTL1=1800" +
        "&HostName2=@&RecordType2=TXT&Address2=$spf&TTL2=1800" +
        "&HostName3=_dmarc&RecordType3=TXT&Address3=$dmarc&TTL3=1800" +
        "&HostName4=emailtracking&RecordType4=CNAME&Address4=open.sleadtrack.com&TTL4=1800" +
        "&HostName5=www&RecordType5=URL301&Address5=$redir&TTL5=1800"

    try {
        [xml]$r = $wc.DownloadString($url)
        if ($r.ApiResponse.Status -eq "OK") {
            Write-Host "OK: $domain"
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

    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host "=== Done: OK=$($ok.Count) FAIL=$($fail.Count) ==="
if ($fail.Count -gt 0) {
    Write-Host "Failed:"
    $fail | ForEach-Object { Write-Host "  $_" }
}
