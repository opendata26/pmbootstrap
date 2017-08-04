"""
Copyright 2017 Pablo Castellano

This file is part of pmbootstrap.

pmbootstrap is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

pmbootstrap is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with pmbootstrap.  If not, see <http://www.gnu.org/licenses/>.
"""
import logging
import os

import pmb.build
import pmb.chroot
import pmb.chroot.apk
import pmb.chroot.other
import pmb.chroot.initfs
import pmb.helpers.devices
import pmb.helpers.run
import pmb.parse.arch


def system_image(args, device):
    """
    Returns path to system image for specified device. In case that it doesn't
    exist, raise and exception explaining how to generate it.
    """
    path = args.work + "/chroot_native/home/user/rootfs/" + device + ".img"
    if not os.path.exists(path):
        logging.debug("Could not find system image: " + path)
        img_command = "pmbootstrap install"
        if device != args.device:
            img_command = "pmbootstrap init' and '" + img_command
        message = "The system image '{0}' has not been generated yet, please" \
                  " run '{1}' first.".format(device, img_command)
        raise RuntimeError(message)
    return path


def qemu_command(args, arch, device, img_path):
    """
    Generate the full QEMU command with arguments to run postmarketOS
    """
    deviceinfo = pmb.parse.deviceinfo(args, device=device)
    cmdline = deviceinfo["kernel_cmdline"]
    if args.cmdline:
        cmdline = args.cmdline
    logging.info("cmdline: " + cmdline)

    qemu_bin = "qemu-system-" + arch
    rootfs = args.work + "/chroot_rootfs_" + device
    command = [qemu_bin,
               "-kernel", rootfs + "/boot/vmlinuz-postmarketos",
               "-initrd", rootfs + "/boot/initramfs-postmarketos",
               "-m", str(args.memory),
               "-append", '"' + cmdline + '"']

    if arch != "x86_64":
        machine = {
            "armhf": "vexpress-a9",
            "aarch64": "virt"
        }
        dtb_image = rootfs + "/usr/share/dtb/" + deviceinfo["dtb"] + ".dtb"
        if not os.path.exists(dtb_image):
            raise RuntimeError("DTB file not found: " + dtb_image)
        command += ["-dtb", dtb_image,
                    "-sd", img_path,
                    "-M", machine[arch]]
    else:
        command += ["-serial", "stdio",
                    "-drive", "file=" + img_path + ",format=raw"]

    # Kernel Virtual Machine (KVM) support
    enable_kvm = True
    if args.arch:
        arch1 = pmb.parse.arch.uname_to_qemu(args.arch_native)
        arch2 = pmb.parse.arch.uname_to_qemu(args.arch)
        enable_kvm = (arch1 == arch2)
    if enable_kvm and os.path.exists("/dev/kvm"):
        command += ["-enable-kvm"]
    else:
        logging.info("Warning: QEMU is not using KVM and will run slower!")

    return command


def run(args):
    """
    Run a postmarketOS image in QEMU
    """
    arch = pmb.parse.arch.uname_to_qemu(args.arch_native)
    if args.arch:
        arch = pmb.parse.arch.uname_to_qemu(args.arch)
    logging.info("Running postmarketOS in QEMU VM (" + arch + ")")

    device = pmb.parse.arch.qemu_to_pmos_device(arch)
    img_path = system_image(args, device)

    # Workaround: QEMU runs as local user and needs write permissions in the
    # system image, which is owned by root
    if not os.access(img_path, os.W_OK):
        pmb.helpers.run.root(args, ["chmod", "666", img_path])

    command = qemu_command(args, arch, device, img_path)

    logging.info("Command: " + " ".join(command))
    pmb.helpers.run.user(args, command)
