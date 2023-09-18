import subprocess
from os import path
import os
import shutil
from glob import glob
import typing
import sys
import platform

# TODO:
# - Auto download backends deps
#		It should be relatively easy to automatically clone any deps.
# - Don't `cd` into temp folder
#		When compiling, we `cd` into the temp folder, as there's no option
#		for clang or gcc to output .o files into another folder.
#		We should probably instead run one compile command per source file.
#		This lets us specify the output file, as well as compiling in paralell
# - Make this file never show it's call stack. Call stacks should mean that a child script failed.

# @CONFIGURE: Must be key into below table
active_branch = "docking"
git_heads = {
	# Default Dear ImGui branch
	"master": { "imgui": "6addf28c4", "dear_bindings": "364a9572532705" },
	# Docking branch
	"docking": { "imgui": "7e246a7bb", "dear_bindings": "364a9572532705" },
}

# @CONFIGURE: Elements must be keys into below table
wanted_backends = ["vulkan", "sdl2", "opengl3", "sdlrenderer2", "glfw", "dx11", "dx12", "win32", "osx", "metal"]
# Supported means that an impl bindings file exists, and that it has been tested.
# Some backends (like dx12, win32) have bindings but not been tested.
backends = {
	"allegro5":     { "supported": False },
	"android":      { "supported": False },
	"dx9":          { "supported": False, "enabled_on": ["windows"] },
	"dx10":         { "supported": False, "enabled_on": ["windows"] },
	"dx11":         { "supported": True,  "enabled_on": ["windows"] },
	# Bindings exist for DX12, but they are untested
	"dx12":         { "supported": False, "enabled_on": ["windows"] },
	# Requires https://github.com/glfw/glfw.git at commit 3eaf125
	"glfw":         { "supported": True,  "includes": [["glfw", "include"]] },
	"glut":         { "supported": False },
	"metal":        { "supported": False, "enabled_on": ["darwin"] },
	"opengl2":      { "supported": False },
	"opengl3":      { "supported": True  },
	"osx":          { "supported": False, "enabled_on": ["darwin"] },
	# Requires https://github.com/libsdl-org/SDL.git at tag release-2.28.3/commit 8a5ba43
	"sdl2":         { "supported": True,  "includes": [["SDL", "include"]] },
	"sdl3":         { "supported": False },
	# Requires https://github.com/libsdl-org/SDL.git at tag release-2.28.3/commit 8a5ba43
	"sdlrenderer2": { "supported": True },
	"sdlrenderer3": { "supported": False },
	# Requires https://github.com/KhronosGroup/Vulkan-Headers.git commit 4f51aac
	"vulkan":       { "supported": True,  "includes": [["Vulkan-Headers", "include"]], "defines": ["VK_NO_PROTOTYPES"] },
	"wgpu":         { "supported": False },
	# Bindings exist for win32, but they are untested
	"win32":        { "supported": False, "enabled_on": ["windows"] },
}

# @CONFIGURE:
compile_debug = False

platform_win32_like = platform.system() == "Windows"
platform_unix_like = platform.system() == "Linux" or platform.system() == "Darwin"

# Assert which doesn't clutter the output
def assertx(cond: bool, msg: str):
	if not cond:
		print(msg)
		exit(1)

def hashes_are_same_ish(first: str, second: str) -> bool:
	smallest_hash_size = min(len(first), len(second))
	assertx(smallest_hash_size >= 7, "Hashes not long enough to be sure")
	return first[:smallest_hash_size] == second[:smallest_hash_size]

def exec(cmd: typing.List[str], what: str) -> str:
	max_what_len = 40
	if len(what) > max_what_len:
		what = what[:max_what_len - 2] + ".."
	print(what + (" " * (max_what_len - len(what))) + "> " + " ".join(cmd))
	return subprocess.check_output(cmd).decode().strip()

def copy(from_path: str, files: typing.List[str], to_path: str):
	for file in files:
		shutil.copy(path.join(from_path, file), to_path)

def glob_copy(root_dir: str, glob_pattern: str, dest_dir: str):
	the_files = glob(root_dir=root_dir, pathname=glob_pattern)
	copy(root_dir, the_files, dest_dir)
	return the_files

def platform_select(the_options):
	""" Given a dict like eg. { "windows": "/DCOOL_DEFINE", "linux, darwin": "-DCOOL_DEFINE" }
	Returns the correct value for the active platform. """
	our_platform = platform.system().lower()
	for platforms_string in the_options:
		if platforms_string.lower().find(our_platform) != -1:
			return the_options[platforms_string]

	print(the_options)
	assertx(False, f"Couldn't find active platform ({our_platform}) in the above options!")

def pp(the_path: str) -> str:
	""" Given a path with '/' as a delimiter, returns an appropriate sys.platform path """
	return path.join(*the_path.split("/"))

def map_to_folder(files: typing.List[str], folder: str) -> typing.List[str]:
	return list(map(lambda file: path.join(folder, file), files))

def ensure_outside_of_repo():
	assertx(not path.isfile("gen_odin.py"), "You must run this from outside of the odin-imgui repository!")

def run_vcvars(cmd: typing.List[str]):
	assertx(subprocess.run(f"vcvarsall.bat x64 && {' '.join(cmd)}").returncode == 0, f"Failed to run command '{cmd}'")

def ensure_checked_out_with_commit(dir: str, repo: str, wanted_commit: str):
	# We assume that we are at least not using a completely wrong git repo
	if not path.isdir(dir):
		exec(["git", "clone", repo], f"Checking out {dir}")

	active_commit = exec(["git", "-C", dir, "rev-parse", "--short", "HEAD"], f"Checking active commit for {dir}")
	if hashes_are_same_ish(active_commit, wanted_commit):
		return
	else:
		print(f"{dir} on unwanted commit {active_commit}")
		exec(["git", "-C", dir, "checkout", wanted_commit], f"Checking out wanted commit {wanted_commit}")

def get_platform_imgui_lib_name() -> str:
	""" Returns imgui binary name for system/processor """

	system = platform.system()

	processor = None
	if platform.machine() in ["AMD64", "x86_64"]:
		processor = "x64"
	if platform.machine() in ["arm64"]:
		processor = "arm64"

	binary_ext = "lib" if system == "Windows" else "a"

	assertx(system != "", "System could not be determined")
	assertx(processor != None, "Could not determine processor")

	return f'imgui_{system.lower()}_{processor}.{binary_ext}'

def main():
	ensure_outside_of_repo()
	ensure_checked_out_with_commit("imgui", "https://github.com/ocornut/imgui.git", git_heads[active_branch]["imgui"])
	ensure_checked_out_with_commit("dear_bindings", "https://github.com/dearimgui/dear_bindings.git", git_heads[active_branch]["dear_bindings"])

	# Clear our temp and build folder
	shutil.rmtree(path="temp", ignore_errors=True)
	os.mkdir("temp")
	shutil.rmtree(path="build", ignore_errors=True)
	os.mkdir("build")

	# Generate bindings for active ImGui branch
	exec([sys.executable, pp("dear_bindings/dear_bindings.py"), "-o", pp("temp/c_imgui"), pp("imgui/imgui.h")], "Running dear_bindings")
	# Generate odin bindings from dear_bindings json file
	exec([sys.executable, pp("odin-imgui/gen_odin.py"), pp("temp/c_imgui.json"), pp("build/imgui.odin")], "Running odin-imgui")

	# Find and copy imgui sources to temp folder
	_imgui_headers = glob_copy("imgui", "*.h", "temp")
	imgui_sources = glob_copy("imgui", "*.cpp", "temp")

	# Gather sources, defines, includes etc
	all_sources = imgui_sources
	all_sources += ["c_imgui.cpp"]

	# Basic flags
	compile_flags = platform_select({
		"windows": ['/DIMGUI_IMPL_API=extern\\\"C\\\"'],
		"linux, darwin": ['-DIMGUI_IMPL_API=extern\"C\"', "-fPIC", "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics"],
	})

	# Optimization flags
	if compile_debug: compile_flags += platform_select({ "windows": ["/Od", "/Z7"], "linux, darwin": ["-g", "-O0"] })
	else: compile_flags += platform_select({ "windows": ["/O2"], "linux, darwin": ["-O3"] })

	# Write file describing the enabled backends
	f = open(pp("build/impl_enabled.odin"), "w+")
	f.writelines([
		"package imgui\n",
		"\n",
		"// This is a generated helper file which you can use to know which\n",
		"// implementations have been compiled into the bindings.\n",
		"\n",
	])

	for backend_name in backends:
		f.writelines([f"BACKEND_{backend_name.upper()}_ENABLED :: {'true' if backend_name in wanted_backends else 'false'}\n"])

	# Find and copy imgui backend sources to temp folder
	for backend_name in wanted_backends:
		backend = backends[backend_name]

		if "enabled_on" in backend and not platform.system().lower() in backend["enabled_on"]:
			continue

		if not backend["supported"]:
			print(f"Warning: compiling backend '{backend_name}' which is not officially supported")

		glob_copy(pp("imgui/backends"), f"imgui_impl_{backend_name}.*", "temp")

		if backend_name in ["osx", "metal"]: all_sources += [f"imgui_impl_{backend_name}.mm"]
		else:                                all_sources += [f"imgui_impl_{backend_name}.cpp"]

		if backend_name == "opengl3":
			shutil.copy(pp("imgui/backends/imgui_impl_opengl3_loader.h"), "temp")

		for define in backend.get("defines", []): compile_flags += [platform_select({ "windows": f"/D{define}", "linux, darwin": f"-D{define}" })]

		for include in backend.get("includes", []):
			if platform_win32_like:  compile_flags += ["/I" + path.join("..", "backend_deps", path.join(*include))]
			elif platform_unix_like: compile_flags += ["-I" + path.join("..", "backend_deps", path.join(*include))]

	# Copy implementation files
	glob_copy("odin-imgui", "imgui_impl_*.odin", "build")

	all_objects = []
	if platform_win32_like:  all_objects += map(lambda file: file.removesuffix(".cpp") + ".obj", all_sources)
	elif platform_unix_like: all_objects += map(lambda file: file.removesuffix(".cpp") + ".o", all_sources)

	os.chdir("temp")

	if platform_win32_like:  run_vcvars(["cl"] + compile_flags + ["/c"] + all_sources)
	elif platform_unix_like: exec(["clang"] + compile_flags + ["-c"] + all_sources, "Compiling sources")

	os.chdir("..")

	dest_binary = get_platform_imgui_lib_name()

	if platform_win32_like:  run_vcvars(["lib", "/OUT:" + path.join("build", dest_binary)] + map_to_folder(all_objects, "temp"))
	elif platform_unix_like: exec(["ar", "rcs", path.join("build", dest_binary)] + map_to_folder(all_objects, "temp"), "Making library from objects")

	expected_files = ["imgui.odin", "impl_enabled.odin", dest_binary]

	for file in expected_files:
		assertx(path.isfile(path.join("build", file)), f"Missing file '{file}' in build folder! Something went wrong..")

	print("Looks like everything went ok!")

if __name__ == "__main__":
	main()
