# Boot the PythonOS ISO in QEMU on Windows.   ./run-qemu.ps1 pythonos-<version>-x86_64.iso [-Disk]
param([Parameter(Mandatory = $true)][string]$Iso, [switch]$Disk)

$qemu = (Get-Command qemu-system-x86_64.exe -ErrorAction SilentlyContinue).Source
if (-not $qemu) { $qemu = "C:\Program Files\qemu\qemu-system-x86_64.exe" }
if (-not (Test-Path $qemu)) { Write-Error "QEMU is not installed (https://www.qemu.org/download/#windows)"; exit 1 }
if (-not (Test-Path $Iso)) { Write-Error "No such file: $Iso"; exit 2 }

$args = @("-m", "1024", "-smp", "2", "-cdrom", $Iso, "-boot", "d", "-nic", "user,model=virtio-net-pci", "-accel", "whpx,kernel-irqchip=off", "-accel", "tcg")
if ($Disk) {
    if (-not (Test-Path "pythonos-data.img")) {
        & (Join-Path (Split-Path $qemu) "qemu-img.exe") create -f qcow2 pythonos-data.img 2G | Out-Null
    }
    $args += @("-drive", "file=pythonos-data.img,if=virtio,format=qcow2")
}
& $qemu @args
