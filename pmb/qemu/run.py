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


def run(args):
    """
    Run qemu with the already generated postmarketOS image
    """
    logging.info("Running postmarketOS in QEMU VM (" + args.arch + ")")

    # Check if the system image is already generated
    img_path = "/home/user/rootfs/" + args.device + ".img"
    if not os.path.exists(args.work + "/chroot_native" + img_path):
        raise RuntimeError("The system image has not been generated yet,"
                           " please run 'pmbootstrap install' first.")

    # Workaround: qemu runs as local user and needs write permissions
    if not os.access(img_path, os.W_OK):
        pmb.helpers.run.root(args, ["chmod", "666", img_path])

    _cmdline = args.deviceinfo["kernel_cmdline"]
    if args.cmdline:
        _cmdline = args.cmdline
    _cmdline = '"' + _cmdline + '"'

    rootfs = args.work + "/chroot_rootfs_" + args.device
    dtb_image = rootfs + "/usr/share/dtb/" + args.deviceinfo["dtb"] + ".dtb"

    arch_mapping = {
        "x86_64": "amd64",
        "armhf": "vexpress-a9",
    }
    qemu_bin = "qemu-system-" + args.arch
    command = [qemu_bin,
               "-kernel", rootfs + "/boot/vmlinuz-postmarketos",
               "-initrd", rootfs + "/boot/initramfs-postmarketos",
               "-M", arch_mapping[args.arch],
               "-m", str(args.memory),
               "-sd", img_path,
               "-append", _cmdline,
               "-dtb", dtb_image]

    pmb.helpers.run.user(args, command)

