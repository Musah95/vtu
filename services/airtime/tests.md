$env:DATABASE_URL = 'postgresql://postgres.jnhrzthffxlqjnlrwjwr:pgpass595013@aws-0-eu-west-1.pooler.supabase.com:5432/postgres'


$h = @{ Authorization = "Key vk_4b4d2b89bc18d0d6:ZW4N4bxRTbTwy0C8gGPKo5wBGwoVBCpFUuYQWQl3swo" }
Invoke-RestMethod -Uri "https://vtu-staging.onrender.com/api/v1/wallet/balance/" -Headers $h

Key ID: vk_4b4d2b89bc18d0d6
Secret: ZW4N4bxRTbTwy0C8gGPKo5wBGwoVBCpFUuYQWQl3swo
   
