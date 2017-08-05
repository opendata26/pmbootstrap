"""
Copyright 2017 Oliver Smith

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
import glob

import pmb.chroot
import pmb.chroot.apk
import pmb.chroot.other
import pmb.chroot.initfs
import pmb.config
import pmb.helpers.run
import pmb.install.blockdevice
import pmb.install


def mount_device_rootfs(args):
    # Mount the device rootfs
    logging.info("(native) copy rootfs_" + args.device + " to" +
                 " /mnt/install/")
    mountpoint = "/mnt/rootfs_" + args.device
    pmb.helpers.mount.bind(args, args.work + "/chroot_rootfs_" + args.device,
                           args.work + "/chroot_native" + mountpoint)
    return mountpoint


def get_chroot_size(args):
    # Mount the device rootfs
    mountpoint = mount_device_rootfs(args)

    # Run the du command
    result = pmb.chroot.root(args, ["sh", "-c", "du -cm . | grep total$ | cut -f1"],
                             working_dir=mountpoint, return_stdout=True)
    return result


def get_chroot_boot_size(args):
    # Mount the device rootfs
    mountpoint = mount_device_rootfs(args)

    # Run the du command
    result = pmb.chroot.root(args, ["sh", "-c", "du -cm ./boot | grep total$ | cut -f1"],
                             working_dir=mountpoint, return_stdout=True)
    return result


def copy_files(args):
    # Mount the device rootfs
    mountpoint = mount_device_rootfs(args)

    # Get all folders inside the device rootfs
    folders = []
    for path in glob.glob(args.work + "/chroot_native" + mountpoint + "/*"):
        folders += [os.path.basename(path)]

    # Run the copy command
    pmb.chroot.root(args, ["cp", "-a"] + folders + ["/mnt/install/"],
                    working_dir=mountpoint)

# copy over keys and delete unneded mount folders


def fix_mount_folders(args):
    # copy over keys
    rootfs = args.work + "/chroot_native/mnt/install/"
    for key in glob.glob(args.work + "/config_apk_keys/*.pub"):
        pmb.helpers.run.root(args, ["cp", key, rootfs + "/etc/apk/keys/"])

    # delete everything (-> empty mount folders) in /home/user
    pmb.helpers.run.root(args, ["rm", "-r", rootfs + "/home/user"])
    pmb.helpers.run.root(args, ["mkdir", rootfs + "/home/user"])
    pmb.helpers.run.root(args, ["chown", pmb.config.chroot_uid_user,
                                rootfs + "/home/user"])


def set_user_password(args):
    """
    Loop until the passwords for user and root have been changed successfully.
    """
    logging.info(" *** SET LOGIN PASSWORD FOR: 'user' ***")
    suffix = "rootfs_" + args.device
    while True:
        try:
            pmb.chroot.root(args, ["passwd", "user"], suffix, log=False)
            break
        except RuntimeError:
            logging.info("WARNING: Failed to set the password. Try it"
                         " one more time.")
            pass


def install(args):
    # Install required programs in native chroot
    logging.info("*** (1/5) PREPARE NATIVE CHROOT ***")
    pmb.chroot.apk.install(args, pmb.config.install_native_packages,
                           build=False)

    # List all packages to be installed (including the ones specified by --add)
    # and upgrade the installed packages/apkindexes
    logging.info("*** (2/5) CREATE DEVICE ROOTFS (" + args.device + ") ***")
    install_packages = (pmb.config.install_device_packages +
                        ["device-" + args.device])
    if args.ui.lower() != "none":
        install_packages += ["postmarketos-ui-" + args.ui]
    suffix = "rootfs_" + args.device
    pmb.chroot.apk.upgrade(args, suffix)

    # Explicitly call build on the install packages, to re-build them or any
    # dependency, in case the version increased
    if args.extra_packages.lower() != "none":
        install_packages += args.extra_packages.split(",")
    if args.add:
        install_packages += args.add.split(",")
    for pkgname in install_packages:
        pmb.build.package(args, pkgname, args.deviceinfo["arch"])

    # Install all packages to device rootfs chroot (and rebuild the initramfs,
    # because that doesn't always happen automatically yet, e.g. when the user
    # installed a hook without pmbootstrap - see #69 for more info)
    pmb.chroot.apk.install(args, install_packages, suffix)
    for flavor in pmb.chroot.other.kernel_flavors_installed(args, suffix):
        pmb.chroot.initfs.build(args, flavor, suffix)

    size_image = str(int(float(get_chroot_size(args)) * 1.15)) + "M"
    size_boot = str(int(get_chroot_boot_size(args)) + 5) + "M"

    # Finally set the user password
    set_user_password(args)

    # Partition and fill image/sdcard
    logging.info("*** (3/5) PREPARE INSTALL BLOCKDEVICE ***")
    pmb.chroot.shutdown(args, True)
    pmb.install.blockdevice.create(args, size_image)
    pmb.install.partition(args, size_boot)
    pmb.install.format(args)

    # Just copy all the files
    logging.info("*** (4/5) FILL INSTALL BLOCKDEVICE ***")
    copy_files(args)
    fix_mount_folders(args)
    pmb.chroot.shutdown(args, True)

    # Convert system image to sparse using img2simg
    if args.deviceinfo["flash_sparse"] == "true":
        logging.info("(native) make sparse system image")
        pmb.chroot.apk.install(args, ["libsparse"])
        sys_image = args.device + ".img"
        sys_image_sparse = args.device + "-sparse.img"
        pmb.chroot.user(args, ["img2simg", sys_image, sys_image_sparse],
                        working_dir="/home/user/rootfs/")
        pmb.chroot.user(args, ["mv", "-f", sys_image_sparse, sys_image],
                        working_dir="/home/user/rootfs/")

    # Kernel flash information
    logging.info("*** (5/5) FLASHING TO DEVICE ***")
    logging.info("Run the following to flash your installation to the"
                 " target device:")
    logging.info("* pmbootstrap flasher flash_kernel")
    logging.info("  Flashes the kernel + initramfs to your device:")
    logging.info("  " + args.work + "/chroot_rootfs_" + args.device +
                 "/boot")
    method = args.deviceinfo["flash_methods"]
    if (method in pmb.config.flashers and "boot" in
            pmb.config.flashers[method]["actions"]):
        logging.info("  (NOTE: " + method + " also supports booting"
                     " the kernel/initramfs directly without flashing."
                     " Use 'pmbootstrap flasher boot' to do that.)")

    # System flash information
    if not args.sdcard:
        logging.info("* pmbootstrap flasher flash_system")
        logging.info("  Flashes the system image, that has been"
                     " generated to your device:")
        logging.info("  " + args.work + "/chroot_native/home/user/rootfs/" +
                     args.device + ".img")
        logging.info("  (NOTE: This file has a partition table,"
                     " which contains a boot- and root subpartition.)")

    # Export information
    logging.info("* If the above steps do not work, you can also create"
                 " symlinks to the generated files with 'pmbootstrap flasher"
                 " export [export_folder]' and flash outside of pmbootstrap.")
