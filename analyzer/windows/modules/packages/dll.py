# Copyright (C) 2010-2015 Cuckoo Foundation.
# This file is part of Cuckoo Sandbox - http://www.cuckoosandbox.org
# See the file 'docs/LICENSE' for copying permission.

import contextlib
import os
import shutil

from lib.common.abstracts import Package
from lib.common.common import check_file_extension

MAX_DLL_EXPORTS_DEFAULT = 8


class Dll(Package):
    """DLL analysis package."""

    PATHS = [
        ("SystemRoot", "System32", "rundll32.exe"),
    ]

    def start(self, path):
        rundll32 = self.get_path("rundll32.exe")
        arguments = self.options.get("arguments", "")
        dllloader = self.options.get("dllloader")

        # If the file doesn't have the proper .dll extension force it
        # and rename it. This is needed for rundll32 to execute correctly.
        # See ticket #354 for details.
        path = check_file_extension(path, ".dll")

        if dllloader:
            newname = os.path.join(os.path.dirname(rundll32), dllloader)
            shutil.copy(rundll32, newname)
            rundll32 = newname

        # If user has requested we use something (function, functions, ordinal, ordinal range)
        function = self.options.get("function")
        run_ordinal_range = False
        run_multiple_functions = False
        if function:

            # If user has requested we use functions, separated by commas
            if "," in function:
                function = function.split(",")
                run_multiple_functions = True

            # If user has requested we use an ordinal range, separated by a hyphen or by ..
            elif "-" in function or ".." in function:
                run_ordinal_range = True

        # If user has not requested that we use something, we should default to running all available exports, up to a limit
        else:
            available_exports = self.config.exports.split(",")

            # Used for export discovery / splitting
            use_export_name = self.options.get("use_export_name")
            if use_export_name.lower() in ["on", "yes", "true"]:
                use_export_name = True
            else:
                use_export_name = False

            if not available_exports:
                if use_export_name:
                    function = ["DllMain", "DllRegisterServer"]
                    run_multiple_functions = True
                else:
                    function = "#1"
            else:
                max_dll_exports = int(self.options.get("max_dll_exports", MAX_DLL_EXPORTS_DEFAULT))
                if max_dll_exports <= 0:
                    max_dll_exports = MAX_DLL_EXPORTS_DEFAULT
                dll_exports_num = min(len(available_exports), max_dll_exports)

                if use_export_name:
                    function = available_exports[:dll_exports_num]
                    run_multiple_functions = True
                else:
                    function = f"#1-{dll_exports_num}"
                    run_ordinal_range = True

        if run_ordinal_range:
            with contextlib.suppress(ValueError, AssertionError):
                start, end = (int(_.lstrip("#")) for _ in function.replace("..", "-").split("-", 1))
                assert start < end
                args = '/c for /l %i in ({start},1,{end}) do @{rundll32} "{path}",#%i {arguments}'.format(**locals())
                # if there are multiple functions launch them by their ordinal number in a for loop via cmd.exe calling rundll32.exe
                return self.execute("C:\\Windows\\System32\\cmd.exe", args.strip(), path)

        elif run_multiple_functions:
            ret_list = []
            for function_name in function:
                args = f'"{path}"' if dllloader == "regsvcs.exe" else f'"{path}",{function_name}'
                if arguments:
                    args += f" {arguments}"

                ret_list.append(self.execute(rundll32, args, path))
            return ret_list

        else:
            args = f'"{path}"' if dllloader == "regsvcs.exe" else f'"{path}",{function}'
            if arguments:
                args += f" {arguments}"

            return self.execute(rundll32, args, path)
