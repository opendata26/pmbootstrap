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
import os
import sys
import pytest
import glob
import filecmp

# Import from parent directory
sys.path.append(os.path.realpath(
    os.path.join(os.path.dirname(__file__) + "/..")))
import pmb.parse.apkindex
import pmb.helpers.git
import pmb.helpers.logging


@pytest.fixture
def args(request):
    import pmb.parse
    sys.argv = ["pmbootstrap.py", "chroot"]
    args = pmb.parse.arguments()
    args.log = args.work + "/log_testsuite.txt"
    pmb.helpers.logging.init(args)
    request.addfinalizer(args.logfd.close)
    return args


def test_keys(args):
    mirror_path = os.path.join(os.path.dirname(__file__) + "../keys")
    original_path = args.work + "/cache_git/aports_upstream/main/alpine-keys"
    pmb.helpers.git.clone(args, "aports_upstream")

    # Check if original keys are mirrored correctly
    for path in glob.glob(original_path + "/*.key"):
        key = os.path.basename(path)
        assert filecmp.cmp(original_path + "/" + key, mirror_path + "/" + key,
                           False)

    # Find outdated keys, which need to be removed
    for path in glob.glob(mirror_path + "/*.key"):
        assert os.path.exists(original_path + "/" + os.path.basename(path))
