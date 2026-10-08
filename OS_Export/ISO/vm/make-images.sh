#!/usr/bin/env bash
# Build ready-to-import virtual machine images from the full ISO (CI runs this; you can too).
#
#   bash make-images.sh dist/iso/pythonos-1.2.0-x86_64.iso 1.2.0 dist/vm
#
# Produces in the output folder:
#   pythonos-<version>-vm.qcow2   a bootable virtual disk for QEMU / KVM / Proxmox / libvirt (attach it as a disk, boot it)
#   pythonos-<version>-vm-data.qcow2  the matching 2 GB data disk (labelled PYOS_DATA): attach it as a second disk and the VM keeps your
#                                 accounts, files and settings between runs
#   pythonos-<version>-vm.ova     an appliance for VirtualBox and VMware (File > Import Appliance): 1 GB memory, 2 CPUs, NAT network, sound,
#                                 a second 2 GB disk (labelled PYOS_DATA) that keeps your accounts, files and settings between runs, and a third,
#                                 empty 8 GB disk that `installos` can install PythonOS on (it takes almost no space: the empty disk is not stored)
#   pythonos-<version>-vm-kit.zip the run/create scripts and the .vmx for people who would rather attach the ISO themselves
#
# Why a disk can be made from an ISO: the PythonOS ISO is a hybrid image (it boots as a CD and as a disk, BIOS and UEFI),
# so converting its bytes to a disk format gives a bootable disk. It is still the live system: changes are forgotten at power off
# unless a data disk is attached. The OVA ships with one already (the live system finds the disk labelled PYOS_DATA by itself); for the
# qcow2, attach a second disk and run `persist create` inside PythonOS (run-qemu.sh --disk adds one).
set -euo pipefail

ISO="${1:?usage: make-images.sh <iso> <version> <outdir>}"
VERSION="${2:?usage: make-images.sh <iso> <version> <outdir>}"
OUT="${3:?usage: make-images.sh <iso> <version> <outdir>}"
HERE="$(cd "$(dirname "$0")" && pwd)"
command -v qemu-img >/dev/null || { echo "qemu-img is required (apt install qemu-utils)" >&2; exit 1; }
[ -f "$ISO" ] || { echo "No such file: $ISO" >&2; exit 1; }
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"            # absolute: the packing steps below change directory
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# 1) qcow2 for QEMU/KVM
qemu-img convert -f raw -O qcow2 -c "$ISO" "$OUT/pythonos-$VERSION-vm.qcow2"

# 2) OVA: an OVF description plus a streamOptimized VMDK, packed as a tar (the OVF must come first)
DISK="pythonos-$VERSION-disk1.vmdk"
qemu-img convert -f raw -O vmdk -o subformat=streamOptimized "$ISO" "$WORK/$DISK"
BYTES="$(stat -c %s "$ISO" 2>/dev/null || stat -f %z "$ISO")"
FILE_SIZE="$(stat -c %s "$WORK/$DISK" 2>/dev/null || stat -f %z "$WORK/$DISK")"

# a ready-made data disk: an empty ext4 filesystem labelled PYOS_DATA. PythonOS mounts it at start and keeps accounts, files and settings on it.
DATA="pythonos-$VERSION-data.vmdk"
DATA_BYTES=$((2 * 1024 * 1024 * 1024))
command -v mkfs.ext4 >/dev/null || { echo "mkfs.ext4 is required (apt install e2fsprogs)" >&2; exit 1; }
truncate -s "$DATA_BYTES" "$WORK/data.img"
mkfs.ext4 -q -F -L PYOS_DATA -m 0 "$WORK/data.img"
qemu-img convert -f raw -O vmdk -o subformat=streamOptimized "$WORK/data.img" "$WORK/$DATA"
qemu-img convert -f raw -O qcow2 -c "$WORK/data.img" "$OUT/pythonos-$VERSION-vm-data.qcow2"      # the same disk for QEMU/KVM/Proxmox
rm -f "$WORK/data.img"
DATA_FILE_SIZE="$(stat -c %s "$WORK/$DATA" 2>/dev/null || stat -f %z "$WORK/$DATA")"

# an empty spare disk (no filesystem at all) for `installos`. A stream-optimised disk stores no empty blocks, so it adds only a few KB to the download.
SPARE="pythonos-$VERSION-spare.vmdk"
SPARE_BYTES=$((8 * 1024 * 1024 * 1024))
truncate -s "$SPARE_BYTES" "$WORK/spare.img"
# A stream-optimised disk with no data at all has no blocks, and VirtualBox cannot import such a file (VERR_EOF while creating the medium).
# So the disk carries a short label one megabyte in (never in the first sector, so no partition table or filesystem is suggested).
printf 'PYTHONOS-SPARE-DISK (empty: installos can use it)
' | dd of="$WORK/spare.img" bs=1M seek=1 conv=notrunc status=none
qemu-img convert -f raw -O vmdk -o subformat=streamOptimized "$WORK/spare.img" "$WORK/$SPARE"
# the converted disk must hold data (an empty one is the VERR_EOF import failure)
qemu-img map --output=json "$WORK/$SPARE" | grep -q '"data": *true' || { echo "the spare disk image has no data blocks; VirtualBox could not import it" >&2; exit 1; }
rm -f "$WORK/spare.img"
SPARE_FILE_SIZE="$(stat -c %s "$WORK/$SPARE" 2>/dev/null || stat -f %z "$WORK/$SPARE")"
cat > "$WORK/pythonos-$VERSION.ovf" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<Envelope vmw:buildId="build-pythonos" xmlns="http://schemas.dmtf.org/ovf/envelope/1" xmlns:cim="http://schemas.dmtf.org/wbem/wscim/1/common"
          xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1" xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData"
          xmlns:vmw="http://www.vmware.com/schema/ovf" xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <References>
    <File ovf:href="$DISK" ovf:id="file1" ovf:size="$FILE_SIZE"/>
    <File ovf:href="$DATA" ovf:id="file2" ovf:size="$DATA_FILE_SIZE"/>
    <File ovf:href="$SPARE" ovf:id="file3" ovf:size="$SPARE_FILE_SIZE"/>
  </References>
  <DiskSection>
    <Info>Virtual disk information</Info>
    <Disk ovf:capacity="$BYTES" ovf:capacityAllocationUnits="byte" ovf:diskId="vmdisk1" ovf:fileRef="file1"
          ovf:format="http://www.vmware.com/interfaces/specifications/vmdk.html#streamOptimized"/>
    <Disk ovf:capacity="$DATA_BYTES" ovf:capacityAllocationUnits="byte" ovf:diskId="vmdisk2" ovf:fileRef="file2"
          ovf:format="http://www.vmware.com/interfaces/specifications/vmdk.html#streamOptimized"/>
    <Disk ovf:capacity="$SPARE_BYTES" ovf:capacityAllocationUnits="byte" ovf:diskId="vmdisk3" ovf:fileRef="file3"
          ovf:format="http://www.vmware.com/interfaces/specifications/vmdk.html#streamOptimized"/>
  </DiskSection>
  <NetworkSection>
    <Info>The list of logical networks</Info>
    <Network ovf:name="NAT"><Description>NAT</Description></Network>
  </NetworkSection>
  <VirtualSystem ovf:id="PythonOS $VERSION">
    <Info>PythonOS $VERSION live system</Info>
    <Name>PythonOS $VERSION</Name>
    <OperatingSystemSection ovf:id="101" vmw:osType="other4xLinux64Guest">
      <Info>Other Linux (64-bit)</Info>
    </OperatingSystemSection>
    <VirtualHardwareSection>
      <Info>Virtual hardware requirements</Info>
      <System>
        <vssd:ElementName>Virtual Hardware Family</vssd:ElementName>
        <vssd:InstanceID>0</vssd:InstanceID>
        <vssd:VirtualSystemIdentifier>PythonOS $VERSION</vssd:VirtualSystemIdentifier>
        <vssd:VirtualSystemType>vmx-14</vssd:VirtualSystemType>
      </System>
      <Item>
        <rasd:AllocationUnits>hertz * 10^6</rasd:AllocationUnits>
        <rasd:Description>Number of Virtual CPUs</rasd:Description>
        <rasd:ElementName>2 virtual CPU(s)</rasd:ElementName>
        <rasd:InstanceID>1</rasd:InstanceID>
        <rasd:ResourceType>3</rasd:ResourceType>
        <rasd:VirtualQuantity>2</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:AllocationUnits>byte * 2^20</rasd:AllocationUnits>
        <rasd:Description>Memory Size</rasd:Description>
        <rasd:ElementName>1024MB of memory</rasd:ElementName>
        <rasd:InstanceID>2</rasd:InstanceID>
        <rasd:ResourceType>4</rasd:ResourceType>
        <rasd:VirtualQuantity>1024</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:Address>0</rasd:Address>
        <rasd:Description>SATA Controller</rasd:Description>
        <rasd:ElementName>sataController0</rasd:ElementName>
        <rasd:InstanceID>3</rasd:InstanceID>
        <rasd:ResourceSubType>AHCI</rasd:ResourceSubType>
        <rasd:ResourceType>20</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
        <rasd:ElementName>Hard Disk 1</rasd:ElementName>
        <rasd:HostResource>ovf:/disk/vmdisk1</rasd:HostResource>
        <rasd:InstanceID>4</rasd:InstanceID>
        <rasd:Parent>3</rasd:Parent>
        <rasd:ResourceType>17</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:AddressOnParent>1</rasd:AddressOnParent>
        <rasd:ElementName>Hard Disk 2 (PythonOS data)</rasd:ElementName>
        <rasd:HostResource>ovf:/disk/vmdisk2</rasd:HostResource>
        <rasd:InstanceID>7</rasd:InstanceID>
        <rasd:Parent>3</rasd:Parent>
        <rasd:ResourceType>17</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:AddressOnParent>2</rasd:AddressOnParent>
        <rasd:ElementName>Hard Disk 3 (empty, for installos)</rasd:ElementName>
        <rasd:HostResource>ovf:/disk/vmdisk3</rasd:HostResource>
        <rasd:InstanceID>8</rasd:InstanceID>
        <rasd:Parent>3</rasd:Parent>
        <rasd:ResourceType>17</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Connection>NAT</rasd:Connection>
        <rasd:ElementName>Ethernet adapter on NAT</rasd:ElementName>
        <rasd:InstanceID>5</rasd:InstanceID>
        <rasd:ResourceSubType>E1000</rasd:ResourceSubType>
        <rasd:ResourceType>10</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:AutomaticAllocation>false</rasd:AutomaticAllocation>
        <rasd:ElementName>Sound Card</rasd:ElementName>
        <rasd:InstanceID>6</rasd:InstanceID>
        <rasd:ResourceSubType>ensoniq1371</rasd:ResourceSubType>
        <rasd:ResourceType>5</rasd:ResourceType>
      </Item>
    </VirtualHardwareSection>
  </VirtualSystem>
</Envelope>
EOF
(cd "$WORK" && tar -cf "$OUT/pythonos-$VERSION-vm.ova" "pythonos-$VERSION.ovf" "$DISK" "$DATA" "$SPARE")

# 3) the scripts and the .vmx, for attaching the ISO yourself
(cd "$HERE" && zip -q -r "$OUT/pythonos-$VERSION-vm-kit.zip" README.md run-qemu.sh run-qemu.ps1 create-virtualbox.sh create-virtualbox.ps1 pythonos.vmx)

ls -la "$OUT"
