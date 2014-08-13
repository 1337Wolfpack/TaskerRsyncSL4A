#!/usr/bin/python

import os
import os.path
import glob 
import string
import re 
import sys 
import getopt 
import stat 
import shutil
import random

 
try:
	import win32file #Win32 imports, for testing and running on Windows
except:
	win32file = None

isAndroid =False
extras = []

try:
    import android
    isAndroid = True
    droid = android.Android()
    extras = droid.getIntent().result['extras']
except :
    isAndroid = False




class Options:
	def __init__(self):
		self.sink_root = ""
		self.target_root = ""
		self.quiet = 0
		self.recursive = 0
		self.relative = 0
		self.dry_run = 0
		self.time = 0
		self.update = 0
		self.cvs_ignore = 0
		self.ignore_time = 0
		self.delete = 0
		self.delete_excluded = 0
		self.delete_from_source = 0
		self.size_only = 0
		self.modify_window = 2
		self.existing = 0
		self.filters = []
		self.case_sensitivity = 0
		if os.name == "nt":
			self.case_sensitivity = re.I

def visit(options, dirname, names):
	"""Copy files names from sink_root + (dirname - sink_root) to target_root + (dirname - sink_root)"""
	if os.path.split(options.sink_root)[1]: 
		dirname = dirname[len(options.sink_root) + 1:]
	else:
		dirname = dirname[len(options.sink_root):]
	target_dir = os.path.join(options.target_root, dirname)
	if not os.path.isdir(target_dir):
		makeDir(options, target_dir)
	sink_dir = os.path.join(options.sink_root, dirname)

	filters = []
	if options.cvs_ignore:
		ignore = os.path.join(sink_dir, ".cvsignore")
		if os.path.isfile(ignore):
			filters = convertPatterns(ignore, "-")
	filters = filters + options.filters

	names_excluded = []
	if filters:
		# filter sink files (names):
		name_index = 0
		while name_index < len(names):
			name = names[name_index]
			path = os.path.join(dirname, name)
			path = convertPath(path)
			if os.path.isdir(os.path.join(sink_dir, name)):
				path = path + "/"
			for filter in filters:
				if re.search(filter[1], path, options.case_sensitivity):
					if filter[0] == '-':
						sink = os.path.join(sink_dir, name)
						if options.delete_from_source:
							if os.path.isfile(sink):
								removeFile(options, sink)
							elif os.path.isdir(sink):
								removeDir(options, sink)
							else:
								logError("Sink %s is neither a file nor a folder (skip removal)" % sink)
						names_excluded += [names[name_index]]
						del(names[name_index])
						name_index = name_index - 1
						break 
					elif filter[0] == '+':
						break
			name_index = name_index + 1

	if options.delete and os.path.isdir(target_dir):
		# Delete files and folder in target not present in filtered sink.
		for name in os.listdir(target_dir):
			if not options.delete_excluded and name in names_excluded:
				continue
			if not name in names:
				target = os.path.join(target_dir, name)
				if os.path.isfile(target):
					removeFile(options, target)
				elif os.path.isdir(target):
					removeDir(options, target)
				else:
					pass

	for name in names:
		# Copy files and folder from sink to target.
		sink = os.path.join(sink_dir, name)
		#print sink
		target = os.path.join(target_dir, name)
		if os.path.exists(target):
			# When target already exit:
			if os.path.isfile(sink):
				if os.path.isfile(target):
					# file-file
					if shouldUpdate(options, sink, target):
						updateFile(options, sink, target)
				elif os.path.isdir(target):
					# file-folder
					removeDir(options, target)
					copyFile(options, sink, target)
				else:
					# file-???
					logError("Target %s is neither a file nor folder (skip update)" % sink)

			elif os.path.isdir(sink):
				if os.path.isfile(target):
					# folder-file
					removeFile(options, target)
					makeDir(options, target)
			else:
				# ???-xxx
				logError("Sink %s is neither a file nor a folder (skip update)" % sink)

		elif not options.existing:
			# When target dont exist:
			if os.path.isfile(sink):
				# file
				copyFile(options, sink, target)
			elif os.path.isdir(sink):
				# folder
				makeDir(options, target)
			else:
				logError("Sink %s is neither a file nor a folder (skip update)" % sink)


def log(options, message):
	if not options.quiet:
		try:
			print message
		except UnicodeEncodeError:
			print message.encode("utf8")


def logError(message):
	try:
		sys.stderr.write(message + "\n")
	except UnicodeEncodeError:
		sys.stderr.write(message.encode("utf8") + "\n")


def shouldUpdate(options, sink, target):
	try:
		sink_st = os.stat(sink)
		sink_sz = sink_st.st_size
		sink_mt = sink_st.st_mtime
	except:
		logError("Fail to retrieve information about sink %s (skip update)" % sink)
		return 0

	try:
		target_st = os.stat(target)
		target_sz = target_st.st_size
		target_mt = target_st.st_mtime
	except:
		logError("Fail to retrieve information about target %s (skip update)" % target)
		return 0

	if options.update:
		return target_mt < sink_mt - options.modify_window

	if options.ignore_time:
		return 1

	if target_sz != sink_sz:
		return 1

	if options.size_only:
		return 0

	return abs(target_mt - sink_mt) > options.modify_window


def copyFile(options, sink, target):
	log(options, "copy: %s to: %s" % (sink, target))
	if not options.dry_run:
		try:
			shutil.copyfile(sink, target)
			error = shutil.copyfile(sink, target)
		except:
			logError("Fail to copy %s" % sink)
			logError("shitul error : %s" % error)

		if options.time:
			try:
				s = os.stat(sink)
				os.utime(target, (s.st_atime, s.st_mtime));
			except:
				logError("Fail to copy timestamp of %s" % sink)


def updateFile(options, sink, target):
	log(options, "update: %s to: %s" % (sink, target))
	if not options.dry_run:
		# Read only and hidden and system files can not be overridden.
		try:
			try:
				if win32file:
					filemode = win32file.GetFileAttributesW(target)
					win32file.SetFileAttributesW(target, filemode & ~win32file.FILE_ATTRIBUTE_READONLY & ~win32file.FILE_ATTRIBUTE_HIDDEN & ~win32file.FILE_ATTRIBUTE_SYSTEM)
				else:
					os.chmod(target, stat.S_IWUSR)
			except:
				pass

			shutil.copyfile(sink, target)
			if options.time:
				try:
					s = os.stat(sink)
					os.utime(target, (s.st_atime, s.st_mtime));
				except:
					logError("Fail to copy timestamp of %s" % sink) # The utime issues with unicode
		except:
			logError("Fail to override %s" % sink)

		if win32file:
			win32file.SetFileAttributesW(target, filemode)


def prepareRemoveFile(path):
	if win32file:
		filemode = win32file.GetFileAttributesW(path)
		win32file.SetFileAttributesW(path, filemode & ~win32file.FILE_ATTRIBUTE_READONLY & ~win32file.FILE_ATTRIBUTE_HIDDEN & ~win32file.FILE_ATTRIBUTE_SYSTEM)
	else:
		os.chmod(path, stat.S_IWUSR)


def removeFile(options, target):
	# Read only files could not be deleted.
	log(options, "remove: %s" % target)
	if not options.dry_run:
		try:
			try:
				prepareRemoveFile(target)
			except:
				#logError("Fail to allow removal of %s" % target)
				pass

			os.remove(target)
		except:
			logError("Fail to remove %s" % target)



def makeDir(options, target):
	log(options, "make dir: %s" % target)
	if not options.dry_run:
		try:
			os.makedirs(target)
		except:
			logError("Fail to make dir %s" % target)


def visitForPrepareRemoveDir(arg, dirname, names):
	for name in names:
		path = os.path.join(dirname, name)
		prepareRemoveFile(path)


def prepareRemoveDir(path):
	prepareRemoveFile(path)
	os.path.walk(path, visitForPrepareRemoveDir, None)


def OnRemoveDirError(func, path, excinfo):
	logError("Fail to remove %s" % path)


def removeDir(options, target):
	# Read only directory could not be deleted.
	log(options, "remove dir: %s" % target)
	if not options.dry_run:
		prepareRemoveDir(target)
		try:
			shutil.rmtree(target, False, OnRemoveDirError)
		except:
			logError("Fail to remove dir %s" % target)


def convertPath(path):
	# Convert windows, mac path to unix version.
	separator = os.path.normpath("/")
	if separator != "/":
		path = re.sub(re.escape(separator), "/", path)

	
	path = "/" + path
	return path


def convertPattern(pattern, sign):
	"""Convert a rsync pattern that match against a path to a filter that match against a converted path."""

	# Check for include vs exclude patterns.
	if pattern[:2] == "+ ":
		pattern = pattern[2:]
		sign = "+"
	elif pattern[:2] == "- ":
		pattern = pattern[2:]
		sign = "-"

	# Express windows, mac patterns in unix patterns (rsync.py extension).
	separator = os.path.normpath("/")
	if separator != "/":
		pattern = re.sub(re.escape(separator), "/", pattern)

	# If pattern contains '/' it should match from the start.
	temp = pattern
	if pattern[0] == "/":
		pattern = pattern[1:]
	if temp[-1] == "/":
		temp = temp[:-1]

	# Convert pattern rules: ** * ? to regexp rules.
	pattern = re.escape(pattern)
	pattern = string.replace(pattern, "\\?", ".")
	pattern = string.replace(pattern, "\\*\\*", ".*")
	pattern = string.replace(pattern, "\\*", "[^/]*")
	pattern = string.replace(pattern, "\\*", ".*")

	if "/" in temp:
		# If pattern contains '/' it should match from the start.
		pattern = "^\\/" + pattern
	else:
		# Else the pattern should match the all file or folder name.
		pattern = "\\/" + pattern

	if pattern[-2:] != "\\/" and pattern[-2:] != ".*":
		# File patterns should match also folders.
		pattern = pattern + "\\/?"

	# Pattern should match till the end.
	pattern = pattern + "$"
	return (sign, pattern)


def convertPatterns(path, sign):
	"""Read the files for pattern and return a vector of filters"""
	filters = []
	f = open(path, "r")
	while 1:
		pattern = f.readline()
		if not pattern:
			break
		if pattern[-1] == "\n":
			pattern = pattern[:-1]

		if re.match("[\t ]*$", pattern):
			continue
		if pattern[0] == "#":
			continue
		filters = filters + [convertPattern(pattern, sign)]
	f.close()
	return filters


def printUsage():
	"""Print the help string that should printed by rsync.py -h"""
	print "usage: Create Variables in tasker. You need %options, %source and %destination"
	print "example : %options = -tr, source = /sdcard, destination = /sdcard/cifs/rwmountedwindowshare/Backups"
	print """
 -q, --quiet              decrease verbosity
 -r, --recursive          recurse into directories
 -R, --relative           use relative path names
 -u, --update             update only (don't overwrite newer files)
 -t, --times              preserve times
 -n, --dry-run            show what would have been transferred
     --existing           only update files that already exist
     --delete             delete files that don't exist on the sending side
     --delete-excluded    also delete excluded files on the receiving side
     --delete-from-source delete excluded files on the receiving side
 -I, --ignore-times       don't exclude files that match length and time
     --size-only          only use file size when determining if a file should
                          be transferred
     --modify-window=NUM  timestamp window (seconds) for file match (default=2)
     --existing           only update existing target files or folders
 -C, --cvs-exclude        auto ignore files in the same way CVS does
     --exclude=PATTERN    exclude files matching PATTERN
     --exclude-from=FILE  exclude patterns listed in FILE
     --include=PATTERN    don't exclude files matching PATTERN
     --include-from=FILE  don't exclude patterns listed in FILE
     --version            print version number
 -h, --help               show this help screen

See https://github.com/1337Wolfpack/TaskerRsyncSL4A for informations and updates."""


def printVersion():
	print "py-rsync.py for android v0.5"


def main(args):
	options = Options()
	print "test with args %s" % (args)

	opts, args = getopt.getopt(args, "qrRntuCIh", ["quiet", "recursive", "relative", "dry-run", "time", "update", "cvs-ignore", "ignore-times", "help", "delete", "delete-excluded", "delete-from-source", "existing", "size-only", "modify-window=", "exclude=", "exclude-from=", "include=", "include-from=", "version"])
	for o, v in opts:
		if o in ["-q", "--quiet"]:
			options.quiet = 1
		if o in ["-r", "--recursive"]:
			print "found option recursive"
			options.recursive = 1
		if o in ["-R", "--relative"]:
			options.relative = 1
		elif o in ["-n", "--dry-run"]:
			options.dry_run = 1
		elif o in ["-t", "--times"]: 
			options.time = 1
		elif o in ["-u", "--update"]:
			options.update = 1
		elif o in ["-C", "--cvs-ignore"]:
			options.cvs_ignore = 1
		elif o in ["-I", "--ignore-time"]:
			options.ignore_time = 1
		elif o == "--delete":
			options.delete = 1
		elif o == "--delete-excluded":
			options.delete = 1
			options.delete_excluded = 1
		elif o == "--delete-from-source":
			options.delete_from_source = 1
		elif o == "--size-only":
			options.size_only = 1
		elif o == "--modify-window":
			options.modify_window = int(v)
		elif o == "--existing":
			options.existing = 1
		elif o == "--exclude":
			options.filters = options.filters + [convertPattern(v, "-")]
		elif o == "--exclude-from":
			options.filters = options.filters + convertPatterns(v, "-")
		elif o == "--include":
			options.filters = options.filters + [convertPattern(v, "+")]
		elif o == "--include-from":
			options.filters = options.filters + convertPatterns(v, "+")
		elif o == "--version":
			printVersion()
			return 0
		elif o in ["-h", "--help"]:
			printUsage()
			return 0

	if len(args) <= 1:
		printUsage()
		return 1

	

	target_root = args[1]
	try: 
		pass
		if os.path.__dict__.has_key("supports_unicode_filenames") and os.path.supports_unicode_filenames:
			target_root = unicode(target_root, 'utf-8')
	finally:
		options.target_root = target_root

	sinks = glob.glob(args[0])
	if not sinks:
		return 0

	sink_families = {}
	for sink in sinks:
		try: 
			if os.path.__dict__.has_key("supports_unicode_filenames") and os.path.supports_unicode_filenames:
				sink = unicode(sink, sys.getfilesystemencoding())
		except:
			pass
		sink_name = ""
		sink_root = sink
		sink_drive, sink_root = os.path.splitdrive(sink)
		while not sink_name:
			if sink_root == os.path.sep:
				sink_name = "."
				break
			sink_root, sink_name = os.path.split(sink_root)
		sink_root = sink_drive + sink_root
		if not sink_families.has_key(sink_root):
			sink_families[sink_root] = []
		sink_families[sink_root] = sink_families[sink_root] + [sink_name]

	for sink_root in sink_families.keys():
		if options.relative:
			options.sink_root = ""
		else:
			options.sink_root = sink_root

		global y 
		y = sink_root
		files = filter(lambda x: os.path.isfile(os.path.join(y, x)), sink_families[sink_root])
		if files:
			visit(options, sink_root, files)

		y = sink_root
		folders = filter(lambda x: os.path.isdir(os.path.join(y, x)), sink_families[sink_root])
		for folder in folders:
			folder_path = os.path.join(sink_root, folder)
			if not options.recursive:
				visit(options, folder_path, os.listdir(folder_path))
			else:
				os.path.walk(folder_path, visit, options)
	return 0


if __name__ == "__main__":
	
	if isAndroid == True:
		try:
			options, source, destination = extras['%options'], extras['%source'], extras['%destination']
		except:
			#default options for testing
			options, source, destination = '-tr', '/sdcard/scripts', '/sdcard/scripts' + str(random.randint(1, 100))
		sys.exit(main([options, source, destination]))
	else:
		#command line behaviour still usable I used on windows and linux
		sys.exit(main(sys.argv[1:]))

class rsync(object):#for imports, to test
	def	__init__(self, args):
	    main(args)
	