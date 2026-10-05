# Create a VirtualBox VM called "PythonOS" that boots the ISO.   ./create-virtualbox.ps1 pythonos-<version>-x86_64.iso
param([Parameter(Mandatory = $true)][string]$Iso)

$vbox = (Get-Command VBoxManage.exe -ErrorAction SilentlyContinue).Source
if (-not $vbox) { $vbox = "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" }
if (-not (Test-Path $vbox)) { Write-Error "VirtualBox is not installed."; exit 1 }
if (-not (Test-Path $Iso)) { Write-Error "No such file: $Iso"; exit 2 }
$Iso = (Resolve-Path $Iso).Path
$name = "PythonOS"

& $vbox showvminfo $name 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { Write-Error "A VM called $name already exists. Remove it first."; exit 1 }

& $vbox createvm --name $name --ostype Linux26_64 --register
& $vbox modifyvm $name --memory 1024 --cpus 2 --vram 16 --graphicscontroller vmsvga --firmware efi --nic1 nat --nictype1 virtio --audio-driver default --audio-controller ac97 --rtcuseutc on
& $vbox storagectl $name --name "IDE" --add ide
& $vbox storageattach $name --storagectl "IDE" --port 0 --device 0 --type dvddrive --medium $Iso
Write-Host "Created. Start it from the VirtualBox window or:  VBoxManage startvm $name"
