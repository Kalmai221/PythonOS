# Boot PythonOS in QEMU on Windows.   ./run-qemu.ps1 <pythonos .iso or .qcow2> [-Disk]
#   <file>  the ISO (boots like a CD), or the pythonos-<version>-vm.qcow2 disk image (boots like a disk)
#   -Disk   also attach a 2 GB data disk (pythonos-data.img, created once) so `persist create` has somewhere to keep your files
param([Parameter(Mandatory = $true)][string]$Iso, [switch]$Disk)

$qemu = (Get-Command qemu-system-x86_64.exe -ErrorAction SilentlyContinue).Source
if (-not $qemu) { $qemu = "C:\Program Files\qemu\qemu-system-x86_64.exe" }
if (-not (Test-Path $qemu)) { Write-Error "QEMU is not installed (https://www.qemu.org/download/#windows)"; exit 1 }
if (-not (Test-Path $Iso)) { Write-Error "No such file: $Iso"; exit 2 }

$qemuArgs = @("-m", "1024", "-smp", "2", "-nic", "user,model=virtio-net-pci", "-accel", "whpx,kernel-irqchip=off", "-accel", "tcg")
if ($Iso -like "*.qcow2") { $qemuArgs += @("-drive", "file=$Iso,format=qcow2", "-boot", "c") }
elseif ($Iso -like "*.vmdk") { $qemuArgs += @("-drive", "file=$Iso,format=vmdk", "-boot", "c") }
else { $qemuArgs += @("-cdrom", $Iso, "-boot", "d") }
if ($Disk) {
    if (-not (Test-Path "pythonos-data.img")) {
        & (Join-Path (Split-Path $qemu) "qemu-img.exe") create -f qcow2 pythonos-data.img 2G | Out-Null
    }
    $qemuArgs += @("-drive", "file=pythonos-data.img,if=virtio,format=qcow2")
}
& $qemu @qemuArgs
