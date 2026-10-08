# Create a VirtualBox VM called "PythonOS" that boots the ISO, with a 2 GB data disk so your accounts and files are kept.
#   ./create-virtualbox.ps1 pythonos-<version>-x86_64.iso [-NoData]
# The data disk is PythonOS-data.vdi, created in the folder you run this from; keep that file. The first time, run `persist create` inside PythonOS.
param([Parameter(Mandatory = $true)][string]$Iso, [switch]$NoData)

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

if (-not $NoData) {
    $data = Join-Path (Get-Location).Path "PythonOS-data.vdi"
    if (-not (Test-Path $data)) { & $vbox createmedium disk --filename $data --size 2048 --format VDI | Out-Null }
    & $vbox storagectl $name --name "SATA" --add sata
    & $vbox storageattach $name --storagectl "SATA" --port 0 --device 0 --type hdd --medium $data
    Write-Host "Data disk: $data (keep it; the first time, run 'persist create' inside PythonOS)"
}
Write-Host "Created. Start it from the VirtualBox window or:  VBoxManage startvm $name"
