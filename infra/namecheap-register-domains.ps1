# Register domains on Namecheap with WhoisGuard (domain privacy) enabled
#
# Usage:
#   .\namecheap-register-domains.ps1 -Domains "domain1.com","domain2.com"
#   .\namecheap-register-domains.ps1 -DomainsFile domains.txt   # one domain per line

param(
    [string[]]$Domains,
    [string]$DomainsFile,
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

$contact = @{
    FirstName        = "Rinat"
    LastName         = "Khatipov"
    Address1         = "Georgia, Tbilisi, Samgori District, Police Street I Dead End"
    City             = "Tbilisi"
    StateProvince    = "NA"
    PostalCode       = "0144"
    Country          = "GE"
    Phone            = "+995.551348977"
    EmailAddress     = "rinat.khatipov@gmail.com"
    OrganizationName = "Getsally"
}

$ok = @(); $fail = @()

foreach ($domain in $Domains) {
    $domain = $domain.Trim()
    $url = "https://api.namecheap.com/xml.response?" +
        "ApiUser=$ApiUser&ApiKey=$ApiKey&UserName=$ApiUser&ClientIp=$ClientIp" +
        "&Command=namecheap.domains.create" +
        "&DomainName=$domain&Years=1" +
        "&AddFreeWhoisguard=yes&WGEnabled=yes" +
        "&RegistrantFirstName=$($contact.FirstName)&RegistrantLastName=$($contact.LastName)" +
        "&RegistrantAddress1=$($contact.Address1)&RegistrantCity=$($contact.City)" +
        "&RegistrantStateProvince=$($contact.StateProvince)&RegistrantPostalCode=$($contact.PostalCode)" +
        "&RegistrantCountry=$($contact.Country)&RegistrantPhone=$($contact.Phone)" +
        "&RegistrantEmailAddress=$($contact.EmailAddress)&RegistrantOrganizationName=$($contact.OrganizationName)" +
        "&TechFirstName=$($contact.FirstName)&TechLastName=$($contact.LastName)" +
        "&TechAddress1=$($contact.Address1)&TechCity=$($contact.City)" +
        "&TechStateProvince=$($contact.StateProvince)&TechPostalCode=$($contact.PostalCode)" +
        "&TechCountry=$($contact.Country)&TechPhone=$($contact.Phone)" +
        "&TechEmailAddress=$($contact.EmailAddress)&TechOrganizationName=$($contact.OrganizationName)" +
        "&AdminFirstName=$($contact.FirstName)&AdminLastName=$($contact.LastName)" +
        "&AdminAddress1=$($contact.Address1)&AdminCity=$($contact.City)" +
        "&AdminStateProvince=$($contact.StateProvince)&AdminPostalCode=$($contact.PostalCode)" +
        "&AdminCountry=$($contact.Country)&AdminPhone=$($contact.Phone)" +
        "&AdminEmailAddress=$($contact.EmailAddress)&AdminOrganizationName=$($contact.OrganizationName)" +
        "&AuxBillingFirstName=$($contact.FirstName)&AuxBillingLastName=$($contact.LastName)" +
        "&AuxBillingAddress1=$($contact.Address1)&AuxBillingCity=$($contact.City)" +
        "&AuxBillingStateProvince=$($contact.StateProvince)&AuxBillingPostalCode=$($contact.PostalCode)" +
        "&AuxBillingCountry=$($contact.Country)&AuxBillingPhone=$($contact.Phone)" +
        "&AuxBillingEmailAddress=$($contact.EmailAddress)&AuxBillingOrganizationName=$($contact.OrganizationName)"

    try {
        $wc = New-Object System.Net.WebClient
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
    Write-Host "Not registered:"
    $fail | ForEach-Object { Write-Host "  $_" }
}
